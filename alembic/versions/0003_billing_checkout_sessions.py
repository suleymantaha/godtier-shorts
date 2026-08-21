"""add durable billing checkout sessions

Revision ID: 0003_billing_checkout_sessions
Revises: 0002_immutable_credit_ledger
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_billing_checkout_sessions"
down_revision: Union[str, Sequence[str], None] = "0002_immutable_credit_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_checkout_sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provider_token_hash", sa.String(length=64), nullable=True),
        sa.Column("response_ciphertext", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('initializing', 'ready', 'consumed', 'failed')",
            name=op.f("ck_billing_checkout_sessions_billing_checkout_status"),
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key_hash", name="uq_billing_checkout_idempotency_key_hash"),
        sa.UniqueConstraint("provider_token_hash", name="uq_billing_checkout_provider_token_hash"),
    )
    op.create_index(
        "ix_billing_checkout_user_created",
        "billing_checkout_sessions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "uq_subscriptions_one_current_per_user",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'active', 'past_due')"),
    )


def downgrade() -> None:
    op.drop_index("uq_subscriptions_one_current_per_user", table_name="subscriptions")
    op.drop_index("ix_billing_checkout_user_created", table_name="billing_checkout_sessions")
    op.drop_table("billing_checkout_sessions")
