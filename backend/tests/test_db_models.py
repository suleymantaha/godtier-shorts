from __future__ import annotations

import asyncio

from sqlalchemy import CheckConstraint, UniqueConstraint, Uuid
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import Base
from backend.db.session import create_session_factory


EXPECTED_TABLES = {
    "assets",
    "audit_logs",
    "billing_checkout_sessions",
    "credit_ledger",
    "credit_wallets",
    "job_events",
    "jobs",
    "payments",
    "plans",
    "projects",
    "risk_events",
    "subscriptions",
    "trial_entitlements",
    "users",
    "webhook_events",
}

UUID_PRIMARY_KEY_TABLES = EXPECTED_TABLES - {
    "audit_logs",
    "credit_wallets",
    "job_events",
    "risk_events",
}


def _unique_column_sets(table_name: str) -> set[frozenset[str]]:
    table = Base.metadata.tables[table_name]
    return {
        frozenset(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _check_names(table_name: str) -> set[str | None]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_metadata_contains_the_production_source_of_truth_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_durable_entities_use_database_generated_uuid_primary_keys() -> None:
    for table_name in UUID_PRIMARY_KEY_TABLES:
        primary_key = list(Base.metadata.tables[table_name].primary_key.columns)

        assert len(primary_key) == 1, table_name
        assert isinstance(primary_key[0].type, Uuid), table_name
        assert primary_key[0].server_default is not None, table_name


def test_financial_and_provider_idempotency_is_enforced_by_unique_constraints() -> None:
    assert frozenset({"clerk_subject"}) in _unique_column_sets("users")
    assert frozenset({"code"}) in _unique_column_sets("plans")
    assert frozenset({"provider_subscription_ref"}) in _unique_column_sets("subscriptions")
    assert frozenset({"provider_payment_id"}) in _unique_column_sets("payments")
    assert frozenset({"idempotency_key"}) in _unique_column_sets("credit_ledger")
    assert frozenset({"provider", "provider_event_key"}) in _unique_column_sets("webhook_events")
    assert frozenset({"storage_key"}) in _unique_column_sets("assets")
    assert frozenset({"idempotency_key_hash"}) in _unique_column_sets("billing_checkout_sessions")
    assert frozenset({"provider_token_hash"}) in _unique_column_sets("billing_checkout_sessions")


def test_ownership_and_billing_foreign_keys_cannot_be_bypassed() -> None:
    expected_targets = {
        ("projects", "user_id"): "users.id",
        ("jobs", "user_id"): "users.id",
        ("jobs", "project_id"): "projects.id",
        ("assets", "user_id"): "users.id",
        ("assets", "project_id"): "projects.id",
        ("assets", "job_id"): "jobs.id",
        ("subscriptions", "user_id"): "users.id",
        ("subscriptions", "plan_id"): "plans.id",
        ("billing_checkout_sessions", "user_id"): "users.id",
        ("billing_checkout_sessions", "plan_id"): "plans.id",
        ("payments", "user_id"): "users.id",
        ("credit_wallets", "user_id"): "users.id",
        ("credit_ledger", "user_id"): "users.id",
        ("credit_ledger", "job_id"): "jobs.id",
        ("credit_ledger", "payment_id"): "payments.id",
        ("job_events", "job_id"): "jobs.id",
        ("trial_entitlements", "user_id"): "users.id",
        ("risk_events", "user_id"): "users.id",
    }

    actual_targets: dict[tuple[str, str], str] = {}
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            actual_targets[(table.name, foreign_key.parent.name)] = foreign_key.target_fullname

    for key, target in expected_targets.items():
        assert actual_targets[key] == target


def test_database_constraints_reject_impossible_wallet_and_job_state() -> None:
    assert {"ck_credit_wallets_available_nonnegative", "ck_credit_wallets_reserved_nonnegative"} <= _check_names(
        "credit_wallets"
    )
    assert "ck_jobs_progress_range" in _check_names("jobs")
    assert {"ck_plans_monthly_price_nonnegative", "ck_plans_monthly_credits_nonnegative"} <= _check_names("plans")


def test_enum_columns_persist_contract_values_instead_of_python_member_names() -> None:
    expected_values = {
        ("users", "status"): ["active", "suspended", "deleted"],
        ("users", "role"): ["user", "support", "admin"],
        ("subscriptions", "status"): ["pending", "active", "past_due", "cancelled", "expired"],
        ("credit_ledger", "kind"): ["grant", "reserve", "release", "settle", "refund", "adjustment", "expire"],
        ("jobs", "status"): ["queued", "processing", "completed", "error", "cancelled", "review_required"],
    }

    for (table_name, column_name), values in expected_values.items():
        assert Base.metadata.tables[table_name].c[column_name].type.enums == values


def test_subscription_schema_tracks_past_due_grace_window() -> None:
    assert "entitlement_grace_until" in Base.metadata.tables["subscriptions"].c


def test_session_factory_creates_one_non_expiring_async_session_per_call() -> None:
    factory = create_session_factory("postgresql+asyncpg://godtier:test@localhost:5432/godtier")

    first = factory()
    second = factory()

    async def close_resources() -> None:
        await first.close()
        await second.close()
        await factory.kw["bind"].dispose()

    assert isinstance(first, AsyncSession)
    assert isinstance(second, AsyncSession)
    assert first is not second
    assert first.sync_session.expire_on_commit is False
    asyncio.run(close_resources())
