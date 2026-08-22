"""add durable job idempotency key

Revision ID: 0005_job_idempotency
Revises: 0004_subscription_grace_window
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_job_idempotency"
down_revision: Union[str, Sequence[str], None] = "0004_subscription_grace_window"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_jobs_user_idempotency_key", "jobs", ["user_id", "idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_jobs_user_idempotency_key", "jobs", type_="unique")
    op.drop_column("jobs", "idempotency_key")
