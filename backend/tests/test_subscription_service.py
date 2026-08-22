from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from backend.db.base import Base
from backend.db.session import create_session_factory

from backend.db.models import Plan, Subscription, SubscriptionStatus, User
from backend.services.billing.iyzico_client import CheckoutSession, ProviderSubscription
from backend.services.billing.subscription_service import (
    BillingInterval,
    CheckoutRecord,
    LocalPlan,
    LocalSubscription,
    PlanReferenceMap,
    SubscriptionService,
    SqlAlchemySubscriptionRepository,
    SubscriptionServiceError,
    paid_entitlement_is_active,
)


@dataclass
class FakeRepository:
    plan: LocalPlan
    subscription: LocalSubscription | None = None
    status_writes: list[SubscriptionStatus] | None = None
    created_subscriptions: list[LocalSubscription] | None = None
    checkout: CheckoutRecord | None = None
    additional_plan: LocalPlan | None = None

    def __post_init__(self) -> None:
        self.status_writes = []
        self.created_subscriptions = []

    async def get_plan(self, code: str) -> LocalPlan | None:
        if self.plan.code == code:
            return self.plan
        return self.additional_plan if self.additional_plan and self.additional_plan.code == code else None

    async def get_subscription(self, user_id: UUID) -> LocalSubscription | None:
        return self.subscription if self.subscription and self.subscription.user_id == user_id else None

    async def set_status(self, subscription_id: UUID, status: SubscriptionStatus) -> None:
        assert self.subscription is not None
        assert subscription_id == self.subscription.id
        self.status_writes.append(status)
        self.subscription.status = status

    async def change_plan(self, subscription_id: UUID, subscription: LocalSubscription) -> None:
        assert self.subscription is not None
        assert subscription_id == self.subscription.id
        self.subscription = subscription

    async def upsert_subscription(self, subscription: LocalSubscription) -> None:
        self.subscription = subscription
        self.created_subscriptions.append(subscription)

    async def reserve_checkout(self, **kwargs) -> CheckoutRecord:
        kwargs.pop("cooldown_seconds")
        if self.checkout and self.checkout.idempotency_key_hash == kwargs["idempotency_key_hash"]:
            if self.checkout.request_fingerprint != kwargs["request_fingerprint"]:
                raise SubscriptionServiceError("checkout idempotency key payload ile eslesmiyor")
            return self.checkout
        if self.subscription and self.subscription.status in {
            SubscriptionStatus.PENDING, SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE
        }:
            raise SubscriptionServiceError("kullanicinin devam eden aboneligi var")
        self.checkout = CheckoutRecord(id=uuid4(), token_hash=None, **kwargs)
        return self.checkout

    async def attach_checkout_token(
        self,
        checkout_id: UUID,
        token_hash: str,
        expires_in_seconds: int,
        response_ciphertext: str,
    ) -> None:
        assert self.checkout and self.checkout.id == checkout_id
        self.checkout.token_hash = token_hash
        self.checkout.response_ciphertext = response_ciphertext

    async def get_checkout(self, token_hash: str) -> CheckoutRecord | None:
        return self.checkout if self.checkout and self.checkout.token_hash == token_hash else None

    async def consume_checkout(self, checkout_id: UUID, subscription: LocalSubscription) -> None:
        assert self.checkout and self.checkout.id == checkout_id
        if not self.checkout.consumed:
            await self.upsert_subscription(subscription)
            self.checkout.consumed = True


class FakeIyzicoClient:
    def __init__(self) -> None:
        self.checkout_refs: list[str] = []
        self.retrieve_calls = 0
        self.subscription = ProviderSubscription(
            reference_code="sub-1",
            product_reference_code="product-creator",
            pricing_plan_reference_code="creator-monthly",
            status="ACTIVE",
        )

    async def initialize_subscription_checkout(self, **kwargs) -> CheckoutSession:
        self.checkout_refs.append(kwargs["pricing_plan_reference_code"])
        return CheckoutSession("checkout-token", "<script>hosted</script>", 1800)

    async def get_subscription(self, reference_code: str) -> ProviderSubscription:
        assert reference_code == self.subscription.reference_code
        return self.subscription

    async def cancel_subscription(self, reference_code: str) -> None:
        assert reference_code == "sub-1"
        self.subscription = ProviderSubscription(
            reference_code="sub-1",
            product_reference_code="product-creator",
            pricing_plan_reference_code="creator-monthly",
            status="CANCELED",
        )

    async def retrieve_checkout(self, token: str) -> ProviderSubscription:
        self.retrieve_calls += 1
        assert token == "checkout-token"
        return self.subscription

    async def upgrade_subscription(self, reference_code: str, pricing_reference: str) -> str:
        assert reference_code == "sub-1"
        assert pricing_reference == "pro-monthly"
        self.subscription = ProviderSubscription(
            reference_code="sub-2",
            product_reference_code="product-creator",
            pricing_plan_reference_code="pro-monthly",
            status="ACTIVE",
        )
        return "sub-2"


def _references() -> PlanReferenceMap:
    return PlanReferenceMap.from_json(
        '{"creator":{"product_reference_code":"product-creator",'
        '"monthly":"creator-monthly","yearly":"creator-yearly"}}'
    )


def _change_references() -> PlanReferenceMap:
    return PlanReferenceMap.from_json(
        '{"creator":{"product_reference_code":"product-creator","monthly":"creator-monthly","yearly":"creator-yearly"},'
        '"pro":{"product_reference_code":"product-creator","monthly":"pro-monthly","yearly":"pro-yearly"}}'
    )


def test_active_subscription_can_change_to_a_plan_in_the_same_product_and_interval() -> None:
    user_id = uuid4()
    repository = FakeRepository(
        LocalPlan(id=uuid4(), code="creator", active=True),
        subscription=LocalSubscription(uuid4(), user_id, "sub-1", "creator", SubscriptionStatus.ACTIVE),
        additional_plan=LocalPlan(id=uuid4(), code="pro", active=True),
    )
    service = SubscriptionService(
        repository, FakeIyzicoClient(), _change_references(),
        "https://api.example.com/callback", "test-checkout-secret",
    )

    snapshot = asyncio.run(service.change_plan(user_id, "pro", BillingInterval.MONTHLY))

    assert snapshot.plan_code == "pro"
    assert snapshot.status is SubscriptionStatus.ACTIVE
    assert repository.subscription is not None
    assert repository.subscription.provider_reference == "sub-2"


@pytest.mark.parametrize(
    ("interval", "expected_reference"),
    [
        (BillingInterval.MONTHLY, "creator-monthly"),
        (BillingInterval.YEARLY, "creator-yearly"),
    ],
)
def test_checkout_maps_monthly_and_yearly_without_granting_entitlement(
    interval: BillingInterval,
    expected_reference: str,
) -> None:
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    provider = FakeIyzicoClient()
    service = SubscriptionService(
        repository,
        provider,
        _references(),
        "https://api.example.com/callback",
        "test-checkout-secret",
    )

    session = asyncio.run(
        service.create_checkout(
            user_id=uuid4(),
            plan_code="creator",
            interval=interval,
            customer={"name": "Ada"},
            idempotency_key=f"checkout-{interval.value}",
        )
    )

    assert provider.checkout_refs == [expected_reference]
    assert repository.status_writes == []
    assert session.token == "checkout-token"


def test_provider_query_is_the_only_source_that_updates_subscription_status() -> None:
    user_id = uuid4()
    local_subscription = LocalSubscription(
        id=uuid4(),
        user_id=user_id,
        provider_reference="sub-1",
        plan_code="creator",
        status=SubscriptionStatus.PENDING,
    )
    repository = FakeRepository(
        LocalPlan(id=uuid4(), code="creator", active=True),
        subscription=local_subscription,
    )
    service = SubscriptionService(
        repository,
        FakeIyzicoClient(),
        _references(),
        "https://api.example.com/callback",
        "test-checkout-secret",
    )

    status = asyncio.run(service.get_status(user_id))

    assert status.status is SubscriptionStatus.ACTIVE
    assert repository.status_writes == [SubscriptionStatus.ACTIVE]


def test_cancel_is_confirmed_by_provider_query_before_local_status_changes() -> None:
    user_id = uuid4()
    repository = FakeRepository(
        LocalPlan(id=uuid4(), code="creator", active=True),
        subscription=LocalSubscription(
            id=uuid4(),
            user_id=user_id,
            provider_reference="sub-1",
            plan_code="creator",
            status=SubscriptionStatus.ACTIVE,
        ),
    )
    service = SubscriptionService(
        repository,
        FakeIyzicoClient(),
        _references(),
        "https://api.example.com/callback",
        "test-checkout-secret",
    )

    status = asyncio.run(service.cancel(user_id))

    assert status.status is SubscriptionStatus.CANCELLED
    assert repository.status_writes == [SubscriptionStatus.CANCELLED]


def test_provider_checkout_result_uses_durable_token_owner_without_conversation_echo() -> None:
    user_id = uuid4()
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    provider = FakeIyzicoClient()
    service = SubscriptionService(
        repository,
        provider,
        _references(),
        "https://api.example.com/callback",
        "test-checkout-secret",
    )
    asyncio.run(service.create_checkout(
        user_id=user_id, plan_code="creator", interval=BillingInterval.MONTHLY,
        customer={"name": "Ada"}, idempotency_key="checkout-1",
    ))
    provider.subscription = ProviderSubscription(
        reference_code="sub-1",
        product_reference_code="product-creator",
        pricing_plan_reference_code="creator-monthly",
        status="ACTIVE",
    )

    snapshot = asyncio.run(service.confirm_checkout("checkout-token"))

    assert snapshot.status is SubscriptionStatus.ACTIVE
    assert repository.created_subscriptions == [repository.subscription]
    assert repository.subscription is not None
    assert repository.subscription.user_id == user_id
    assert repository.subscription.provider_reference == "sub-1"


def test_unknown_callback_token_never_queries_provider() -> None:
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    provider = FakeIyzicoClient()
    service = SubscriptionService(repository, provider, _references(), "https://api.example.com/callback", "test-checkout-secret")

    with pytest.raises(SubscriptionServiceError, match="checkout bulunamadi"):
        asyncio.run(service.confirm_checkout("unknown"))
    assert provider.retrieve_calls == 0


def test_callback_replay_does_not_query_provider_or_create_twice() -> None:
    user_id = uuid4()
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    provider = FakeIyzicoClient()
    service = SubscriptionService(repository, provider, _references(), "https://api.example.com/callback", "test-checkout-secret")
    asyncio.run(service.create_checkout(
        user_id=user_id, plan_code="creator", interval=BillingInterval.MONTHLY,
        customer={"name": "Ada"}, idempotency_key="checkout-replay",
    ))

    first = asyncio.run(service.confirm_checkout("checkout-token"))
    second = asyncio.run(service.confirm_checkout("checkout-token"))

    assert first == second
    assert provider.retrieve_calls == 1
    assert len(repository.created_subscriptions) == 1


def test_existing_active_subscription_blocks_new_checkout() -> None:
    user_id = uuid4()
    repository = FakeRepository(
        LocalPlan(id=uuid4(), code="creator", active=True),
        subscription=LocalSubscription(
            id=uuid4(), user_id=user_id, provider_reference="sub-1",
            plan_code="creator", status=SubscriptionStatus.ACTIVE,
        ),
    )
    service = SubscriptionService(repository, FakeIyzicoClient(), _references(), "https://api.example.com/callback", "test-checkout-secret")
    with pytest.raises(SubscriptionServiceError, match="devam eden aboneligi"):
        asyncio.run(service.create_checkout(
            user_id=user_id, plan_code="creator", interval=BillingInterval.MONTHLY,
            customer={"name": "Ada"}, idempotency_key="checkout-active",
        ))


def test_same_idempotency_key_returns_same_hosted_checkout_without_provider_retry() -> None:
    user_id = uuid4()
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    provider = FakeIyzicoClient()
    service = SubscriptionService(
        repository, provider, _references(), "https://api.example.com/callback",
        "test-checkout-secret",
    )
    request = dict(
        user_id=user_id,
        plan_code="creator",
        interval=BillingInterval.MONTHLY,
        customer={"name": "Ada"},
        idempotency_key="checkout-same-key",
    )

    first = asyncio.run(service.create_checkout(**request))
    second = asyncio.run(service.create_checkout(**request))

    assert second == first
    assert provider.checkout_refs == ["creator-monthly"]


def test_same_idempotency_key_rejects_different_checkout_payload() -> None:
    user_id = uuid4()
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    service = SubscriptionService(
        repository, FakeIyzicoClient(), _references(),
        "https://api.example.com/callback", "test-checkout-secret",
    )
    asyncio.run(service.create_checkout(
        user_id=user_id, plan_code="creator", interval=BillingInterval.MONTHLY,
        customer={"name": "Ada"}, idempotency_key="checkout-same-key",
    ))

    with pytest.raises(SubscriptionServiceError, match="payload ile eslesmiyor"):
        asyncio.run(service.create_checkout(
            user_id=user_id, plan_code="creator", interval=BillingInterval.YEARLY,
            customer={"name": "Ada"}, idempotency_key="checkout-same-key",
        ))


def test_callback_rejects_wrong_provider_product_before_mutation() -> None:
    user_id = uuid4()
    repository = FakeRepository(LocalPlan(id=uuid4(), code="creator", active=True))
    provider = FakeIyzicoClient()
    service = SubscriptionService(repository, provider, _references(), "https://api.example.com/callback", "test-checkout-secret")
    asyncio.run(service.create_checkout(
        user_id=user_id, plan_code="creator", interval=BillingInterval.MONTHLY,
        customer={"name": "Ada"}, idempotency_key="checkout-wrong-product",
    ))
    provider.subscription = ProviderSubscription(
        reference_code="sub-1", product_reference_code="wrong-product",
        pricing_plan_reference_code="creator-monthly", status="ACTIVE",
    )
    with pytest.raises(SubscriptionServiceError, match="product eslesmesi"):
        asyncio.run(service.confirm_checkout("checkout-token"))
    assert repository.created_subscriptions == []


def test_plan_mapping_rejects_duplicate_pricing_references() -> None:
    with pytest.raises(SubscriptionServiceError, match="benzersiz"):
        PlanReferenceMap.from_json(
            '{"creator":{"product_reference_code":"p1","monthly":"same","yearly":"y1"},'
            '"pro":{"product_reference_code":"p2","monthly":"same","yearly":"y2"}}'
        )


def test_past_due_entitlement_is_available_only_inside_grace_window() -> None:
    now = datetime(2026, 8, 21, tzinfo=timezone.utc)

    assert paid_entitlement_is_active(
        SubscriptionStatus.PAST_DUE,
        grace_until=now + timedelta(days=1),
        now=now,
    )
    assert not paid_entitlement_is_active(
        SubscriptionStatus.PAST_DUE,
        grace_until=now,
        now=now,
    )
    assert paid_entitlement_is_active(
        SubscriptionStatus.ACTIVE,
        grace_until=None,
        now=now,
    )


def test_subscription_snapshot_exposes_grace_entitlement_to_production_callers() -> None:
    user_id = uuid4()
    repository = FakeRepository(
        LocalPlan(id=uuid4(), code="creator", active=True),
        subscription=LocalSubscription(
            id=uuid4(),
            user_id=user_id,
            provider_reference="sub-1",
            plan_code="creator",
            status=SubscriptionStatus.PAST_DUE,
            grace_until=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )
    provider = FakeIyzicoClient()
    provider.subscription = ProviderSubscription(
        reference_code="sub-1",
        product_reference_code="product-creator",
        pricing_plan_reference_code="creator-monthly",
        status="ACTIVE",
    )
    service = SubscriptionService(
        repository,
        provider,
        _references(),
        "https://api.example.com/callback",
        "test-checkout-secret",
    )

    snapshot = asyncio.run(service.get_status(user_id))

    assert snapshot.status is SubscriptionStatus.PAST_DUE
    assert snapshot.grace_until == repository.subscription.grace_until
    assert snapshot.entitlement_active is True
    assert repository.status_writes == []


def test_sql_repository_checkout_replay_is_idempotent_and_cannot_rebind_owner() -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for subscription integration test")

    async def scenario() -> None:
        factory = create_session_factory(database_url)
        engine = factory.kw["bind"]
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        owner_id = uuid4()
        other_user_id = uuid4()
        plan_id = uuid4()
        suffix = uuid4().hex
        async with factory() as session:
            session.add_all(
                [
                    User(id=owner_id, clerk_subject=f"owner-{suffix}"),
                    User(id=other_user_id, clerk_subject=f"other-{suffix}"),
                    Plan(
                        id=plan_id,
                        code=f"creator-{suffix}",
                        name="Creator",
                        monthly_price_minor=9900,
                        currency="TRY",
                        monthly_compute_credits=1000,
                        max_source_minutes_per_job=60,
                        max_clips_per_job=10,
                        max_active_jobs=2,
                        retention_days=30,
                        priority=0,
                        active=True,
                    ),
                ]
            )
            await session.commit()
            repository = SqlAlchemySubscriptionRepository(session)
            subscription = LocalSubscription(
                id=uuid4(),
                user_id=owner_id,
                provider_reference=f"sub-{suffix}",
                plan_code=f"creator-{suffix}",
                status=SubscriptionStatus.ACTIVE,
                plan_id=plan_id,
            )
            await repository.upsert_subscription(subscription)
            await repository.upsert_subscription(subscription)

            count = await session.scalar(
                select(func.count()).select_from(Subscription).where(
                    Subscription.provider_subscription_ref == subscription.provider_reference
                )
            )
            assert count == 1

            with pytest.raises(SubscriptionServiceError):
                await repository.upsert_subscription(
                    LocalSubscription(
                        id=uuid4(),
                        user_id=other_user_id,
                        provider_reference=subscription.provider_reference,
                        plan_code=subscription.plan_code,
                        status=SubscriptionStatus.ACTIVE,
                        plan_id=plan_id,
                    )
                )

        await engine.dispose()

    asyncio.run(scenario())


def test_sql_repository_serializes_concurrent_checkout_reservations_per_user() -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for checkout concurrency test")

    async def scenario() -> None:
        factory = create_session_factory(database_url)
        engine = factory.kw["bind"]
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        user_id = uuid4()
        plan_id = uuid4()
        suffix = uuid4().hex
        async with factory() as session:
            session.add_all([
                User(id=user_id, clerk_subject=f"checkout-owner-{suffix}"),
                Plan(
                    id=plan_id, code=f"checkout-plan-{suffix}", name="Creator",
                    monthly_price_minor=9900, currency="TRY",
                    monthly_compute_credits=1000, max_source_minutes_per_job=60,
                    max_clips_per_job=10, max_active_jobs=2, retention_days=30,
                    priority=0, active=True,
                ),
            ])
            await session.commit()

        async def reserve(key: str) -> str:
            async with factory() as session:
                repository = SqlAlchemySubscriptionRepository(session)
                try:
                    await repository.reserve_checkout(
                        user_id=user_id,
                        plan_id=plan_id,
                        plan_code=f"checkout-plan-{suffix}",
                        interval=BillingInterval.MONTHLY,
                        idempotency_key_hash=key * 64,
                        request_fingerprint=key * 64,
                        cooldown_seconds=30,
                    )
                    return "created"
                except SubscriptionServiceError:
                    await session.rollback()
                    return "blocked"

        results = await asyncio.gather(reserve("a"), reserve("b"))
        assert sorted(results) == ["blocked", "created"]
        await engine.dispose()

    asyncio.run(scenario())
