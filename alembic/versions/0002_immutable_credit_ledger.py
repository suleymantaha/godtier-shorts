"""make credit ledger append only

Revision ID: 0002_immutable_credit_ledger
Revises: 0001_production_schema
Create Date: 2026-08-20 23:30:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002_immutable_credit_ledger"
down_revision: Union[str, Sequence[str], None] = "0001_production_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_credit_ledger_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'credit_ledger is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_ledger_append_only
        BEFORE UPDATE OR DELETE ON credit_ledger
        FOR EACH ROW EXECUTE FUNCTION prevent_credit_ledger_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS credit_ledger_append_only ON credit_ledger")
    op.execute("DROP FUNCTION IF EXISTS prevent_credit_ledger_mutation()")
