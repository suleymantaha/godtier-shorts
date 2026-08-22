from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    BillingCheckoutSession,
    BillingCheckoutStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    User,
)
from backend.services.billing.iyzico_client import CheckoutSession, IyzicoClient


class SubscriptionServiceError(RuntimeError):
    pass


class BillingInterval(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass(frozen=True, slots=True)
class LocalPlan:
    id: UUID
    code: str
    active: bool


@dataclass(slots=True)
class LocalSubscription:
    id: UUID
    user_id: UUID
    provider_reference: str
    plan_code: str
    status: SubscriptionStatus
    plan_id: UUID | None = None
    grace_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class SubscriptionSnapshot:
    plan_code: str
    interval: BillingInterval
    status: SubscriptionStatus
    grace_until: datetime | None = None

    @property
    def entitlement_active(self) -> bool:
        return paid_entitlement_is_active(
            self.status,
            grace_until=self.grace_until,
        )


@dataclass(slots=True)
class CheckoutRecord:
    id: UUID
    user_id: UUID
    plan_id: UUID
    plan_code: str
    interval: BillingInterval
    idempotency_key_hash: str
    token_hash: str | None = None
    consumed: bool = False
    expires_at: datetime | None = None
    request_fingerprint: str = ""
    response_ciphertext: str | None = None


class CheckoutCipher:
    def __init__(self, secret: str) -> None:
        normalized = secret.strip()
        if not normalized:
            raise SubscriptionServiceError("checkout encryption secret eksik")
        digest = hashlib.sha256(b"godtier-billing-checkout-v1:" + normalized.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, checkout: CheckoutSession) -> str:
        payload = json.dumps(
            {
                "token": checkout.token,
                "checkout_form_content": checkout.checkout_form_content,
                "expires_in_seconds": checkout.expires_in_seconds,
            },
            separators=(",", ":"),
        )
        return self._fernet.encrypt(payload.encode()).decode()

    def decrypt(self, ciphertext: str) -> CheckoutSession:
        try:
            payload = json.loads(self._fernet.decrypt(ciphertext.encode()).decode())
            return CheckoutSession(
                token=str(payload["token"]),
                checkout_form_content=str(payload["checkout_form_content"]),
                expires_in_seconds=int(payload["expires_in_seconds"]),
            )
        except (InvalidToken, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SubscriptionServiceError("checkout response cozulemedi") from exc


@dataclass(frozen=True, slots=True)
class PlanReferences:
    product_reference_code: str
    monthly: str
    yearly: str


class PlanReferenceMap:
    def __init__(self, references: dict[str, PlanReferences]) -> None:
        self._references = references

    @classmethod
    def from_json(cls, raw: str) -> PlanReferenceMap:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SubscriptionServiceError("IYZICO_PLAN_REFERENCES_JSON gecersiz") from exc
        if not isinstance(payload, dict) or not payload:
            raise SubscriptionServiceError("iyzico plan mapping bos olamaz")
        references: dict[str, PlanReferences] = {}
        for code, value in payload.items():
            if not isinstance(code, str) or not code.strip() or not isinstance(value, dict):
                raise SubscriptionServiceError("iyzico plan mapping gecersiz")
            refs = PlanReferences(
                product_reference_code=str(value.get("product_reference_code") or "").strip(),
                monthly=str(value.get("monthly") or "").strip(),
                yearly=str(value.get("yearly") or "").strip(),
            )
            if not all((refs.product_reference_code, refs.monthly, refs.yearly)):
                raise SubscriptionServiceError("iyzico plan mapping eksik")
            references[code.strip()] = refs
        pricing_references = [
            reference
            for refs in references.values()
            for reference in (refs.monthly, refs.yearly)
        ]
        if len(pricing_references) != len(set(pricing_references)):
            raise SubscriptionServiceError("iyzico pricing reference degerleri benzersiz olmali")
        return cls(references)

    def pricing_reference(self, plan_code: str, interval: BillingInterval) -> str:
        references = self._references.get(plan_code)
        if references is None:
            raise SubscriptionServiceError("plan iyzico ile eslesmiyor")
        return references.monthly if interval is BillingInterval.MONTHLY else references.yearly

    def interval_for_reference(self, plan_code: str, pricing_reference: str) -> BillingInterval:
        references = self._references.get(plan_code)
        if references is None:
            raise SubscriptionServiceError("plan iyzico ile eslesmiyor")
        if pricing_reference == references.monthly:
            return BillingInterval.MONTHLY
        if pricing_reference == references.yearly:
            return BillingInterval.YEARLY
        raise SubscriptionServiceError("provider pricing plan eslesmesi gecersiz")

    def plan_for_reference(self, pricing_reference: str) -> tuple[str, BillingInterval]:
        for plan_code, references in self._references.items():
            if pricing_reference == references.monthly:
                return plan_code, BillingInterval.MONTHLY
            if pricing_reference == references.yearly:
                return plan_code, BillingInterval.YEARLY
        raise SubscriptionServiceError("provider pricing plan eslesmesi gecersiz")

    def verify_provider_references(
        self, plan_code: str, product_reference: str, pricing_reference: str
    ) -> BillingInterval:
        references = self._references.get(plan_code)
        if references is None or product_reference != references.product_reference_code:
            raise SubscriptionServiceError("provider product eslesmesi gecersiz")
        return self.interval_for_reference(plan_code, pricing_reference)


class SubscriptionRepository(Protocol):
    async def get_plan(self, code: str) -> LocalPlan | None: ...

    async def get_subscription(self, user_id: UUID) -> LocalSubscription | None: ...

    async def set_status(self, subscription_id: UUID, status: SubscriptionStatus) -> None: ...

    async def change_plan(self, subscription_id: UUID, subscription: LocalSubscription) -> None: ...

    async def upsert_subscription(self, subscription: LocalSubscription) -> None: ...

    async def reserve_checkout(self, **kwargs: Any) -> CheckoutRecord: ...

    async def attach_checkout_token(
        self,
        checkout_id: UUID,
        token_hash: str,
        expires_in_seconds: int,
        response_ciphertext: str,
    ) -> None: ...

    async def get_checkout(self, token_hash: str) -> CheckoutRecord | None: ...

    async def consume_checkout(self, checkout_id: UUID, subscription: LocalSubscription) -> None: ...


class SqlAlchemySubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_plan(self, code: str) -> LocalPlan | None:
        plan = await self._session.scalar(select(Plan).where(Plan.code == code))
        if plan is None:
            return None
        return LocalPlan(id=plan.id, code=plan.code, active=plan.active)

    async def get_subscription(self, user_id: UUID) -> LocalSubscription | None:
        row = (
            await self._session.execute(
                select(Subscription, Plan.code)
                .join(Plan, Plan.id == Subscription.plan_id)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        subscription, plan_code = row
        return LocalSubscription(
            id=subscription.id,
            user_id=subscription.user_id,
            provider_reference=subscription.provider_subscription_ref,
            plan_code=plan_code,
            status=subscription.status,
            plan_id=subscription.plan_id,
            grace_until=subscription.entitlement_grace_until,
        )

    async def set_status(self, subscription_id: UUID, status: SubscriptionStatus) -> None:
        await self._session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=status)
        )
        await self._session.commit()

    async def change_plan(self, subscription_id: UUID, subscription: LocalSubscription) -> None:
        if subscription.plan_id is None:
            raise SubscriptionServiceError("subscription plan kimligi eksik")
        result = await self._session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id, Subscription.user_id == subscription.user_id)
            .values(
                provider_subscription_ref=subscription.provider_reference,
                plan_id=subscription.plan_id,
                status=subscription.status,
            )
        )
        if result.rowcount != 1:
            await self._session.rollback()
            raise SubscriptionServiceError("subscription plan degisikligi kaydedilemedi")
        await self._session.commit()

    async def upsert_subscription(self, subscription: LocalSubscription) -> None:
        if subscription.plan_id is None:
            raise SubscriptionServiceError("subscription plan kimligi eksik")
        statement = (
            insert(Subscription)
            .values(
                id=subscription.id,
                user_id=subscription.user_id,
                provider="iyzico",
                provider_subscription_ref=subscription.provider_reference,
                plan_id=subscription.plan_id,
                status=subscription.status,
            )
            .on_conflict_do_update(
                index_elements=[Subscription.provider_subscription_ref],
                set_={
                    "plan_id": subscription.plan_id,
                    "status": subscription.status,
                },
                where=Subscription.user_id == subscription.user_id,
            )
        )
        result = await self._session.execute(statement)
        if result.rowcount != 1:
            await self._session.rollback()
            raise SubscriptionServiceError("provider subscription baska kullaniciya ait")
        await self._session.commit()

    async def reserve_checkout(
        self,
        *,
        user_id: UUID,
        plan_id: UUID,
        plan_code: str,
        interval: BillingInterval,
        idempotency_key_hash: str,
        request_fingerprint: str,
        cooldown_seconds: int,
    ) -> CheckoutRecord:
        locked_user = await self._session.scalar(
            select(User.id).where(User.id == user_id).with_for_update()
        )
        if locked_user is None:
            raise SubscriptionServiceError("billing kullanicisi bulunamadi")
        existing = await self._session.scalar(
            select(BillingCheckoutSession).where(
                BillingCheckoutSession.idempotency_key_hash == idempotency_key_hash
            )
        )
        if existing is not None:
            if (
                existing.user_id != user_id
                or existing.request_fingerprint != request_fingerprint
            ):
                raise SubscriptionServiceError("checkout idempotency key payload ile eslesmiyor")
            if (
                existing.status is BillingCheckoutStatus.READY
                and existing.response_ciphertext
            ):
                return CheckoutRecord(
                    id=existing.id,
                    user_id=user_id,
                    plan_id=existing.plan_id,
                    plan_code=plan_code,
                    interval=BillingInterval(existing.interval),
                    idempotency_key_hash=idempotency_key_hash,
                    token_hash=existing.provider_token_hash,
                    expires_at=existing.expires_at,
                    request_fingerprint=existing.request_fingerprint,
                    response_ciphertext=existing.response_ciphertext,
                )
            raise SubscriptionServiceError("checkout idempotency istegi halen isleniyor")
        active = await self._session.scalar(
            select(Subscription.id).where(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.PENDING,
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.PAST_DUE,
                ]),
            ).limit(1)
        )
        if active is not None:
            raise SubscriptionServiceError("kullanicinin devam eden aboneligi var")
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)
        recent = await self._session.scalar(
            select(BillingCheckoutSession.id).where(
                BillingCheckoutSession.user_id == user_id,
                BillingCheckoutSession.status.in_([
                    BillingCheckoutStatus.INITIALIZING,
                    BillingCheckoutStatus.READY,
                ]),
                BillingCheckoutSession.created_at >= cutoff,
            ).limit(1)
        )
        if recent is not None:
            raise SubscriptionServiceError("checkout cok sik tekrarlandi")
        row = BillingCheckoutSession(
            id=uuid4(),
            user_id=user_id,
            plan_id=plan_id,
            interval=interval.value,
            idempotency_key_hash=idempotency_key_hash,
            request_fingerprint=request_fingerprint,
            status=BillingCheckoutStatus.INITIALIZING,
        )
        self._session.add(row)
        await self._session.commit()
        return CheckoutRecord(
            id=row.id,
            user_id=user_id,
            plan_id=plan_id,
            plan_code=plan_code,
            interval=interval,
            idempotency_key_hash=idempotency_key_hash,
            request_fingerprint=request_fingerprint,
        )

    async def attach_checkout_token(
        self,
        checkout_id: UUID,
        token_hash: str,
        expires_in_seconds: int,
        response_ciphertext: str,
    ) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in_seconds, 1))
        result = await self._session.execute(
            update(BillingCheckoutSession)
            .where(
                BillingCheckoutSession.id == checkout_id,
                BillingCheckoutSession.status == BillingCheckoutStatus.INITIALIZING,
            )
            .values(
                provider_token_hash=token_hash,
                status=BillingCheckoutStatus.READY,
                expires_at=expires_at,
                response_ciphertext=response_ciphertext,
            )
        )
        if result.rowcount != 1:
            await self._session.rollback()
            raise SubscriptionServiceError("checkout oturumu guncellenemedi")
        await self._session.commit()

    async def get_checkout(self, token_hash: str) -> CheckoutRecord | None:
        row = (
            await self._session.execute(
                select(BillingCheckoutSession, Plan.code)
                .join(Plan, Plan.id == BillingCheckoutSession.plan_id)
                .where(BillingCheckoutSession.provider_token_hash == token_hash)
            )
        ).first()
        if row is None:
            return None
        checkout, plan_code = row
        return CheckoutRecord(
            id=checkout.id,
            user_id=checkout.user_id,
            plan_id=checkout.plan_id,
            plan_code=plan_code,
            interval=BillingInterval(checkout.interval),
            idempotency_key_hash=checkout.idempotency_key_hash,
            token_hash=checkout.provider_token_hash,
            consumed=checkout.status is BillingCheckoutStatus.CONSUMED,
            expires_at=checkout.expires_at,
            request_fingerprint=checkout.request_fingerprint,
            response_ciphertext=checkout.response_ciphertext,
        )

    async def consume_checkout(
        self, checkout_id: UUID, subscription: LocalSubscription
    ) -> None:
        if subscription.plan_id is None:
            raise SubscriptionServiceError("subscription plan kimligi eksik")
        checkout = await self._session.scalar(
            select(BillingCheckoutSession)
            .where(BillingCheckoutSession.id == checkout_id)
            .with_for_update()
        )
        if checkout is None:
            raise SubscriptionServiceError("checkout bulunamadi")
        if checkout.status is BillingCheckoutStatus.CONSUMED:
            return
        if checkout.status is not BillingCheckoutStatus.READY:
            raise SubscriptionServiceError("checkout durumu gecersiz")
        statement = (
            insert(Subscription)
            .values(
                id=subscription.id,
                user_id=subscription.user_id,
                provider="iyzico",
                provider_subscription_ref=subscription.provider_reference,
                plan_id=subscription.plan_id,
                status=subscription.status,
            )
            .on_conflict_do_update(
                index_elements=[Subscription.provider_subscription_ref],
                set_={"plan_id": subscription.plan_id, "status": subscription.status},
                where=Subscription.user_id == subscription.user_id,
            )
        )
        result = await self._session.execute(statement)
        if result.rowcount != 1:
            await self._session.rollback()
            raise SubscriptionServiceError("provider subscription baska kullaniciya ait")
        checkout.status = BillingCheckoutStatus.CONSUMED
        checkout.consumed_at = datetime.now(timezone.utc)
        await self._session.commit()


PROVIDER_STATUS_MAP = {
    "ACTIVE": SubscriptionStatus.ACTIVE,
    "PENDING": SubscriptionStatus.PENDING,
    "UNPAID": SubscriptionStatus.PAST_DUE,
    "UPGRADED": SubscriptionStatus.ACTIVE,
    "CANCELED": SubscriptionStatus.CANCELLED,
    "CANCELLED": SubscriptionStatus.CANCELLED,
    "EXPIRED": SubscriptionStatus.EXPIRED,
}


def paid_entitlement_is_active(
    status: SubscriptionStatus,
    *,
    grace_until: datetime | None,
    now: datetime | None = None,
) -> bool:
    if status is SubscriptionStatus.ACTIVE:
        return True
    if status is not SubscriptionStatus.PAST_DUE or grace_until is None:
        return False
    current = now or datetime.now(timezone.utc)
    return grace_until > current


class SubscriptionService:
    def __init__(
        self,
        repository: SubscriptionRepository,
        provider: IyzicoClient,
        plan_references: PlanReferenceMap,
        callback_url: str,
        checkout_encryption_secret: str,
        cooldown_seconds: int = 30,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._plan_references = plan_references
        self._callback_url = callback_url
        self._checkout_cipher = CheckoutCipher(checkout_encryption_secret)
        self._cooldown_seconds = cooldown_seconds
        if not callback_url.strip() or cooldown_seconds < 0:
            raise SubscriptionServiceError("checkout callback configuration eksik")

    async def create_checkout(
        self,
        *,
        user_id: UUID,
        plan_code: str,
        interval: BillingInterval,
        customer: dict[str, Any],
        idempotency_key: str,
    ) -> CheckoutSession:
        plan = await self._repository.get_plan(plan_code)
        if plan is None or not plan.active:
            raise SubscriptionServiceError("aktif plan bulunamadi")
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise SubscriptionServiceError("idempotency key bos olamaz")
        key_hash = hashlib.sha256(f"{user_id}:{normalized_key}".encode()).hexdigest()
        request_fingerprint = hashlib.sha256(
            json.dumps(
                {"plan_code": plan.code, "interval": interval.value, "customer": customer},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        checkout_record = await self._repository.reserve_checkout(
            user_id=user_id,
            plan_id=plan.id,
            plan_code=plan.code,
            interval=interval,
            idempotency_key_hash=key_hash,
            request_fingerprint=request_fingerprint,
            cooldown_seconds=self._cooldown_seconds,
        )
        if checkout_record.response_ciphertext:
            if (
                checkout_record.expires_at is not None
                and checkout_record.expires_at <= datetime.now(timezone.utc)
            ):
                raise SubscriptionServiceError("checkout suresi dolmus")
            return self._checkout_cipher.decrypt(checkout_record.response_ciphertext)
        pricing_reference = self._plan_references.pricing_reference(plan.code, interval)
        checkout = await self._provider.initialize_subscription_checkout(
            callback_url=self._callback_url,
            pricing_plan_reference_code=pricing_reference,
            conversation_id=str(checkout_record.id),
            customer=customer,
        )
        await self._repository.attach_checkout_token(
            checkout_record.id,
            hashlib.sha256(checkout.token.encode()).hexdigest(),
            checkout.expires_in_seconds,
            self._checkout_cipher.encrypt(checkout),
        )
        return checkout

    async def get_status(self, user_id: UUID) -> SubscriptionSnapshot:
        subscription = await self._repository.get_subscription(user_id)
        if subscription is None:
            raise SubscriptionServiceError("subscription bulunamadi")
        provider = await self._provider.get_subscription(subscription.provider_reference)
        if provider.reference_code != subscription.provider_reference:
            raise SubscriptionServiceError("provider subscription eslesmesi gecersiz")
        interval = self._plan_references.verify_provider_references(
            subscription.plan_code,
            provider.product_reference_code,
            provider.pricing_plan_reference_code,
        )
        try:
            status = PROVIDER_STATUS_MAP[provider.status]
        except KeyError as exc:
            raise SubscriptionServiceError("provider subscription status gecersiz") from exc
        if (
            subscription.status is SubscriptionStatus.PAST_DUE
            and status is SubscriptionStatus.ACTIVE
        ):
            status = SubscriptionStatus.PAST_DUE
        if status is not subscription.status:
            await self._repository.set_status(subscription.id, status)
        return SubscriptionSnapshot(
            subscription.plan_code,
            interval,
            status,
            grace_until=subscription.grace_until,
        )

    async def change_plan(
        self,
        user_id: UUID,
        plan_code: str,
        interval: BillingInterval,
    ) -> SubscriptionSnapshot:
        subscription = await self._repository.get_subscription(user_id)
        if subscription is None:
            raise SubscriptionServiceError("subscription bulunamadi")
        target_plan = await self._repository.get_plan(plan_code)
        if target_plan is None or not target_plan.active:
            raise SubscriptionServiceError("aktif plan bulunamadi")
        provider = await self._provider.get_subscription(subscription.provider_reference)
        current_interval = self._plan_references.verify_provider_references(
            subscription.plan_code,
            provider.product_reference_code,
            provider.pricing_plan_reference_code,
        )
        if current_interval is not interval:
            raise SubscriptionServiceError("plan degisikligi odeme araligi ile eslesmiyor")
        target_pricing_reference = self._plan_references.pricing_reference(plan_code, interval)
        self._plan_references.verify_provider_references(
            plan_code,
            provider.product_reference_code,
            target_pricing_reference,
        )
        upgraded_reference = await self._provider.upgrade_subscription(
            subscription.provider_reference,
            target_pricing_reference,
        )
        upgraded = await self._provider.get_subscription(upgraded_reference)
        verified_interval = self._plan_references.verify_provider_references(
            plan_code,
            upgraded.product_reference_code,
            upgraded.pricing_plan_reference_code,
        )
        try:
            status = PROVIDER_STATUS_MAP[upgraded.status]
        except KeyError as exc:
            raise SubscriptionServiceError("provider subscription status gecersiz") from exc
        changed = LocalSubscription(
            id=subscription.id,
            user_id=user_id,
            provider_reference=upgraded.reference_code,
            plan_code=plan_code,
            status=status,
            plan_id=target_plan.id,
            grace_until=subscription.grace_until,
        )
        await self._repository.change_plan(subscription.id, changed)
        return SubscriptionSnapshot(plan_code, verified_interval, status, subscription.grace_until)

    async def confirm_checkout(self, token: str) -> SubscriptionSnapshot:
        token_hash = hashlib.sha256(token.strip().encode()).hexdigest()
        checkout = await self._repository.get_checkout(token_hash)
        if checkout is None:
            raise SubscriptionServiceError("checkout bulunamadi")
        if (
            not checkout.consumed
            and checkout.expires_at is not None
            and checkout.expires_at <= datetime.now(timezone.utc)
        ):
            raise SubscriptionServiceError("checkout suresi dolmus")
        if checkout.consumed:
            subscription = await self._repository.get_subscription(checkout.user_id)
            if subscription is None:
                raise SubscriptionServiceError("subscription bulunamadi")
            return SubscriptionSnapshot(checkout.plan_code, checkout.interval, subscription.status)
        checkout_result = await self._provider.retrieve_checkout(token)
        provider = await self._provider.get_subscription(checkout_result.reference_code)
        if (
            provider.reference_code != checkout_result.reference_code
            or provider.pricing_plan_reference_code
            != checkout_result.pricing_plan_reference_code
        ):
            raise SubscriptionServiceError("provider checkout eslesmesi gecersiz")
        interval = self._plan_references.verify_provider_references(
            checkout.plan_code,
            provider.product_reference_code,
            provider.pricing_plan_reference_code
        )
        if interval is not checkout.interval:
            raise SubscriptionServiceError("checkout interval eslesmesi gecersiz")
        plan = await self._repository.get_plan(checkout.plan_code)
        if plan is None or not plan.active:
            raise SubscriptionServiceError("aktif plan bulunamadi")
        try:
            status = PROVIDER_STATUS_MAP[provider.status]
        except KeyError as exc:
            raise SubscriptionServiceError("provider subscription status gecersiz") from exc
        subscription = LocalSubscription(
            id=uuid4(),
            user_id=checkout.user_id,
            provider_reference=provider.reference_code,
            plan_code=plan.code,
            status=status,
            plan_id=plan.id,
        )
        await self._repository.consume_checkout(checkout.id, subscription)
        return SubscriptionSnapshot(plan.code, interval, status)

    async def cancel(self, user_id: UUID) -> SubscriptionSnapshot:
        subscription = await self._repository.get_subscription(user_id)
        if subscription is None:
            raise SubscriptionServiceError("subscription bulunamadi")
        await self._provider.cancel_subscription(subscription.provider_reference)
        return await self.get_status(user_id)
