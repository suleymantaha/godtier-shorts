from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from dataclasses import dataclass
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
        self.apply_count += 1
        self.status = kwargs["status"]
        self.payment_amount_minor = kwargs["payment_amount_minor"]
        self.payment_currency = kwargs["payment_currency"]
        if kwargs["grant_credits"]:
            self.granted_credits += kwargs["grant_credits"]
        self.processed = True
        return True


class FakeProvider:
    def __init__(
        self,
        *,
        customer_reference: str = "customer-1",
        order_references: frozenset[str] = frozenset({"order-1", "order-2"}),
        order_amount_minor: int = 9900,
        success_order_status: str = "SUCCESS",
        failure_order_status: str = "WAITING",
        failure_payment_statuses: tuple[str, ...] = ("FAILED",),
    ) -> None:
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
            status="ACTIVE",
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


def test_same_event_reference_with_changed_payload_is_rejected() -> None:
    repository = FakeWebhookRepository()
    service = _service(repository)
    asyncio.run(service.handle(SUCCESS_PAYLOAD, VALID_SIGNATURE))

    with pytest.raises(WebhookConflictError):
        asyncio.run(
            service.handle(
                {**SUCCESS_PAYLOAD, "unexpected": "changed"},
                VALID_SIGNATURE,
            )
        )

    assert repository.apply_count == 1


def test_failed_recurring_payment_marks_past_due_without_credit_grant() -> None:
    payload = {
        **SUCCESS_PAYLOAD,
        "iyziEventType": "subscription.order.failure",
        "orderReferenceCode": "order-2",
        "iyziReferenceCode": "event-2",
    }
    repository = FakeWebhookRepository()
    service = _service(repository)

    asyncio.run(
        service.handle(
            payload,
            "8cbf42d127d7137bebe7de8dd30fab3fdc57d77e698caeab2bb0da12912fb423",
        )
    )

    assert repository.status is SubscriptionStatus.PAST_DUE
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
            subscription = Subscription(
                id=uuid4(), user_id=user.id, provider_subscription_ref="sub-1",
                plan_id=plan.id, status=SubscriptionStatus.PENDING,
            )
            session.add_all([user, plan, subscription])
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
            await service.handle(
                failure_payload,
                "8cbf42d127d7137bebe7de8dd30fab3fdc57d77e698caeab2bb0da12912fb423",
            )
            await session.refresh(subscription)
            assert subscription.status is SubscriptionStatus.PAST_DUE
            assert subscription.entitlement_grace_until is not None
            assert wallet.available == 100
            assert await session.scalar(select(func.count()).select_from(Payment)) == 2

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
