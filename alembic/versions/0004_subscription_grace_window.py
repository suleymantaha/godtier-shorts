"""add subscription entitlement grace window

Revision ID: 0004_subscription_grace_window
Revises: 0003_billing_checkout_sessions
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_subscription_grace_window"
down_revision: Union[str, Sequence[str], None] = "0003_billing_checkout_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("entitlement_grace_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "entitlement_grace_until")
