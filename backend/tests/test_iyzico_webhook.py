from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from sqlalchemy import func, select, text

from backend.db.models import (
    CreditLedgerEntry,
    CreditWallet,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    User,
    WebhookEvent,
)
from backend.db.session import create_session_factory
from backend.services.billing.iyzico_client import ProviderOrder, ProviderSubscription
from backend.services.billing.webhook_service import (
    IyzicoWebhookVerifier,
    WebhookNotification,
    WebhookConflictError,
    WebhookSignatureError,
    WebhookSubscription,
    WebhookUpdate,
    IyzicoWebhookService,
    SqlAlchemyWebhookRepository,
    reconcile_payment_record,
)


SUCCESS_PAYLOAD = {
    "merchantId": 3404590,
    "iyziEventType": "subscription.order.success",
    "subscriptionReferenceCode": "sub-1",
    "orderReferenceCode": "order-1",
    "customerReferenceCode": "customer-1",
    "iyziReferenceCode": "event-1",
    "iyziEventTime": 1758704403161,
}
VALID_SIGNATURE = "6a8bd40dbc2a6756a6ae2da327391e4a31903151408229ab756c05e5e4bac179"


def _signature(payload: dict[str, object]) -> str:
    message = (
        str(payload["merchantId"])
        + "secret-key"
        + str(payload["iyziEventType"])
        + str(payload["subscriptionReferenceCode"])
        + str(payload["orderReferenceCode"])
        + str(payload["customerReferenceCode"])
    )
    return hmac.new(b"secret-key", message.encode(), hashlib.sha256).hexdigest()


def test_subscription_v3_signature_matches_official_field_order() -> None:
    verifier = IyzicoWebhookVerifier("3404590", "secret-key")

    assert verifier.verify(WebhookNotification.from_mapping(SUCCESS_PAYLOAD), VALID_SIGNATURE)


def test_invalid_v3_signature_is_rejected_before_repository_mutation() -> None:
    repository = FakeWebhookRepository()
    service = _service(repository)

    with pytest.raises(WebhookSignatureError):
        asyncio.run(service.handle(SUCCESS_PAYLOAD, "0" * 64))

    assert repository.claim_count == 0
    assert repository.apply_count == 0


@dataclass
class FakeWebhookRepository:
    subscription: WebhookSubscription | None = None
    claimed_hash: str | None = None
    processed: bool = False
    claim_count: int = 0
    apply_count: int = 0
    granted_credits: int = 0
    status: SubscriptionStatus | None = None
    payment_amount_minor: int | None = None
    payment_currency: str | None = None
    grace_until: datetime | None = None
    event_key: str | None = None

    def __post_init__(self) -> None:
        if self.subscription is None:
            self.subscription = WebhookSubscription(
                id=uuid4(),
                user_id=uuid4(),
                provider_reference="sub-1",
                plan_code="creator",
                plan_id=uuid4(),
                monthly_compute_credits=100,
                monthly_price_minor=9900,
                currency="TRY",
            )

    async def claim_event(self, event_key: str, payload_hash: str) -> bool:
        self.claim_count += 1
        self.event_key = event_key
        if self.claimed_hash is None:
            self.claimed_hash = payload_hash
            return True
        if self.claimed_hash != payload_hash:
            raise WebhookConflictError("payload conflict")
        return not self.processed

    async def get_subscription(self, provider_reference: str) -> WebhookSubscription | None:
        assert self.subscription is not None
        return self.subscription if provider_reference == self.subscription.provider_reference else None

    async def apply_event(self, **kwargs) -> bool:
        if self.processed:
            return False
        update = await kwargs["resolve_update"]()
        self.apply_count += 1
        self.status = update.status
        self.grace_until = update.grace_until
        self.payment_amount_minor = update.payment_amount_minor
        self.payment_currency = update.payment_currency
        if update.grant_credits:
            self.granted_credits += update.grant_credits
        self.processed = True
        return True


class FakeProvider:
    def __init__(
        self,
        *,
        status: str = "ACTIVE",
        customer_reference: str = "customer-1",
        order_references: frozenset[str] = frozenset({"order-1", "order-2"}),
        order_amount_minor: int = 9900,
        success_order_status: str = "SUCCESS",
        failure_order_status: str = "WAITING",
        failure_payment_statuses: tuple[str, ...] = ("FAILED",),
    ) -> None:
        self.status = status
        self.customer_reference = customer_reference
        self.order_references = order_references
        self.order_amount_minor = order_amount_minor
        self.success_order_status = success_order_status
        self.failure_order_status = failure_order_status
        self.failure_payment_statuses = failure_payment_statuses

    async def get_subscription(self, reference_code: str) -> ProviderSubscription:
        assert reference_code == "sub-1"
        return ProviderSubscription(
            reference_code="sub-1",
            pricing_plan_reference_code="creator-monthly",
            status=self.status,
            product_reference_code="product-creator",
            customer_reference_code=self.customer_reference,
            order_references=self.order_references,
            orders={
                reference: ProviderOrder(
                    reference,
                    self.order_amount_minor,
                    "TRY",
                    self.success_order_status
                    if reference == "order-1"
                    else self.failure_order_status,
                    ("SUCCESS",)
                    if reference == "order-1"
                    else self.failure_payment_statuses,
                )
                for reference in self.order_references
            },
        )


def _service(
    repository: FakeWebhookRepository,
    provider: FakeProvider | None = None,
) -> IyzicoWebhookService:
    return IyzicoWebhookService(
        repository=repository,
        provider=provider or FakeProvider(),
        merchant_id="3404590",
        secret_key="secret-key",
        plan_references_json=(
            '{"creator":{"product_reference_code":"product-creator",'
            '"monthly":"creator-monthly","yearly":"creator-yearly"}}'
        ),
        grace_days=3,
    )


def test_same_success_webhook_five_times_grants_credits_once() -> None:
    repository = FakeWebhookRepository()
    service = _service(repository)

    for _ in range(5):
        asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))

    assert repository.apply_count == 1
    assert repository.granted_credits == 100
    assert repository.status is SubscriptionStatus.ACTIVE


def test_unsigned_extra_fields_do_not_change_processed_event_identity() -> None:
    repository = FakeWebhookRepository()
    service = _service(repository)
    asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))
    result = asyncio.run(service.handle(
        {**SUCCESS_PAYLOAD, "unsignedExtra": "changed"}, VALID_SIGNATURE,
    ))
    assert result.processed is False
    assert repository.apply_count == 1


def test_unsigned_extra_fields_cannot_poison_retry_after_provider_failure() -> None:
    class TransientProvider(FakeProvider):
        fail = True

        async def get_subscription(self, reference_code):
            if self.fail:
                self.fail = False
                raise RuntimeError("transient provider failure")
            return await super().get_subscription(reference_code)

    repository = FakeWebhookRepository()
    service = _service(repository, TransientProvider())
    with pytest.raises(RuntimeError, match="transient provider failure"):
        asyncio.run(service.handle(
            {**SUCCESS_PAYLOAD, "unsignedExtra": "attacker"}, VALID_SIGNATURE,
        ))
    result = asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))
    assert result.processed is True
    assert repository.granted_credits == 100


def test_failed_recurring_payment_marks_past_due_without_credit_grant() -> None:
    payload = {
        **SUCCESS_PAYLOAD,
        "iyziEventType": "subscription.order.failure",
        "orderReferenceCode": "order-2",
        "iyziReferenceCode": "event-2",
    }
    repository = FakeWebhookRepository()
    service = _service(repository, FakeProvider(status="UNPAID"))

    asyncio.run(
        service.handle(
            payload,
            "8cbf42d127d7137bebe7de8dd30fab3fdc57d77e698caeab2bb0da12912fb423",
        )
    )

    assert repository.status is SubscriptionStatus.PAST_DUE
    assert repository.grace_until is not None
    assert repository.grace_until > datetime.now(timezone.utc)
    assert repository.granted_credits == 0


@pytest.mark.parametrize(
    "provider",
    [
        FakeProvider(customer_reference="another-customer"),
        FakeProvider(order_references=frozenset({"another-order"})),
    ],
)
def test_provider_customer_and_order_must_match_before_financial_mutation(
    provider: FakeProvider,
) -> None:
    repository = FakeWebhookRepository()
    service = _service(repository, provider)

    with pytest.raises(Exception, match="provider webhook eslesmesi"):
        asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))

    assert repository.apply_count == 0
    assert repository.granted_credits == 0


def test_payment_uses_provider_order_amount_instead_of_local_monthly_guess() -> None:
    repository = FakeWebhookRepository()
    service = _service(repository, FakeProvider(order_amount_minor=19900))

    asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))

    assert repository.payment_amount_minor == 19900
    assert repository.payment_currency == "TRY"


def test_success_event_requires_provider_order_success_before_credit_grant() -> None:
    repository = FakeWebhookRepository()
    service = _service(repository, FakeProvider(success_order_status="WAITING"))

    with pytest.raises(Exception, match="order durumu"):
        asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))

    assert repository.granted_credits == 0
    assert repository.apply_count == 0


def test_stale_failure_is_rejected_after_provider_order_succeeds() -> None:
    payload = {
        **SUCCESS_PAYLOAD,
        "iyziEventType": "subscription.order.failure",
        "orderReferenceCode": "order-2",
        "iyziReferenceCode": "event-2",
    }
    repository = FakeWebhookRepository()
    service = _service(
        repository,
        FakeProvider(
            failure_order_status="SUCCESS",
            failure_payment_statuses=("FAILED", "SUCCESS"),
        ),
    )

    with pytest.raises(Exception, match="order durumu"):
        asyncio.run(
            service.handle(
                payload,
                "8cbf42d127d7137bebe7de8dd30fab3fdc57d77e698caeab2bb0da12912fb423",
            )
        )

    assert repository.apply_count == 0


def test_failed_payment_retry_is_promoted_to_succeeded_without_owner_rebind() -> None:
    user_id = uuid4()
    payment = Payment(
        user_id=user_id,
        provider_payment_id="order-1",
        provider_conversation_id="failure-event",
        amount_minor=9900,
        currency="TRY",
        status=PaymentStatus.FAILED,
        event_type="subscription.order.failure",
        raw_event_hash="a" * 64,
    )

    reconcile_payment_record(
        payment,
        user_id=user_id,
        status=PaymentStatus.SUCCEEDED,
        event_type="subscription.order.success",
        event_reference="success-event",
        payload_hash="b" * 64,
        amount_minor=9900,
        currency="TRY",
    )

    assert payment.status is PaymentStatus.SUCCEEDED
    assert payment.provider_conversation_id == "success-event"
    with pytest.raises(WebhookConflictError):
        reconcile_payment_record(
            payment,
            user_id=uuid4(),
            status=PaymentStatus.SUCCEEDED,
            event_type="subscription.order.success",
            event_reference="foreign-event",
            payload_hash="c" * 64,
            amount_minor=9900,
            currency="TRY",
        )
    payment.status = PaymentStatus.REFUNDED
    with pytest.raises(WebhookConflictError):
        reconcile_payment_record(
            payment,
            user_id=user_id,
            status=PaymentStatus.SUCCEEDED,
            event_type="subscription.order.success",
            event_reference="late-event",
            payload_hash="d" * 64,
            amount_minor=9900,
            currency="TRY",
        )


@pytest.mark.integration
def test_postgres_webhook_replay_grants_once_and_failure_sets_grace_window() -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for webhook integration test")

    async def scenario() -> None:
        factory = create_session_factory(database_url)
        async with factory() as session:
            await session.execute(
                text(
                    "TRUNCATE webhook_events, credit_ledger, payments, credit_wallets, "
                    "billing_checkout_sessions, subscriptions, plans, users CASCADE"
                )
            )
            user = User(id=uuid4(), clerk_subject=f"webhook-{uuid4().hex}")
            plan = Plan(
                id=uuid4(), code="creator", name="Creator",
                monthly_price_minor=9900, currency="TRY",
                monthly_compute_credits=100, max_source_minutes_per_job=60,
                max_clips_per_job=10, max_active_jobs=2, retention_days=30,
                priority=0, active=True,
            )
            session.add_all([user, plan])
            await session.commit()

            subscription = Subscription(
                id=uuid4(), user_id=user.id, provider_subscription_ref="sub-1",
                plan_id=plan.id, status=SubscriptionStatus.PENDING,
            )
            session.add(subscription)
            await session.commit()

            repository = SqlAlchemyWebhookRepository(session)
            provider = FakeProvider()
            service = _service(repository, provider)
            for _ in range(5):
                await service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE)

            wallet = await session.get(CreditWallet, user.id)
            assert wallet is not None
            assert wallet.available == 100
            assert await session.scalar(select(func.count()).select_from(CreditLedgerEntry)) == 1
            assert await session.scalar(select(func.count()).select_from(Payment)) == 1
            assert await session.scalar(select(func.count()).select_from(WebhookEvent)) == 1

            failure_payload = {
                **SUCCESS_PAYLOAD,
                "iyziEventType": "subscription.order.failure",
                "orderReferenceCode": "order-2",
                "iyziReferenceCode": "event-2",
            }
            provider.status = "UNPAID"
            await service.handle(
                failure_payload,
                "8cbf42d127d7137bebe7de8dd30fab3fdc57d77e698caeab2bb0da12912fb423",
            )
            await session.refresh(subscription)
            assert subscription.status is SubscriptionStatus.PAST_DUE
            assert subscription.entitlement_grace_until is not None
            assert wallet.available == 100
            assert await session.scalar(select(func.count()).select_from(Payment)) == 2

            provider.status = "ACTIVE"
            provider.failure_order_status = "SUCCESS"
            provider.failure_payment_statuses = ("FAILED", "SUCCESS")
            retry_success_payload = {
                **failure_payload,
                "iyziEventType": "subscription.order.success",
                "iyziReferenceCode": "event-3",
            }
            await service.handle(
                retry_success_payload,
                _signature(retry_success_payload),
            )
            await session.refresh(subscription)
            retried_payment = await session.scalar(
                select(Payment).where(Payment.provider_payment_id == "order-2")
            )
            await session.refresh(wallet)
            assert subscription.status is SubscriptionStatus.ACTIVE
            assert subscription.entitlement_grace_until is None
            assert retried_payment is not None
            assert retried_payment.status is PaymentStatus.SUCCEEDED
            assert wallet.available == 200
        await factory.kw["bind"].dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("event_type, order", [
    ("subscription.order.success", "order-1"),
    ("subscription.order.failure", "order-2"),
])
def test_unsigned_delivery_metadata_cannot_bypass_order_deduplication(
    event_type: str, order: str,
) -> None:
    payload = {**SUCCESS_PAYLOAD, "iyziEventType": event_type, "orderReferenceCode": order}
    repository = FakeWebhookRepository()
    service = _service(
        repository, FakeProvider(status="UNPAID" if order == "order-2" else "ACTIVE"),
    )
    first = asyncio.run(service.handle(payload, _signature(payload)))
    original_key = repository.event_key
    original_grace = repository.grace_until
    replay = {**payload, "iyziReferenceCode": "attacker-changed", "iyziEventTime": 9999999999999}
    result = asyncio.run(service.handle(replay, _signature(payload)))
    assert first.processed is True
    assert result.processed is False
    assert repository.event_key == original_key
    assert repository.apply_count == 1
    assert repository.grace_until == original_grace


@pytest.mark.parametrize("provider_status, expected", [
    ("CANCELED", SubscriptionStatus.CANCELLED),
    ("CANCELLED", SubscriptionStatus.CANCELLED),
    ("EXPIRED", SubscriptionStatus.EXPIRED),
    ("PENDING", SubscriptionStatus.PENDING),
    ("ACTIVE", SubscriptionStatus.ACTIVE),
])
def test_old_failed_order_uses_current_provider_status_without_grace(
    provider_status: str, expected: SubscriptionStatus,
) -> None:
    payload = {
        **SUCCESS_PAYLOAD,
        "iyziEventType": "subscription.order.failure",
        "orderReferenceCode": "order-2",
    }
    repository = FakeWebhookRepository()
    service = _service(repository, FakeProvider(status=provider_status))
    asyncio.run(service.handle(payload, _signature(payload)))
    assert repository.status is expected
    assert repository.grace_until is None
    assert repository.granted_credits == 0


@pytest.mark.parametrize("local_status, payment_exists", [
    (SubscriptionStatus.ACTIVE, True),
    (SubscriptionStatus.PAST_DUE, True),
    (SubscriptionStatus.CANCELLED, False),
    (SubscriptionStatus.EXPIRED, False),
    (SubscriptionStatus.PAST_DUE, False),
])
def test_repository_old_failure_never_reopens_terminal_state_or_renews_grace(
    local_status: SubscriptionStatus, payment_exists: bool,
) -> None:
    snapshot = FakeWebhookRepository().subscription
    assert snapshot is not None
    old_grace = (
        datetime.now(timezone.utc) - timedelta(days=1)
        if local_status is SubscriptionStatus.PAST_DUE else None
    )
    local = Subscription(
        id=snapshot.id, user_id=snapshot.user_id,
        provider_subscription_ref="sub-1", plan_id=snapshot.plan_id,
        status=local_status, entitlement_grace_until=old_grace,
    )
    event = WebhookEvent(
        provider="iyzico", provider_event_key="canonical-event",
        payload_hash="a" * 64, signature_valid=True,
    )
    payment = Payment(
        user_id=snapshot.user_id, provider_payment_id="order-2",
        amount_minor=9900, currency="TRY", status=PaymentStatus.FAILED,
    ) if payment_exists else None

    class Session:
        def __init__(self):
            self.rows = iter([event, local, payment])

        @asynccontextmanager
        async def begin(self):
            yield

        async def scalar(self, query):
            return next(self.rows)

        def add(self, row):
            pass

    payload = {
        **SUCCESS_PAYLOAD,
        "iyziEventType": "subscription.order.failure",
        "orderReferenceCode": "order-2",
    }
    async def resolve_update():
        return WebhookUpdate(
            status=SubscriptionStatus.PAST_DUE,
            grace_until=datetime.now(timezone.utc) + timedelta(days=3),
            grant_credits=0, payment_amount_minor=9900, payment_currency="TRY",
        )

    asyncio.run(SqlAlchemyWebhookRepository(Session()).apply_event(
        event_key="canonical-event", payload_hash="a" * 64,
        notification=WebhookNotification.from_mapping(payload), subscription=snapshot,
        resolve_update=resolve_update,
    ))
    assert local.status is local_status
    assert local.entitlement_grace_until == old_grace
    assert event.processed_at is not None


@pytest.mark.integration
def test_postgres_different_orders_revalidate_provider_under_subscription_lock() -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for webhook concurrency test")

    async def scenario() -> None:
        factory = create_session_factory(database_url)
        engine = factory.kw["bind"]
        suffix = uuid4().hex
        reference = f"race-sub-{suffix}"
        failure_order, success_order = f"failure-{suffix}", f"success-{suffix}"
        paused, resume = asyncio.Event(), asyncio.Event()

        class CurrentProvider(FakeProvider):
            async def get_subscription(self, reference_code):
                assert reference_code == reference
                snapshot = await super().get_subscription("sub-1")
                return replace(snapshot, reference_code=reference, orders={
                    failure_order: snapshot.orders["order-2"],
                    success_order: snapshot.orders["order-1"],
                })

        class PausedRepository(SqlAlchemyWebhookRepository):
            async def apply_event(self, **kwargs):
                # Pause just before the transaction that acquires the row lock.
                paused.set()
                await asyncio.wait_for(resume.wait(), timeout=10)
                return await super().apply_event(**kwargs)

        provider = CurrentProvider(status="UNPAID")
        async with factory() as session:
            user = User(id=uuid4(), clerk_subject=f"webhook-race-{suffix}")
            plan = Plan(
                id=uuid4(), code=f"race-plan-{suffix}", name="Race plan",
                monthly_price_minor=9900, currency="TRY",
                monthly_compute_credits=100, max_source_minutes_per_job=60,
                max_clips_per_job=10, max_active_jobs=2, retention_days=30,
                priority=0, active=True,
            )
            session.add_all([user, plan])
            await session.flush()
            subscription = Subscription(
                id=uuid4(), user_id=user.id, provider_subscription_ref=reference,
                plan_id=plan.id, status=SubscriptionStatus.PAST_DUE,
            )
            session.add(subscription)
            await session.commit()
            subscription_id = subscription.id
            plan_code = plan.code

        def service(repository):
            return IyzicoWebhookService(
                repository=repository, provider=provider,
                merchant_id="3404590", secret_key="secret-key", grace_days=3,
                plan_references_json=(
                    '{"' + plan_code + '":{"product_reference_code":"product-creator",'
                    '"monthly":"creator-monthly","yearly":"creator-yearly"}}'
                ),
            )

        failure_payload = {
            **SUCCESS_PAYLOAD, "subscriptionReferenceCode": reference,
            "orderReferenceCode": failure_order, "iyziEventType": "subscription.order.failure",
        }
        success_payload = {
            **failure_payload, "orderReferenceCode": success_order,
            "iyziEventType": "subscription.order.success",
        }
        async with factory() as failure_session, factory() as success_session:
            failure_task = asyncio.create_task(service(PausedRepository(failure_session)).handle(
                failure_payload, _signature(failure_payload),
            ))
            try:
                await asyncio.wait_for(paused.wait(), timeout=10)
                provider.status = "ACTIVE"
                await service(SqlAlchemyWebhookRepository(success_session)).handle(
                    success_payload, _signature(success_payload),
                )
            finally:
                resume.set()
            await asyncio.wait_for(failure_task, timeout=10)

        async with factory() as session:
            current = await session.get(Subscription, subscription_id)
            assert current.status is SubscriptionStatus.ACTIVE
            assert current.entitlement_grace_until is None
            wallet = await session.get(CreditWallet, user.id)
            assert wallet.available == 100
            statuses = (await session.scalars(select(Payment.status).where(
                Payment.user_id == user.id,
            ))).all()
            assert set(statuses) == {PaymentStatus.FAILED, PaymentStatus.SUCCEEDED}
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.integration
@pytest.mark.parametrize("sync_writer", ["status", "admin"])
def test_postgres_first_failure_after_unpaid_sync_anchors_grace_once(sync_writer) -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for first failure grace test")

    async def scenario() -> None:
        from backend.services.admin_operations import AuditContext, SqlAlchemyAdminService
        from backend.services.billing.subscription_service import (
            PlanReferenceMap, SqlAlchemySubscriptionRepository, SubscriptionService,
        )
        factory = create_session_factory(database_url)
        engine = factory.kw["bind"]
        suffix = uuid4().hex
        reference = f"first-failure-{suffix}"
        orders = [f"first-order-{suffix}", f"later-order-{suffix}"]
        async with factory() as session:
            user = User(id=uuid4(), clerk_subject=f"first-failure-{suffix}")
            plan = Plan(
                id=uuid4(), code=f"first-failure-{suffix}", name="Grace test",
                monthly_price_minor=9900, currency="TRY", monthly_compute_credits=100,
                max_source_minutes_per_job=60, max_clips_per_job=10, max_active_jobs=2,
                retention_days=30, priority=0, active=True,
            )
            session.add_all([user, plan])
            await session.flush()
            local = Subscription(
                id=uuid4(), user_id=user.id, provider_subscription_ref=reference,
                plan_id=plan.id, status=SubscriptionStatus.ACTIVE,
            )
            session.add(local)
            await session.commit()
            subscription_id, user_id = local.id, user.id
            references = ('{"' + plan.code + '":{"product_reference_code":"product-creator",'
                          '"monthly":"creator-monthly","yearly":"creator-yearly"}}')

        class UnpaidProvider(FakeProvider):
            async def get_subscription(self, requested):
                assert requested == reference
                snapshot = await super().get_subscription("sub-1")
                return replace(snapshot, reference_code=reference, orders={
                    order: replace(snapshot.orders["order-2"], reference_code=order)
                    for order in orders
                })

        provider = UnpaidProvider(status="UNPAID")
        async with factory() as session:
            if sync_writer == "status":
                service = SubscriptionService(
                    SqlAlchemySubscriptionRepository(session), provider,
                    PlanReferenceMap.from_json(references), "https://api.example.com/callback",
                    "test-checkout-secret",
                )
                await service.get_status(user_id)
            else:
                await SqlAlchemyAdminService(session, provider, None).sync_subscription(
                    subscription_id, reason="Initial unpaid reconciliation",
                    audit=AuditContext(actor_id=None, request_id=f"first-failure-{suffix}"),
                )
            current = await session.get(Subscription, subscription_id)
            assert current.status is SubscriptionStatus.PAST_DUE
            assert current.entitlement_grace_until is None

        payload = {
            **SUCCESS_PAYLOAD, "subscriptionReferenceCode": reference,
            "orderReferenceCode": orders[0], "iyziEventType": "subscription.order.failure",
            "iyziEventTime": 1,
        }
        before = datetime.now(timezone.utc)
        async with factory() as session:
            service = IyzicoWebhookService(
                repository=SqlAlchemyWebhookRepository(session), provider=provider,
                merchant_id="3404590", secret_key="secret-key",
                plan_references_json=references, grace_days=3,
            )
            await service.handle(payload, _signature(payload))
            current = await session.get(Subscription, subscription_id)
            first_grace = current.entitlement_grace_until
            assert first_grace is not None
            assert before + timedelta(days=3) <= first_grace <= datetime.now(timezone.utc) + timedelta(days=3)
            await session.commit()
            replay = {**payload, "iyziReferenceCode": "changed", "iyziEventTime": 9999999999999}
            assert (await service.handle(replay, _signature(payload))).processed is False
            current = await session.get(Subscription, subscription_id)
            assert current.entitlement_grace_until == first_grace
            expired = before - timedelta(days=1)
            current.entitlement_grace_until = expired
            await session.commit()
            later = {**payload, "orderReferenceCode": orders[1]}
            await service.handle(later, _signature(later))
            await session.refresh(current)
            assert current.entitlement_grace_until == expired
        await engine.dispose()

    asyncio.run(scenario())
