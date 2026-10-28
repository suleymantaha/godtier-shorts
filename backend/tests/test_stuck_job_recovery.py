from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import Job, JobStatus, JobType, Project, SourceType, User, UserStatus
from backend.services.queue.client import QueueDispatchError
from backend.tests.test_gpu_recovery_deletion_fence import AsyncSessionAdapter
from backend.workers import gpu_worker
from backend.workers.gpu_worker import recover_stuck_jobs


class FakeStore:
    async def claim_stuck(self, stale_after_seconds):
        assert stale_after_seconds == 300
        return [uuid4(), uuid4()]


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_gpu_job(self, job_id):
        self.jobs.append(job_id)


def test_stuck_jobs_are_claimed_from_postgres_and_requeued() -> None:
    queue = FakeQueue()
    count = asyncio.run(recover_stuck_jobs(FakeStore(), queue, stale_after_seconds=300))

    assert count == 2
    assert len(queue.jobs) == 2


@pytest.fixture
def recovery_database(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    user_id, project_id = uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=user_id, clerk_subject=str(user_id), status=UserStatus.ACTIVE))
        session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                            source_ref="private", source_fingerprint="private"))
        for _ in range(12):
            session.add(Job(id=uuid4(), user_id=user_id, project_id=project_id,
                            type=JobType.FULL_RENDER, status=JobStatus.QUEUED,
                            request={}, reserved_credits=4))
    monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: lambda: AsyncSessionAdapter(engine))
    yield engine
    engine.dispose()


@pytest.mark.parametrize("candidate_count", [2, 3])
def test_healthy_enqueue_delays_yield_remaining_work_without_timeout(recovery_database, candidate_count):
    engine = recovery_database
    with Session(engine) as session, session.begin():
        jobs = list(session.scalars(select(Job)))
        for job in jobs[candidate_count:]:
            job.status = JobStatus.CANCELLED
    queue = FakeQueue()
    async def enqueue(job_id):
        await asyncio.sleep(2.6)
        queue.jobs.append(job_id)
    queue.enqueue_gpu_job = enqueue
    assert asyncio.run(gpu_worker.recover_dispatchable_jobs(queue)) == 2
    assert len(queue.jobs) == 2


def test_recovery_bounds_batch_and_next_heartbeat_drains_backlog(recovery_database):
    queue = FakeQueue()
    assert asyncio.run(gpu_worker.recover_dispatchable_jobs(queue)) == 10
    first = set(queue.jobs)
    # Workers claim these after recovery commits; the next heartbeat sees the rest.
    with Session(recovery_database) as session, session.begin():
        for job in session.scalars(select(Job).where(Job.id.in_(first))):
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
    assert asyncio.run(gpu_worker.recover_dispatchable_jobs(queue)) == 2
    assert len(set(queue.jobs)) == 12


def test_oldest_job_is_not_starved_by_lower_user_ids_replenishing(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    users = [UUID(int=index + 1) for index in range(11)]
    projects, oldest_job = {user_id: uuid4() for user_id in users}, uuid4()
    now = datetime.now(timezone.utc)
    with Session(engine) as session, session.begin():
        for user_id in users:
            session.add(User(id=user_id, clerk_subject=str(user_id), status=UserStatus.ACTIVE))
            session.add(Project(id=projects[user_id], user_id=user_id, source_type=SourceType.UPLOAD,
                                source_ref="private", source_fingerprint="private"))
        session.add(Job(id=oldest_job, user_id=users[-1], project_id=projects[users[-1]],
                        type=JobType.FULL_RENDER, status=JobStatus.QUEUED, request={},
                        reserved_credits=4, created_at=now - timedelta(hours=1)))
    monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: lambda: AsyncSessionAdapter(engine))
    queue = FakeQueue()
    try:
        for _ in range(3):
            with Session(engine) as session, session.begin():
                for user_id in users[:10]:
                    session.add(Job(id=uuid4(), user_id=user_id, project_id=projects[user_id],
                                    type=JobType.FULL_RENDER, status=JobStatus.QUEUED,
                                    request={}, reserved_credits=4, created_at=now))
            asyncio.run(gpu_worker.recover_dispatchable_jobs(queue))
            with Session(engine) as session, session.begin():
                for job in session.scalars(select(Job).where(Job.id.in_(queue.jobs))):
                    job.status = JobStatus.COMPLETED
        assert oldest_job in queue.jobs
    finally:
        engine.dispose()


@pytest.mark.parametrize("error", [TimeoutError, QueueDispatchError])
def test_startup_keeps_heartbeat_retry_after_initial_dispatch_failure(monkeypatch, error):
    async def scenario():
        recovered, calls = asyncio.Event(), []
        async def reconcile():
            return 0
        async def recover(_queue, **_kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise error("temporary dispatch failure")
            recovered.set()
            return 0
        class Redis:
            async def set(self, *args, **kwargs):
                pass
        monkeypatch.setattr(gpu_worker, "configure_logging", lambda *args: None)
        monkeypatch.setattr(gpu_worker, "configure_error_reporting", lambda: None)
        monkeypatch.setattr(gpu_worker, "capture_exception", lambda exc: None)
        monkeypatch.setattr(gpu_worker, "reconcile_failed_reservations", reconcile)
        monkeypatch.setattr(gpu_worker, "recover_dispatchable_jobs", recover)
        ctx = {"gpu_runner": object(), "redis": Redis()}
        await gpu_worker.startup(ctx)
        try:
            await asyncio.wait_for(recovered.wait(), 1)
            assert len(calls) == 2
        finally:
            await gpu_worker.shutdown(ctx)
    asyncio.run(scenario())
