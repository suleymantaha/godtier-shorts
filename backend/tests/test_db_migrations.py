from __future__ import annotations

from io import StringIO
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.tests.test_db_models import EXPECTED_TABLES


ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", "postgresql+asyncpg://godtier:test@postgres:5432/godtier")
    return config


def _offline_sql(revision: str, *, downgrade: bool = False) -> str:
    output = StringIO()
    config = _alembic_config()
    config.output_buffer = output
    if downgrade:
        command.downgrade(config, revision, sql=True)
    else:
        command.upgrade(config, revision, sql=True)
    return output.getvalue().lower()


def test_subscription_grace_migration_is_the_schema_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert script.get_heads() == ["0004_subscription_grace_window"]


def test_initial_upgrade_creates_every_production_table() -> None:
    sql = _offline_sql("head")

    for table_name in EXPECTED_TABLES:
        assert f"create table {table_name}" in sql


def test_initial_downgrade_removes_every_production_table() -> None:
    sql = _offline_sql("head:base", downgrade=True)

    for table_name in EXPECTED_TABLES:
        assert f"drop table {table_name}" in sql


@pytest.mark.integration
def test_postgres_upgrade_downgrade_round_trip_has_no_schema_drift() -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for the PostgreSQL migration smoke test")

    config = _alembic_config()
    config.attributes["database_url"] = database_url

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
