from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Coroutine, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from backend.db.models import (
    CreditLedgerEntry,
    CreditWallet,
    Job,
    JobStatus,
    JobType,
    LedgerKind,
    Project,
    SourceType,
    User,
    UserRole,
    UserStatus,
)
from backend.db.session import create_session_factory, get_session_factory
from backend.services.billing import ledger


ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for credit ledger integration tests")
    return database_url


def _prepare_database(database_url: str) -> None:
    config = Config(ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


async def _reset_billing_data(database_url: str) -> None:
    factory = create_session_factory(database_url)
    async with factory() as session:
        await session.execute(
            text(
                "TRUNCATE credit_ledger, jobs, projects, credit_wallets, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    await factory.kw["bind"].dispose()


async def _create_user_and_jobs(database_url: str, *, job_count: int = 1) -> tuple[UUID, list[UUID]]:
    factory = create_session_factory(database_url)
    user_id = uuid4()
    project_id = uuid4()
    job_ids = [uuid4() for _ in range(job_count)]
    async with factory() as session:
        session.add(
            User(
                id=user_id,
                clerk_subject=f"user_{user_id.hex}",
                status=UserStatus.ACTIVE,
                role=UserRole.USER,
            )
        )
        await session.flush()
        session.add(
            Project(
                id=project_id,
                user_id=user_id,
                source_type=SourceType.UPLOAD,
                source_ref="test-source.mp4",
                source_fingerprint="a" * 64,
            )
        )
        await session.flush()
        session.add_all(
            Job(
                id=job_id,
                user_id=user_id,
                project_id=project_id,
                type=JobType.FULL_RENDER,
                status=JobStatus.QUEUED,
                request={},
            )
            for job_id in job_ids
        )
        await session.commit()
    await factory.kw["bind"].dispose()
    return user_id, job_ids


async def _wallet_and_entries(
    database_url: str,
    user_id: UUID,
) -> tuple[CreditWallet, list[CreditLedgerEntry]]:
    factory = create_session_factory(database_url)
    async with factory() as session:
        wallet = await session.get(CreditWallet, user_id)
        entries = list(
            (
                await session.scalars(
                    select(CreditLedgerEntry)
                    .where(CreditLedgerEntry.user_id == user_id)
                    .order_by(CreditLedgerEntry.created_at, CreditLedgerEntry.id)
                )
            ).all()
        )
    await factory.kw["bind"].dispose()
    assert wallet is not None
    return wallet, entries


@pytest.fixture(scope="module", autouse=True)
def prepared_database() -> Iterator[Callable[[Coroutine[Any, Any, Any]], Any]]:
    database_url = _database_url()
    _prepare_database(database_url)
    asyncio.run(_reset_billing_data(database_url))
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    runner = asyncio.Runner()
    yield runner.run
    runner.run(get_session_factory(database_url).kw["bind"].dispose())
    runner.close()
    if previous_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database_url
    asyncio.run(_reset_billing_data(database_url))


@pytest.mark.integration
def test_grant_is_idempotent_and_changes_balance_once(prepared_database) -> None:
    async def scenario() -> None:
        database_url = _database_url()
        user_id, _ = await _create_user_and_jobs(database_url)

        await ledger.grant(user_id, 100, "grant:subscription:1", {"source": "subscription"})
        await ledger.grant(user_id, 100, "grant:subscription:1", {"source": "subscription"})

        wallet, entries = await _wallet_and_entries(database_url, user_id)
        assert (wallet.available, wallet.reserved) == (100, 0)
        assert [(entry.kind, entry.amount) for entry in entries] == [(LedgerKind.GRANT, 100)]

    prepared_database(scenario())


@pytest.mark.integration
def test_concurrent_reservations_cannot_overspend_one_wallet(prepared_database) -> None:
    async def scenario() -> None:
        database_url = _database_url()
        user_id, job_ids = await _create_user_and_jobs(database_url, job_count=2)
        await ledger.grant(user_id, 100, "grant:concurrency", {})

        results = await asyncio.gather(
            ledger.reserve(user_id, 80, job_ids[0], "reserve:job:1"),
            ledger.reserve(user_id, 80, job_ids[1], "reserve:job:2"),
            return_exceptions=True,
        )

        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, ledger.InsufficientCredits) for result in results) == 1
        wallet, entries = await _wallet_and_entries(database_url, user_id)
        assert (wallet.available, wallet.reserved) == (20, 80)
        assert sum(entry.kind is LedgerKind.RESERVE for entry in entries) == 1

        factory = create_session_factory(database_url)
        async with factory() as session:
            reserved_amounts = sorted(
                (await session.scalars(select(Job.reserved_credits).where(Job.id.in_(job_ids)))).all()
            )
        await factory.kw["bind"].dispose()
        assert reserved_amounts == [0, 80]

    prepared_database(scenario())


@pytest.mark.integration
def test_settle_charges_actual_usage_and_returns_unused_reservation(prepared_database) -> None:
    async def scenario() -> None:
        database_url = _database_url()
        user_id, [job_id] = await _create_user_and_jobs(database_url)
        await ledger.grant(user_id, 100, "grant:settle", {})
        await ledger.reserve(user_id, 80, job_id, "reserve:settle")

        await ledger.settle(user_id, job_id, 60, "settle:job:1")
        await ledger.settle(user_id, job_id, 60, "settle:job:1")

        wallet, entries = await _wallet_and_entries(database_url, user_id)
        assert (wallet.available, wallet.reserved) == (40, 0)
        assert [entry.kind for entry in entries] == [
            LedgerKind.GRANT,
            LedgerKind.RESERVE,
            LedgerKind.SETTLE,
        ]
        factory = create_session_factory(database_url)
        async with factory() as session:
            job = await session.get(Job, job_id)
        await factory.kw["bind"].dispose()
        assert job is not None
        assert (job.reserved_credits, job.settled_credits) == (0, 60)

    prepared_database(scenario())


@pytest.mark.parametrize("terminal_status", [JobStatus.ERROR, JobStatus.CANCELLED])
@pytest.mark.integration
def test_terminal_job_release_returns_the_entire_reservation(
    terminal_status: JobStatus,
    prepared_database,
) -> None:
    async def scenario() -> None:
        database_url = _database_url()
        user_id, [job_id] = await _create_user_and_jobs(database_url)
        await ledger.grant(user_id, 100, f"grant:release:{terminal_status.value}", {})
        await ledger.reserve(user_id, 80, job_id, f"reserve:release:{terminal_status.value}")

        factory = create_session_factory(database_url)
        async with factory() as session:
            job = await session.get(Job, job_id)
            assert job is not None
            job.status = terminal_status
            await session.commit()
        await factory.kw["bind"].dispose()

        key = f"release:job:{terminal_status.value}"
        await ledger.release(user_id, job_id, key)
        await ledger.release(user_id, job_id, key)

        wallet, entries = await _wallet_and_entries(database_url, user_id)
        assert (wallet.available, wallet.reserved) == (100, 0)
        assert sum(entry.kind is LedgerKind.RELEASE for entry in entries) == 1

    prepared_database(scenario())


@pytest.mark.integration
def test_database_rejects_ledger_update_and_delete(prepared_database) -> None:
    async def scenario() -> None:
        database_url = _database_url()
        user_id, _ = await _create_user_and_jobs(database_url)
        await ledger.grant(user_id, 100, "grant:immutable", {})
        factory = create_session_factory(database_url)

        async with factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("UPDATE credit_ledger SET amount = 999 WHERE idempotency_key = 'grant:immutable'")
                )
                await session.commit()
            await session.rollback()

        async with factory() as session:
            with pytest.raises(DBAPIError):
                await session.execute(
                    text("DELETE FROM credit_ledger WHERE idempotency_key = 'grant:immutable'")
                )
                await session.commit()
            await session.rollback()

        async with factory() as session:
            entries = list(
                (
                    await session.scalars(
                        select(CreditLedgerEntry).where(CreditLedgerEntry.user_id == user_id)
                    )
                ).all()
            )
        await factory.kw["bind"].dispose()
        assert len(entries) == 1
        assert entries[0].amount == 100

    prepared_database(scenario())
