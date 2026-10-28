import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import (Asset, AssetKind, CreditLedgerEntry, Job, JobStatus, JobType,
                               LedgerKind, Project, SourceType, Subscription, SubscriptionStatus, User, UserStatus)
from backend.services import account_purge as purge


class AsyncSessionAdapter:
    def __init__(self, engine):
        self.session = Session(engine, expire_on_commit=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.session.close()

    @asynccontextmanager
    async def begin(self):
        with self.session.begin():
            yield

    async def scalar(self, stmt):
        return self.session.scalar(stmt)

    async def scalars(self, stmt):
        return self.session.scalars(stmt)

    async def execute(self, stmt):
        return self.session.execute(stmt)


@pytest.fixture
def production(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    user_id, foreign_id, project_id, foreign_project_id, job_id = [uuid4() for _ in range(5)]
    key = f"uploads/{user_id}/source.mp4"
    foreign_key = f"outputs/{foreign_id}/private.mp4"
    with Session(engine) as session, session.begin():
        session.add_all([User(id=user_id, clerk_subject="owner", status=UserStatus.ACTIVE),
                         User(id=foreign_id, clerk_subject="foreign", status=UserStatus.ACTIVE)])
        session.add_all([Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                                source_ref=key, source_fingerprint="private", title="private"),
                         Project(id=foreign_project_id, user_id=foreign_id, source_type=SourceType.UPLOAD,
                                 source_ref=foreign_key, source_fingerprint="foreign")])
        session.add(Job(id=job_id, user_id=user_id, project_id=project_id, type=JobType.FULL_RENDER,
                        status=JobStatus.COMPLETED, request={"private": "text"}, reserved_credits=0))
        session.add(Asset(id=uuid4(), user_id=user_id, project_id=project_id, storage_key=key,
                          kind=AssetKind.SOURCE, mime_type="video/mp4", size_bytes=1, sha256="private"))
        session.add(CreditLedgerEntry(id=uuid4(), user_id=user_id, job_id=job_id,
                                     kind=LedgerKind.GRANT, amount=20, idempotency_key="keep-financial-history"))
    monkeypatch.setattr(purge, "get_session_factory", lambda: lambda: AsyncSessionAdapter(engine))
    state = SimpleNamespace(engine=engine, user_id=user_id, job_id=job_id, key=key,
                            objects={key, f"outputs/{user_id}/orphan.mp4", foreign_key}, fail=False,
                            cancelled=[], local_calls=[])

    class Remote:
        async def cancel(self, key):
            state.cancelled.append(key)
            if state.fail:
                raise RuntimeError("external unavailable")
            return True

        async def keys(self, prefix):
            return [key for key in state.objects if key.startswith(prefix)]

        async def delete(self, key):
            if state.fail:
                raise RuntimeError("external unavailable")
            state.objects.discard(key)

    @asynccontextmanager
    async def remote():
        yield Remote()

    monkeypatch.setattr(purge, "_production_remote", remote)
    return state


def expire_window(state):
    with Session(state.engine) as session, session.begin():
        user = session.get(User, state.user_id)
        user.deletion_requested_at = datetime.now(timezone.utc) - timedelta(seconds=1000)


def test_production_tombstone_waits_for_presigned_window_and_retries(production):
    first = asyncio.run(purge._purge_production("owner"))
    assert first["status"] == "deletion_pending"
    with Session(production.engine) as session:
        assert session.get(User, production.user_id).status is UserStatus.DELETED
        assert session.get(User, production.user_id).data_purged_at is None
        assert session.scalar(select(Asset)) is not None
    expire_window(production)
    final = asyncio.run(purge._purge_production("owner"))
    assert final["status"] == "deletion_pending"
    assert final["reason"] == "storage_finalization_unverified"
    assert production.objects == {next(key for key in production.objects if "private.mp4" in key)}
    with Session(production.engine) as session:
        assert session.scalar(select(Asset)) is None
        assert session.scalar(select(CreditLedgerEntry)).idempotency_key == "keep-financial-history"
        assert session.get(Job, production.job_id).request == {}
        assert session.get(User, production.user_id).data_purged_at is None
        assert session.scalar(select(Project).where(Project.user_id == production.user_id)).source_ref == ""
        assert session.scalar(select(Project).where(Project.user_id != production.user_id)).source_ref.endswith("private.mp4")
    assert asyncio.run(purge._purge_production("owner"))["reason"] == "storage_finalization_unverified"


def test_remote_failure_is_pending_and_retains_retry_inventory(production):
    asyncio.run(purge._purge_production("owner"))
    expire_window(production)
    production.fail = True
    result = asyncio.run(purge._purge_production("owner"))
    assert result["status"] == "deletion_pending"
    with Session(production.engine) as session:
        assert session.scalar(select(Asset)) is not None
        assert session.get(User, production.user_id).data_purged_at is None
    production.fail = False
    assert asyncio.run(purge._purge_production("owner"))["reason"] == "storage_finalization_unverified"


def test_late_put_after_empty_listing_is_cleaned_on_retry_without_claiming_finality(production):
    asyncio.run(purge._purge_production("owner"))
    expire_window(production)
    assert asyncio.run(purge._purge_production("owner"))["reason"] == "storage_finalization_unverified"
    # A PUT that started before URL expiry may finish after cleanup and asset scrubbing.
    late_key = f"uploads/{production.user_id}/late-source.mp4"
    production.objects.add(late_key)

    result = asyncio.run(purge._purge_production("owner"))

    assert result["status"] == "deletion_pending"
    assert result["reason"] == "storage_finalization_unverified"
    assert late_key not in production.objects
    assert any("private.mp4" in key for key in production.objects)
    with Session(production.engine) as session:
        user = session.get(User, production.user_id)
        assert user.status is UserStatus.DELETED
        assert user.data_purged_at is None


def test_foreign_storage_key_fails_closed(production):
    asyncio.run(purge._purge_production("owner"))
    expire_window(production)
    with Session(production.engine) as session, session.begin():
        session.scalar(select(Asset)).storage_key = "uploads/foreign/private.mp4"
    assert asyncio.run(purge._purge_production("owner"))["status"] == "deletion_pending"
    assert production.key in production.objects


def test_active_subscription_requires_separate_cancellation_before_fencing(production):
    with Session(production.engine) as session, session.begin():
        session.add(Subscription(id=uuid4(), user_id=production.user_id, plan_id=uuid4(),
                                 provider_subscription_ref="sub-active", status=SubscriptionStatus.ACTIVE))
    result = asyncio.run(purge._purge_production("owner"))
    assert result["reason"] == "subscription_cancellation_required"
    assert not result["deletion_fenced"]
    with Session(production.engine) as session:
        assert session.get(User, production.user_id).status is UserStatus.ACTIVE


def test_worker_abort_failure_keeps_inventory_and_returns_pending(production):
    with Session(production.engine) as session, session.begin():
        session.get(Job, production.job_id).status = JobStatus.PROCESSING
    production.fail = True
    assert asyncio.run(purge._purge_production("owner"))["status"] == "deletion_pending"
    with Session(production.engine) as session:
        assert session.get(Job, production.job_id).status is JobStatus.PROCESSING
        assert session.scalar(select(Asset)) is not None


def test_queued_job_cancellation_releases_reservation_without_deleting_ledger(monkeypatch, production):
    from backend.services.billing import ledger

    with Session(production.engine) as session, session.begin():
        job = session.get(Job, production.job_id)
        job.status, job.reserved_credits = JobStatus.QUEUED, 4
    released = []

    async def release(*args):
        released.append(args)

    monkeypatch.setattr(ledger, "release", release)
    asyncio.run(purge._purge_production("owner"))
    assert released == [(production.user_id, production.job_id, f"release:cancel:{production.job_id}")]
    with Session(production.engine) as session:
        assert session.get(Job, production.job_id).status is JobStatus.CANCELLED
        assert session.scalar(select(CreditLedgerEntry)) is not None


def test_lost_tombstone_commit_ack_recovers_fence_from_database(monkeypatch, production):
    class LostCommitAcknowledgment(AsyncSessionAdapter):
        @asynccontextmanager
        async def begin(self):
            with self.session.begin():
                yield
            raise RuntimeError("commit acknowledgment lost")

    monkeypatch.setattr(purge, "get_session_factory", lambda: lambda: LostCommitAcknowledgment(production.engine))
    result = asyncio.run(purge._purge_production("owner"))
    assert result["status"] == "deletion_pending"
    assert result["deletion_fenced"] is True
    with Session(production.engine) as session:
        assert session.get(User, production.user_id).status is UserStatus.DELETED
