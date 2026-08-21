from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class UserRole(str, enum.Enum):
    USER = "user"
    SUPPORT = "support"
    ADMIN = "admin"


class SubscriptionStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BillingCheckoutStatus(str, enum.Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    CONSUMED = "consumed"
    FAILED = "failed"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class LedgerKind(str, enum.Enum):
    GRANT = "grant"
    RESERVE = "reserve"
    RELEASE = "release"
    SETTLE = "settle"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    EXPIRE = "expire"


class JobType(str, enum.Enum):
    PREVIEW = "preview"
    FULL_RENDER = "full_render"
    REBURN = "reburn"
    BATCH = "batch"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
    REVIEW_REQUIRED = "review_required"


class SourceType(str, enum.Enum):
    YOUTUBE = "youtube"
    UPLOAD = "upload"


class AssetKind(str, enum.Enum):
    SOURCE = "source"
    TRANSCRIPT = "transcript"
    PREVIEW = "preview"
    SHORT = "short"
    THUMBNAIL = "thumbnail"
    DEBUG = "debug"


class TrialStatus(str, enum.Enum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    BLOCKED = "blocked"


def _enum(enum_type: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


def _enum_check(column_name: str, enum_type: type[enum.Enum], name: str) -> CheckConstraint:
    values = ", ".join(repr(member.value) for member in enum_type)
    return CheckConstraint(f"{column_name} IN ({values})", name=name)


def _uuid_primary_key() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        _enum_check("status", UserStatus, "user_status"),
        _enum_check("role", UserRole, "user_role"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    clerk_subject: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email_normalized: Mapped[str | None] = mapped_column(Text)
    status: Mapped[UserStatus] = mapped_column(_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False, default=UserRole.USER)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("monthly_price_minor >= 0", name="monthly_price_nonnegative"),
        CheckConstraint("monthly_compute_credits >= 0", name="monthly_credits_nonnegative"),
        CheckConstraint("max_source_minutes_per_job > 0", name="source_minutes_positive"),
        CheckConstraint("max_clips_per_job > 0", name="clips_positive"),
        CheckConstraint("max_active_jobs > 0", name="active_jobs_positive"),
        CheckConstraint("retention_days > 0", name="retention_days_positive"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    monthly_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    monthly_compute_credits: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_source_minutes_per_job: Mapped[int] = mapped_column(Integer, nullable=False)
    max_clips_per_job: Mapped[int] = mapped_column(Integer, nullable=False)
    max_active_jobs: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        _enum_check("status", SubscriptionStatus, "subscription_status"),
        Index(
            "uq_subscriptions_one_current_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active', 'past_due')"),
            sqlite_where=text("status IN ('pending', 'active', 'past_due')"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'iyzico'"))
    provider_subscription_ref: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        _enum(SubscriptionStatus, "subscription_status"), nullable=False, default=SubscriptionStatus.PENDING
    )
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    entitlement_grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BillingCheckoutSession(Base):
    __tablename__ = "billing_checkout_sessions"
    __table_args__ = (
        _enum_check("status", BillingCheckoutStatus, "billing_checkout_status"),
        UniqueConstraint("idempotency_key_hash", name="uq_billing_checkout_idempotency_key_hash"),
        UniqueConstraint("provider_token_hash", name="uq_billing_checkout_provider_token_hash"),
        Index("ix_billing_checkout_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_token_hash: Mapped[str | None] = mapped_column(String(64))
    response_ciphertext: Mapped[str | None] = mapped_column(Text)
    status: Mapped[BillingCheckoutStatus] = mapped_column(
        _enum(BillingCheckoutStatus, "billing_checkout_status"),
        nullable=False,
        default=BillingCheckoutStatus.INITIALIZING,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="amount_nonnegative"),
        _enum_check("status", PaymentStatus, "payment_status"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider_payment_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provider_conversation_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(_enum(PaymentStatus, "payment_status"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class CreditWallet(Base):
    __tablename__ = "credit_wallets"
    __table_args__ = (
        CheckConstraint("available >= 0", name="available_nonnegative"),
        CheckConstraint("reserved >= 0", name="reserved_nonnegative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    available: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    reserved: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (_enum_check("source_type", SourceType, "source_type"),)

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_type: Mapped[SourceType] = mapped_column(_enum(SourceType, "source_type"), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created_at()


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        CheckConstraint("reserved_credits >= 0", name="reserved_credits_nonnegative"),
        CheckConstraint("settled_credits >= 0", name="settled_credits_nonnegative"),
        _enum_check("type", JobType, "job_type"),
        _enum_check("status", JobStatus, "job_status"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    type: Mapped[JobType] = mapped_column(_enum(JobType, "job_type"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus, "job_status"), nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    last_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    reserved_credits: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    settled_credits: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    gpu_seconds: Mapped[int | None] = mapped_column(BigInteger)
    gpu_model: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class CreditLedgerEntry(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (_enum_check("kind", LedgerKind, "ledger_kind"),)

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind: Mapped[LedgerKind] = mapped_column(_enum(LedgerKind, "ledger_kind"), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), index=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VALUE, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created_at()


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (_enum_check("status", JobStatus, "job_event_status"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus, "job_event_status"), nullable=False)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        _enum_check("kind", AssetKind, "asset_kind"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[AssetKind] = mapped_column(_enum(AssetKind, "asset_kind"), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class TrialEntitlement(Base):
    __tablename__ = "trial_entitlements"
    __table_args__ = (
        UniqueConstraint("identity_key_hash", name="uq_trial_entitlements_identity_key_hash"),
        _enum_check("status", TrialStatus, "trial_status"),
    )

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    identity_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[TrialStatus] = mapped_column(_enum(TrialStatus, "trial_status"), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    value_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VALUE, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created_at()


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_key", name="uq_webhook_events_provider_event_key"),)

    id: Mapped[uuid.UUID] = _uuid_primary_key()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_key: Mapped[str] = mapped_column(Text, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VALUE, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created_at()
