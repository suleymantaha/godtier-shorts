"""Real SQL persistence tests; synchronous SQLite behind an async session port.

PostgreSQL row lock scheduling still requires the deployment integration gate.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import BigInteger, create_engine, event, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import Asset, CreditWallet, Job, JobEvent, JobStatus, Project, SourceType, User
from backend.services.queue import job_service
from backend.services.billing import ledger
from backend.workers import gpu_tasks, gpu_worker
from backend.services.storage import validated_uploads


@compiles(BigInteger, "sqlite")
def sqlite_bigint(_type, _compiler, **_kwargs):
    return "INTEGER"


class AsyncSessionPort:
    def __init__(self, engine): self.session = Session(engine, expire_on_commit=False)
    async def __aenter__(self): return self
    async def __aexit__(self, *_): self.session.close()
    @asynccontextmanager
    async def begin(self):
        with self.session.begin(): yield
    async def get(self, model, key): return self.session.get(model, key)
    async def scalar(self, statement): return self.session.scalar(statement)
    async def execute(self, statement): return self.session.execute(statement)
    async def scalars(self, statement): return self.session.scalars(statement)
    async def flush(self): self.session.flush()
    def add(self, row): self.session.add(row)


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://")
    @event.listens_for(engine, "connect")
    def functions(connection, _):
        connection.create_function("gen_random_uuid", 0, lambda: uuid4().hex)
    Base.metadata.create_all(engine)
    user_id, project_id = uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=user_id, clerk_subject=str(user_id)))
        session.flush()
        session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD, source_ref="source", source_fingerprint="a"*64))
        session.add(CreditWallet(user_id=user_id, available=100, reserved=0))
    factory = lambda: AsyncSessionPort(engine)
    for module in (job_service, validated_uploads, ledger, gpu_tasks, gpu_worker):
        monkeypatch.setattr(module, "get_session_factory", lambda: factory)
    yield engine, user_id, project_id
    engine.dispose()


def test_real_sql_creates_job_and_reservation_atomically(database):
    engine, user_id, project_id = database
    result = asyncio.run(job_service.SqlAlchemyJobRepository().create_queued(user_id=user_id, project_id=project_id, job_type="full_render", request={}, idempotency_key="one", estimated_credits=20, max_active_jobs=1))
    with Session(engine) as session:
        assert session.get(Job, result.id).reserved_credits == 20
        wallet = session.get(CreditWallet, user_id)
        assert (wallet.available, wallet.reserved) == (80, 20)


def test_real_sql_reservation_failure_leaves_no_job_or_debit(database, monkeypatch):
    engine, user_id, project_id = database
    async def crash(*_): raise RuntimeError("crash window")
    monkeypatch.setattr(job_service.ledger, "reserve_in_session", crash)
    with pytest.raises(RuntimeError, match="crash window"):
        asyncio.run(job_service.SqlAlchemyJobRepository().create_queued(user_id=user_id, project_id=project_id, job_type="full_render", request={}, idempotency_key="one", estimated_credits=20))
    with Session(engine) as session:
        assert session.scalar(select(Job)) is None
        assert session.get(CreditWallet, user_id).available == 100


def test_real_sql_validated_upload_persists_render_prerequisites_once(database):
    engine, user_id, _ = database
    kwargs = dict(user_id=user_id, storage_key=f"uploads/{user_id}/one.mp4", content_type="video/mp4", size_bytes=100, duration_seconds=13, sha256="a"*64)
    first = asyncio.run(validated_uploads.persist_validated_upload(**kwargs))
    second = asyncio.run(validated_uploads.persist_validated_upload(**kwargs))
    assert first == second
    with Session(engine) as session:
        project = session.get(Project, first)
        asset = session.scalar(select(Asset).where(Asset.project_id == first))
        assert project.duration_seconds == 13
        assert asset.storage_key == kwargs["storage_key"]
        assert len(session.scalars(select(Asset)).all()) == 1


@pytest.mark.parametrize("outcome", ["completed", "failed_before_release"])
def test_real_sql_worker_lifecycle_and_failure_reconciliation(database, outcome):
    engine, user_id, project_id = database
    async def scenario():
        durable = await job_service.SqlAlchemyJobRepository().create_queued(
            user_id=user_id, project_id=project_id, job_type="full_render",
            request={"clips": 2}, idempotency_key="worker-lifecycle", estimated_credits=20,
        )
        store = gpu_tasks.SqlAlchemyWorkerJobStore()
        request = await store.claim(durable.id)
        assert request["_user_id"] == str(user_id)
        assert request["_project_id"] == str(project_id)
        await store.heartbeat(durable.id)
        await store.progress(durable.id, 45, "tracking")
        if outcome == "completed":
            await store.settle(durable.id)
            await store.complete(durable.id)
            # Repeated settlement after a lost acknowledgement cannot charge twice.
            await store.settle(durable.id)
        else:
            await store.fail(durable.id, "RETRY_EXHAUSTED", "storage unavailable")
            # Simulate worker death after failure commit, before release.
            assert await gpu_worker.reconcile_failed_reservations() == 1
            assert await gpu_worker.reconcile_failed_reservations() == 0
            await store.release(durable.id)
        return durable.id
    job_id = asyncio.run(scenario())
    with Session(engine) as session:
        job = session.get(Job, job_id)
        wallet = session.get(CreditWallet, user_id)
        events = session.scalars(select(JobEvent).where(JobEvent.job_id == job_id)).all()
        assert any(item.source == "gpu-worker-heartbeat" for item in events)
        assert any(item.progress == 45 and item.message == "tracking" for item in events)
        assert job.reserved_credits == 0 and wallet.reserved == 0
        if outcome == "completed":
            assert job.status is JobStatus.COMPLETED and job.progress == 100
            assert job.settled_credits == 20 and wallet.available == 80
        else:
            assert job.status is JobStatus.ERROR and job.error_code == "RETRY_EXHAUSTED"
            assert job.error_message == "storage unavailable" and wallet.available == 100
