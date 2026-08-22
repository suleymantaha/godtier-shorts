"""add durable job usage metrics

Revision ID: 0006_job_usage_metrics
Revises: 0005_job_idempotency
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_job_usage_metrics"
down_revision: Union[str, Sequence[str], None] = "0005_job_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_usage_metrics",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_seconds", sa.Integer(), nullable=False),
        sa.Column("transcript_seconds", sa.Integer(), nullable=False),
        sa.Column("tracking_seconds", sa.Integer(), nullable=False),
        sa.Column("render_seconds", sa.Integer(), nullable=False),
        sa.Column("total_wall_seconds", sa.Integer(), nullable=False),
        sa.Column("gpu_model", sa.String(length=120), nullable=False),
        sa.Column("gpu_seconds", sa.BigInteger(), nullable=False),
        sa.Column("output_count", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("estimated_internal_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("peak_vram_mb", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_seconds >= 0", name=op.f("ck_job_usage_metrics_source_seconds_nonnegative")),
        sa.CheckConstraint("gpu_seconds >= 0", name=op.f("ck_job_usage_metrics_gpu_seconds_nonnegative")),
        sa.CheckConstraint("estimated_internal_cost_usd >= 0", name=op.f("ck_job_usage_metrics_cost_nonnegative")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_job_usage_metrics_user_id", "job_usage_metrics", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_job_usage_metrics_user_id", table_name="job_usage_metrics")
    op.drop_table("job_usage_metrics")
