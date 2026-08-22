from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    AuditLog,
    CreditLedgerEntry,
    Job,
    JobEvent,
    JobStatus,
    LedgerKind,
    RiskEvent,
    Subscription,
    SubscriptionStatus,
    User,
    UserStatus,
)
from backend.services.billing import ledger
from backend.services.billing.iyzico_client import ProviderSubscription
from backend.services.billing.subscription_service import PROVIDER_STATUS_MAP
from backend.services.queue.client import QueueClient


class AdminOperationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuditContext:
    actor_id: UUID | None
    request_id: str
    ip_hash: str | None = None


class AdminService(Protocol):
    async def overview(self) -> dict[str, Any]: ...

    async def adjust_credit(self, user_id: UUID, amount: int, *, reason: str, idempotency_key: str, audit: AuditContext) -> int: ...

    async def suspend_user(self, user_id: UUID, *, reason: str, audit: AuditContext) -> None: ...

    async def sync_subscription(self, subscription_id: UUID, *, reason: str, audit: AuditContext) -> str: ...

    async def retry_failed_job(self, job_id: UUID, *, reason: str, idempotency_key: str, audit: AuditContext) -> None: ...


class SubscriptionProvider(Protocol):
    async def get_subscription(self, reference_code: str) -> ProviderSubscription: ...


class SqlAlchemyAdminService:
    def __init__(self, session: AsyncSession, provider: SubscriptionProvider, queue: QueueClient) -> None:
        self._session = session
        self._provider = provider
        self._queue = queue

    async def overview(self) -> dict[str, Any]:
        async def count(model, *criteria) -> int:
            value = await self._session.scalar(select(func.count()).select_from(model).where(*criteria))
            return int(value or 0)

        users = list((await self._session.scalars(select(User).order_by(User.created_at.desc()).limit(20))).all())
        subscriptions = list((await self._session.scalars(select(Subscription).order_by(Subscription.created_at.desc()).limit(20))).all())
        jobs = list((await self._session.scalars(select(Job).order_by(Job.created_at.desc()).limit(20))).all())
        risks = list((await self._session.scalars(select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(20))).all())
        return {
            "users": await count(User),
            "subscriptions": await count(Subscription),
            "jobs": await count(Job),
            "failed_jobs": await count(Job, Job.status == JobStatus.ERROR),
            "risk_events": await count(RiskEvent),
            "recent_users": [{"id": str(row.id), "status": row.status.value, "role": row.role.value} for row in users],
            "recent_subscriptions": [{"id": str(row.id), "user_id": str(row.user_id), "status": row.status.value} for row in subscriptions],
            "recent_jobs": [{"id": str(row.id), "user_id": str(row.user_id), "status": row.status.value} for row in jobs],
            "recent_risk_events": [{"id": row.id, "user_id": str(row.user_id) if row.user_id else None, "signal": row.signal, "weight": row.weight} for row in risks],
        }

    def _audit(
        self,
        audit: AuditContext,
        *,
        action: str,
        target_type: str,
        target_id: UUID,
        reason: str,
        metadata: dict | None = None,
    ) -> None:
        values = {"reason": reason, **(metadata or {})}
        self._session.add(
            AuditLog(
                actor_type="admin",
                actor_id=audit.actor_id,
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                request_id=audit.request_id,
                ip_hash=audit.ip_hash,
                metadata_json=values,
            )
        )

    async def adjust_credit(
        self,
        user_id: UUID,
        amount: int,
        *,
        reason: str,
        idempotency_key: str,
        audit: AuditContext,
    ) -> int:
        async with self._session.begin():
            if await self._session.get(User, user_id) is None:
                raise AdminOperationError("kullanici bulunamadi")
            available = await ledger.adjust_in_session(
                self._session,
                user_id,
                amount,
                f"admin-adjust:{idempotency_key}",
                {"reason": reason, "actor_id": str(audit.actor_id) if audit.actor_id else None},
            )
            self._audit(
                audit,
                action="credit.adjust",
                target_type="user",
                target_id=user_id,
                reason=reason,
                metadata={"amount": amount, "idempotency_key": idempotency_key},
            )
        return available

    async def suspend_user(self, user_id: UUID, *, reason: str, audit: AuditContext) -> None:
        async with self._session.begin():
            user = await self._session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise AdminOperationError("kullanici bulunamadi")
            if audit.actor_id == user_id:
                raise AdminOperationError("admin kendi hesabini askıya alamaz")
            previous = user.status.value
            user.status = UserStatus.SUSPENDED
            self._audit(
                audit,
                action="user.suspend",
                target_type="user",
                target_id=user_id,
                reason=reason,
                metadata={"previous_status": previous},
            )

    async def sync_subscription(
        self,
        subscription_id: UUID,
        *,
        reason: str,
        audit: AuditContext,
    ) -> str:
        async with self._session.begin():
            subscription = await self._session.get(Subscription, subscription_id)
            if subscription is None:
                raise AdminOperationError("subscription bulunamadi")
            provider_reference = subscription.provider_subscription_ref
        provider = await self._provider.get_subscription(provider_reference)
        if provider.reference_code != provider_reference:
            raise AdminOperationError("provider subscription eslesmesi gecersiz")
        try:
            provider_status = PROVIDER_STATUS_MAP[provider.status]
        except KeyError as exc:
            raise AdminOperationError("provider subscription status gecersiz") from exc

        async with self._session.begin():
            locked = await self._session.scalar(
                select(Subscription).where(Subscription.id == subscription_id).with_for_update()
            )
            if locked is None:
                raise AdminOperationError("subscription bulunamadi")
            if locked.provider_subscription_ref != provider_reference:
                raise AdminOperationError("subscription provider referansi eszamanli degisti")
            previous = locked.status.value
            locked.status = provider_status
            self._audit(
                audit,
                action="subscription.sync",
                target_type="subscription",
                target_id=subscription_id,
                reason=reason,
                metadata={"previous_status": previous, "provider_status": provider_status.value},
            )
        return provider_status.value

    async def retry_failed_job(
        self,
        job_id: UUID,
        *,
        reason: str,
        idempotency_key: str,
        audit: AuditContext,
    ) -> None:
        reservation_key = f"admin-retry-reserve:{idempotency_key}"
        async with self._session.begin():
            existing_retry = await self._session.scalar(
                select(CreditLedgerEntry).where(CreditLedgerEntry.idempotency_key == reservation_key)
            )
            if existing_retry is not None:
                if existing_retry.job_id != job_id or existing_retry.kind is not LedgerKind.RESERVE:
                    raise AdminOperationError("idempotency key farkli bir retry icin kullanilmis")
                return
            job = await self._session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job is None:
                raise AdminOperationError("job bulunamadi")
            if job.status is not JobStatus.ERROR or job.settled_credits:
                raise AdminOperationError("yalniz harcanmamis failed job tekrar denenebilir")
            reserve_amount = await self._session.scalar(
                select(CreditLedgerEntry.amount)
                .where(
                    CreditLedgerEntry.job_id == job_id,
                    CreditLedgerEntry.kind == LedgerKind.RELEASE,
                )
                .order_by(CreditLedgerEntry.created_at.desc())
                .limit(1)
            )
            if not reserve_amount:
                raise AdminOperationError("retry icin onceki kredi rezervasyonu bulunamadi")
            await ledger.reserve_in_session(
                self._session,
                job.user_id,
                int(reserve_amount),
                job.id,
                reservation_key,
            )
            job.status = JobStatus.QUEUED
            job.progress = 0
            job.started_at = None
            job.finished_at = None
            job.error_code = None
            job.error_message = None
            job.last_message = "Admin retry queued"
            self._session.add(JobEvent(job_id=job.id, status=job.status, progress=0, message=job.last_message, source="admin"))
            self._audit(
                audit,
                action="job.retry",
                target_type="job",
                target_id=job_id,
                reason=reason,
                metadata={"idempotency_key": idempotency_key},
            )

        try:
            await self._queue.enqueue_gpu_job(job_id)
        except Exception:
            async with self._session.begin():
                job = await self._session.scalar(select(Job).where(Job.id == job_id).with_for_update())
                if job is not None and job.status is JobStatus.QUEUED:
                    job.status = JobStatus.ERROR
                    job.error_code = "ADMIN_RETRY_DISPATCH_FAILED"
                    job.error_message = "Redis queue dispatch failed"
                    await ledger.release_in_session(
                        self._session,
                        job.user_id,
                        job.id,
                        f"admin-retry-release:{idempotency_key}",
                    )
            raise AdminOperationError("job queue dispatch basarisiz")
