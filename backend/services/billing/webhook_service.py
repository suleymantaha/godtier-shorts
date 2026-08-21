from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    WebhookEvent,
)
from backend.services.billing.ledger import grant_in_session
from backend.services.billing.iyzico_client import IyzicoClient
from backend.services.billing.subscription_service import (
    PROVIDER_STATUS_MAP,
    PlanReferenceMap,
    SubscriptionServiceError,
)


class WebhookError(RuntimeError):
    pass


class WebhookPayloadError(WebhookError):
    pass


class WebhookSignatureError(WebhookError):
    pass


class WebhookConflictError(WebhookError):
    pass


def reconcile_payment_record(
    payment: Payment,
    *,
    user_id: UUID,
    status: PaymentStatus,
    event_type: str,
    event_reference: str,
    payload_hash: str,
    amount_minor: int,
    currency: str,
) -> None:
    if (
        payment.user_id != user_id
        or payment.amount_minor != amount_minor
        or payment.currency != currency
    ):
        raise WebhookConflictError("provider payment sahipligi conflict")
    if payment.status is status:
        return
    if not (
        payment.status is PaymentStatus.FAILED
        and status is PaymentStatus.SUCCEEDED
    ):
        raise WebhookConflictError("provider payment durum gecisi gecersiz")
    payment.status = status
    payment.event_type = event_type
    payment.provider_conversation_id = event_reference
    payment.raw_event_hash = payload_hash


@dataclass(frozen=True, slots=True)
class WebhookNotification:
    merchant_id: str
    event_type: str
    subscription_reference: str
    order_reference: str
    customer_reference: str
    event_reference: str
    event_time: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> WebhookNotification:
        try:
            event_time = int(payload["iyziEventTime"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WebhookPayloadError("iyzico webhook event time gecersiz") from exc
        values = {
            "merchant_id": str(payload.get("merchantId") or "").strip(),
            "event_type": str(payload.get("iyziEventType") or "").strip(),
            "subscription_reference": str(
                payload.get("subscriptionReferenceCode") or ""
            ).strip(),
            "order_reference": str(payload.get("orderReferenceCode") or "").strip(),
            "customer_reference": str(payload.get("customerReferenceCode") or "").strip(),
            "event_reference": str(payload.get("iyziReferenceCode") or "").strip(),
        }
        if not all(values.values()):
            raise WebhookPayloadError("iyzico webhook payload eksik")
        if values["event_type"] not in {
            "subscription.order.success",
            "subscription.order.failure",
        }:
            raise WebhookPayloadError("iyzico webhook event type desteklenmiyor")
        return cls(**values, event_time=event_time)

    def signature_message(self, secret_key: str) -> bytes:
        return (
            self.merchant_id
            + secret_key
            + self.event_type
            + self.subscription_reference
            + self.order_reference
            + self.customer_reference
        ).encode("utf-8")


class IyzicoWebhookVerifier:
    def __init__(self, merchant_id: str, secret_key: str) -> None:
        self._merchant_id = merchant_id.strip()
        self._secret_key = secret_key.strip()
        if not self._merchant_id or not self._secret_key:
            raise ValueError("iyzico webhook verifier configuration eksik")

    def verify(self, notification: WebhookNotification, signature: str) -> bool:
        if notification.merchant_id != self._merchant_id:
            return False
        expected = hmac.new(
            self._secret_key.encode(),
            notification.signature_message(self._secret_key),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip().lower())


@dataclass(frozen=True, slots=True)
class WebhookSubscription:
    id: UUID
    user_id: UUID
    provider_reference: str
    plan_code: str
    plan_id: UUID
    monthly_compute_credits: int
    monthly_price_minor: int
    currency: str


class WebhookRepository(Protocol):
    async def claim_event(self, event_key: str, payload_hash: str) -> bool: ...

    async def get_subscription(
        self, provider_reference: str
    ) -> WebhookSubscription | None: ...

    async def apply_event(self, **kwargs: Any) -> bool: ...


class SqlAlchemyWebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_event(self, event_key: str, payload_hash: str) -> bool:
        inserted = await self._session.scalar(
            insert(WebhookEvent)
            .values(
                provider="iyzico",
                provider_event_key=event_key,
                signature_valid=True,
                payload_hash=payload_hash,
            )
            .on_conflict_do_nothing(
                index_elements=[WebhookEvent.provider, WebhookEvent.provider_event_key]
            )
            .returning(WebhookEvent.id)
        )
        await self._session.commit()
        if inserted is not None:
            return True
        existing = await self._session.scalar(
            select(WebhookEvent).where(
                WebhookEvent.provider == "iyzico",
                WebhookEvent.provider_event_key == event_key,
            )
        )
        if existing is None:
            raise WebhookError("webhook event kaydi okunamadi")
        if existing.payload_hash != payload_hash or not existing.signature_valid:
            raise WebhookConflictError("webhook event payload conflict")
        should_process = existing.processed_at is None
        await self._session.commit()
        return should_process

    async def get_subscription(
        self, provider_reference: str
    ) -> WebhookSubscription | None:
        row = (
            await self._session.execute(
                select(Subscription, Plan)
                .join(Plan, Plan.id == Subscription.plan_id)
                .where(
                    Subscription.provider == "iyzico",
                    Subscription.provider_subscription_ref == provider_reference,
                )
            )
        ).first()
        await self._session.commit()
        if row is None:
            return None
        subscription, plan = row
        return WebhookSubscription(
            id=subscription.id,
            user_id=subscription.user_id,
            provider_reference=subscription.provider_subscription_ref,
            plan_code=plan.code,
            plan_id=plan.id,
            monthly_compute_credits=plan.monthly_compute_credits,
            monthly_price_minor=plan.monthly_price_minor,
            currency=plan.currency,
        )

    async def apply_event(
        self,
        *,
        event_key: str,
        payload_hash: str,
        notification: WebhookNotification,
        subscription: WebhookSubscription,
        status: SubscriptionStatus,
        grace_until: datetime | None,
        grant_credits: int,
        payment_amount_minor: int,
        payment_currency: str,
    ) -> bool:
        async with self._session.begin():
            event = await self._session.scalar(
                select(WebhookEvent)
                .where(
                    WebhookEvent.provider == "iyzico",
                    WebhookEvent.provider_event_key == event_key,
                )
                .with_for_update()
            )
            if event is None or event.payload_hash != payload_hash:
                raise WebhookConflictError("webhook event claim gecersiz")
            if event.processed_at is not None:
                return False

            local = await self._session.scalar(
                select(Subscription)
                .where(
                    Subscription.id == subscription.id,
                    Subscription.user_id == subscription.user_id,
                    Subscription.provider_subscription_ref
                    == subscription.provider_reference,
                )
                .with_for_update()
            )
            if local is None:
                raise WebhookError("webhook subscription sahipligi gecersiz")

            payment_status = (
                PaymentStatus.SUCCEEDED
                if notification.event_type == "subscription.order.success"
                else PaymentStatus.FAILED
            )
            payment = await self._session.scalar(
                select(Payment)
                .where(Payment.provider_payment_id == notification.order_reference)
                .with_for_update()
            )
            if payment is None:
                payment = Payment(
                    user_id=subscription.user_id,
                    provider_payment_id=notification.order_reference,
                    provider_conversation_id=notification.event_reference,
                    amount_minor=payment_amount_minor,
                    currency=payment_currency,
                    status=payment_status,
                    event_type=notification.event_type,
                    raw_event_hash=payload_hash,
                )
                self._session.add(payment)
            else:
                reconcile_payment_record(
                    payment,
                    user_id=subscription.user_id,
                    status=payment_status,
                    event_type=notification.event_type,
                    event_reference=notification.event_reference,
                    payload_hash=payload_hash,
                    amount_minor=payment_amount_minor,
                    currency=payment_currency,
                )

            local.status = status
            local.entitlement_grace_until = grace_until
            if grant_credits:
                await grant_in_session(
                    self._session,
                    subscription.user_id,
                    grant_credits,
                    f"grant:iyzico:{notification.order_reference}",
                    {
                        "provider": "iyzico",
                        "subscription_reference": subscription.provider_reference,
                        "order_reference": notification.order_reference,
                    },
                )
            event.processed_at = datetime.now(timezone.utc)
        return True


@dataclass(frozen=True, slots=True)
class WebhookResult:
    processed: bool


class IyzicoWebhookService:
    def __init__(
        self,
        *,
        repository: WebhookRepository,
        provider: IyzicoClient,
        merchant_id: str,
        secret_key: str,
        plan_references_json: str,
        grace_days: int,
    ) -> None:
        if grace_days <= 0:
            raise ValueError("billing grace days pozitif olmali")
        self._repository = repository
        self._provider = provider
        self._verifier = IyzicoWebhookVerifier(merchant_id, secret_key)
        self._plan_references = PlanReferenceMap.from_json(plan_references_json)
        self._grace_days = grace_days

    async def handle(
        self, payload: Mapping[str, Any], signature: str
    ) -> WebhookResult:
        notification = WebhookNotification.from_mapping(payload)
        if not self._verifier.verify(notification, signature):
            raise WebhookSignatureError("iyzico webhook imzasi gecersiz")

        try:
            canonical_payload = json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise WebhookPayloadError("iyzico webhook payload JSON olmali") from exc
        payload_hash = hashlib.sha256(canonical_payload.encode()).hexdigest()
        should_process = await self._repository.claim_event(
            notification.event_reference, payload_hash
        )
        if not should_process:
            return WebhookResult(processed=False)

        local = await self._repository.get_subscription(
            notification.subscription_reference
        )
        if local is None:
            raise WebhookError("webhook subscription bulunamadi")
        provider = await self._provider.get_subscription(
            notification.subscription_reference
        )
        if provider.reference_code != local.provider_reference:
            raise WebhookError("provider subscription eslesmesi gecersiz")
        provider_order = provider.orders.get(notification.order_reference)
        if (
            provider.customer_reference_code != notification.customer_reference
            or provider_order is None
        ):
            raise WebhookError("provider webhook eslesmesi gecersiz")
        if provider_order.currency != local.currency:
            raise WebhookError("provider payment currency eslesmesi gecersiz")
        self._plan_references.verify_provider_references(
            local.plan_code,
            provider.product_reference_code,
            provider.pricing_plan_reference_code,
        )

        is_success = notification.event_type == "subscription.order.success"
        if is_success:
            if (
                provider_order.order_status != "SUCCESS"
                or "SUCCESS" not in provider_order.payment_statuses
            ):
                raise WebhookError("provider payment order durumu gecersiz")
            try:
                status = PROVIDER_STATUS_MAP[provider.status]
            except KeyError as exc:
                raise SubscriptionServiceError(
                    "provider subscription status gecersiz"
                ) from exc
            if status is not SubscriptionStatus.ACTIVE:
                raise WebhookError("basarili odeme aktif subscription ile dogrulanamadi")
            grace_until = None
            grant_credits = local.monthly_compute_credits
        else:
            if (
                provider_order.order_status == "SUCCESS"
                or "FAILED" not in provider_order.payment_statuses
                or "SUCCESS" in provider_order.payment_statuses
            ):
                raise WebhookError("provider payment order durumu gecersiz")
            status = SubscriptionStatus.PAST_DUE
            grace_until = datetime.now(timezone.utc) + timedelta(days=self._grace_days)
            grant_credits = 0

        processed = await self._repository.apply_event(
            event_key=notification.event_reference,
            payload_hash=payload_hash,
            notification=notification,
            subscription=local,
            status=status,
            grace_until=grace_until,
            grant_credits=grant_credits,
            payment_amount_minor=provider_order.amount_minor,
            payment_currency=provider_order.currency,
        )
        return WebhookResult(processed=processed)
