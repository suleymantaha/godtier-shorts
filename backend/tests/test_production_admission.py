from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.db.models import Job, JobStatus, UserStatus
from backend.services.queue import job_service
from backend.workers import gpu_tasks, gpu_worker


class Session:
    def __init__(self, results):
        self.results = iter(results)
        self.statements = []
        self.added = []
        self.committed = False
        self.rolled_back = False
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    @asynccontextmanager
    async def begin(self):
        try:
            yield
        except BaseException:
            self.rolled_back = True
            raise
        else:
            self.committed = True
    async def scalar(self, statement):
        self.statements.append(statement)
        return next(self.results)
    def add(self, row): self.added.append(row)
    async def flush(self): pass


def test_job_creation_and_reservation_share_commit_and_account_lock(monkeypatch):
    session = Session([SimpleNamespace(status=UserStatus.ACTIVE), None, 0])
    monkeypatch.setattr(job_service, "get_session_factory", lambda: lambda: session)
    async def reserve(s, user_id, amount, job_id, key):
        assert s is session and not session.committed
        assert any(isinstance(item, Job) and item.id == job_id for item in session.added)
        assert amount == 20
    monkeypatch.setattr(job_service.ledger, "reserve_in_session", reserve)
    result = asyncio.run(job_service.SqlAlchemyJobRepository().create_queued(user_id=uuid4(), project_id=uuid4(), job_type="full_render", request={}, idempotency_key="one", estimated_credits=20, max_active_jobs=1))
    assert session.committed and result.reserved
    assert session.statements[0]._for_update_arg is not None


def test_reservation_crash_rolls_back_queued_job(monkeypatch):
    session = Session([SimpleNamespace(status=UserStatus.ACTIVE), None])
    monkeypatch.setattr(job_service, "get_session_factory", lambda: lambda: session)
    async def crash(*_): raise RuntimeError("simulated crash before reservation")
    monkeypatch.setattr(job_service.ledger, "reserve_in_session", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        asyncio.run(job_service.SqlAlchemyJobRepository().create_queued(user_id=uuid4(), project_id=uuid4(), job_type="full_render", request={}, idempotency_key="one", estimated_credits=20))
    assert session.rolled_back and not session.committed


def test_active_quota_is_checked_under_account_lock_before_create(monkeypatch):
    session = Session([SimpleNamespace(status=UserStatus.ACTIVE), None, 1])
    monkeypatch.setattr(job_service, "get_session_factory", lambda: lambda: session)
    reserve = AsyncMock()
    monkeypatch.setattr(job_service.ledger, "reserve_in_session", reserve)
    with pytest.raises(job_service.ActiveJobLimitReached):
        asyncio.run(job_service.SqlAlchemyJobRepository().create_queued(user_id=uuid4(), project_id=uuid4(), job_type="full_render", request={}, idempotency_key="one", estimated_credits=20, max_active_jobs=1))
    assert session.statements[0]._for_update_arg is not None
    assert not session.added
    reserve.assert_not_awaited()


def test_worker_refuses_unreserved_job_before_runner(monkeypatch):
    job = SimpleNamespace(status=JobStatus.QUEUED, reserved_credits=0)
    session = Session([uuid4(), SimpleNamespace(status=UserStatus.ACTIVE), job])
    monkeypatch.setattr(gpu_tasks, "get_session_factory", lambda: lambda: session)
    with pytest.raises(gpu_tasks.DeterministicJobError, match="no active credit"):
        asyncio.run(gpu_tasks.SqlAlchemyWorkerJobStore().claim(uuid4()))
    assert job.status is JobStatus.QUEUED


def test_periodic_recovery_filters_jobs_without_reservation(monkeypatch):
    session = Session([])
    statements = []
    async def scalars(statement):
        statements.append(statement)
        return SimpleNamespace(all=lambda: [])
    session.scalars = scalars
    monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: lambda: session)
    asyncio.run(gpu_worker.recover_dispatchable_jobs(SimpleNamespace(enqueue_gpu_job=AsyncMock())))
    assert "jobs.reserved_credits >" in str(statements[0])


def test_recovery_completes_settled_job_without_dispatching_again(monkeypatch):
    job = SimpleNamespace(id=uuid4(), status=JobStatus.PROCESSING, reserved_credits=0, settled_credits=20)
    session = Session([])
    async def scalars(_statement):
        return SimpleNamespace(all=lambda: [job])
    session.scalars = scalars
    monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: lambda: session)
    queue = SimpleNamespace(enqueue_gpu_job=AsyncMock())
    assert asyncio.run(gpu_worker.recover_dispatchable_jobs(queue)) == 0
    assert session.committed and job.status is JobStatus.COMPLETED
    assert job.progress == 100
    queue.enqueue_gpu_job.assert_not_awaited()


def test_deleted_account_cannot_publish_worker_output(monkeypatch):
    from backend.workers import production_runner
    session = Session([SimpleNamespace(status=UserStatus.DELETED)])
    monkeypatch.setattr(production_runner, "get_session_factory", lambda: lambda: session)
    upload = AsyncMock()
    context = SimpleNamespace(user_id=uuid4(), job_id=uuid4())
    with pytest.raises(gpu_tasks.DeterministicJobError, match="Account is not active"):
        asyncio.run(production_runner.SqlAlchemyProductionJobRepository().publish_output(context=context, upload=upload))
    upload.assert_not_awaited()


def test_publish_cancellation_retains_fence_until_upload_stops(monkeypatch, tmp_path):
    from backend.workers import production_runner
    async def scenario():
        session = Session([
            SimpleNamespace(status=UserStatus.ACTIVE), SimpleNamespace(status=JobStatus.PROCESSING), None,
            SimpleNamespace(status=UserStatus.ACTIVE), SimpleNamespace(status=JobStatus.PROCESSING), None,
        ])
        monkeypatch.setattr(production_runner, "get_session_factory", lambda: lambda: session)
        reserve = AsyncMock()
        monkeypatch.setattr(production_runner, "reserve_storage_in_session", reserve)
        source = tmp_path / "render.mp4"
        source.write_bytes(b"rendered output")
        started, finish = asyncio.Event(), asyncio.Event()
        async def upload():
            started.set()
            await finish.wait()
        task = asyncio.create_task(production_runner.SqlAlchemyProductionJobRepository().publish_output(
            context=SimpleNamespace(user_id=uuid4(), job_id=uuid4(), project_id=uuid4()),
            upload=upload, source=source, storage_key="outputs/test/render.mp4",
            content_type="video/mp4", sha256="test-sha256",
        ))
        await started.wait()
        reserve.assert_awaited_once()
        assert session.committed
        task.cancel()
        await asyncio.sleep(0)
        assert not session.rolled_back and not task.done()
        finish.set()
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(scenario())
