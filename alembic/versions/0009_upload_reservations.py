"""Account storage admission before issuing private PUT URLs."""
from alembic import op
import sqlalchemy as sa

revision = "0009_upload_reservations"
down_revision = "0008_account_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_reservations",
        sa.Column("storage_key", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_upload_reservations_upload_size_positive")),
    )
    op.create_index("ix_upload_reservations_user_id", "upload_reservations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_upload_reservations_user_id", table_name="upload_reservations")
    op.drop_table("upload_reservations")
