"""Persist the account deletion fence and verified completion timestamp."""
from alembic import op
import sqlalchemy as sa

revision = "0008_account_deletion"
down_revision = "0007_immutable_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("data_purged_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "data_purged_at")
    op.drop_column("users", "deletion_requested_at")
