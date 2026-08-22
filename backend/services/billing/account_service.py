from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    CreditWallet,
    Job,
    JobUsageMetric,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
)


@dataclass(frozen=True, slots=True)
class PlanRecord:
    id: UUID
    code: str
    name: str
    monthly_price_minor: int
    currency: str
    monthly_compute_credits: int
    max_source_minutes_per_job: int
    max_clips_per_job: int
    max_active_jobs: int
    retention_days: int


@dataclass(frozen=True, slots=True)
class SubscriptionRecord:
    plan: PlanRecord
    status: SubscriptionStatus
    period_start: datetime | None
    period_end: datetime | None
    cancel_at_period_end: bool
    grace_until: datetime | None


@dataclass(frozen=True, slots=True)
class PaymentRecord:
    id: UUID
    amount_minor: int
    currency: str
    status: PaymentStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AccountRecord:
    subscription: SubscriptionRecord | None
    plans: tuple[PlanRecord, ...]
    payments: tuple[PaymentRecord, ...]
    source_seconds_used: int
    compute_credits_used: int
    wallet_available: int
    wallet_reserved: int


@dataclass(frozen=True, slots=True)
class AccountSubscriptionSnapshot:
    plan: PlanRecord
    interval: str | None
    status: SubscriptionStatus
    period_start: datetime | None
    period_end: datetime | None
    cancel_at_period_end: bool
    grace_until: datetime | None


@dataclass(frozen=True, slots=True)
class BillingAccountSnapshot:
    subscription: AccountSubscriptionSnapshot | None
    plans: tuple[PlanRecord, ...]
    payments: tuple[PaymentRecord, ...]
    source_seconds_used: int
    source_seconds_per_job_limit: int
    compute_credits_used: int
    compute_credits_available: int
    compute_credits_reserved: int


class AccountRepository(Protocol):
    async def get_account(self, user_id: UUID) -> AccountRecord: ...


def _plan_record(plan: Plan) -> PlanRecord:
    return PlanRecord(
        plan.id,
        plan.code,
        plan.name,
        plan.monthly_price_minor,
        plan.currency,
        plan.monthly_compute_credits,
        plan.max_source_minutes_per_job,
        plan.max_clips_per_job,
        plan.max_active_jobs,
        plan.retention_days,
    )


class SqlAlchemyBillingAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_account(self, user_id: UUID) -> AccountRecord:
        subscription_row = (
            await self._session.execute(
                select(Subscription, Plan)
                .join(Plan, Plan.id == Subscription.plan_id)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.updated_at.desc())
                .limit(1)
            )
        ).first()
        subscription = None
        if subscription_row is not None:
            local_subscription, subscribed_plan = subscription_row
            subscription = SubscriptionRecord(
                plan=_plan_record(subscribed_plan),
                status=local_subscription.status,
                period_start=local_subscription.period_start,
                period_end=local_subscription.period_end,
                cancel_at_period_end=local_subscription.cancel_at_period_end,
                grace_until=local_subscription.entitlement_grace_until,
            )

        plans = tuple(
            _plan_record(plan)
            for plan in (
                await self._session.scalars(
                    select(Plan).where(Plan.active.is_(True)).order_by(Plan.priority, Plan.monthly_price_minor)
                )
            ).all()
        )
        period_start, period_end = _usage_period(subscription)
        usage_filters = [JobUsageMetric.user_id == user_id, JobUsageMetric.created_at >= period_start]
        job_filters = [Job.user_id == user_id, Job.created_at >= period_start]
        if period_end is not None:
            usage_filters.append(JobUsageMetric.created_at < period_end)
            job_filters.append(Job.created_at < period_end)
        source_seconds = await self._session.scalar(
            select(func.coalesce(func.sum(JobUsageMetric.source_seconds), 0)).where(*usage_filters)
        )
        compute_credits = await self._session.scalar(
            select(func.coalesce(func.sum(Job.settled_credits), 0)).where(*job_filters)
        )
        wallet = await self._session.get(CreditWallet, user_id)
        payment_rows = (
            await self._session.scalars(
                select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(Payment.created_at.desc())
                .limit(50)
            )
        ).all()
        payments = tuple(
            PaymentRecord(payment.id, payment.amount_minor, payment.currency, payment.status, payment.created_at)
            for payment in payment_rows
        )
        return AccountRecord(
            subscription=subscription,
            plans=plans,
            payments=payments,
            source_seconds_used=int(source_seconds or 0),
            compute_credits_used=int(compute_credits or 0),
            wallet_available=wallet.available if wallet else 0,
            wallet_reserved=wallet.reserved if wallet else 0,
        )


def _usage_period(subscription: SubscriptionRecord | None) -> tuple[datetime, datetime | None]:
    if subscription and subscription.period_start:
        return subscription.period_start, subscription.period_end
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), None


class BillingAccountService:
    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    async def get_account(self, user_id: UUID, *, interval: str | None = None) -> BillingAccountSnapshot:
        record = await self._repository.get_account(user_id)
        subscription = None
        if record.subscription is not None:
            subscription = AccountSubscriptionSnapshot(
                plan=record.subscription.plan,
                interval=interval,
                status=record.subscription.status,
                period_start=record.subscription.period_start,
                period_end=record.subscription.period_end,
                cancel_at_period_end=record.subscription.cancel_at_period_end,
                grace_until=record.subscription.grace_until,
            )
        limit_plan = record.subscription.plan if record.subscription else next(iter(record.plans), None)
        source_limit = limit_plan.max_source_minutes_per_job * 60 if limit_plan else 0
        return BillingAccountSnapshot(
            subscription=subscription,
            plans=record.plans,
            payments=record.payments,
            source_seconds_used=max(0, record.source_seconds_used),
            source_seconds_per_job_limit=max(0, source_limit),
            compute_credits_used=max(0, record.compute_credits_used),
            compute_credits_available=max(0, record.wallet_available),
            compute_credits_reserved=max(0, record.wallet_reserved),
        )
