"""Recovery must not dispatch or mutate jobs after an account deletion fence."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import Job, JobEvent, JobStatus, JobType, Project, SourceType, User, UserStatus
from backend.workers import gpu_worker


class AsyncSessionAdapter:
    def __init__(self, engine):
        self.session = Session(engine, expire_on_commit=False)
        self.next_event_id = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.session.close()

    @asynccontextmanager
    async def begin(self):
        with self.session.begin():
            yield

    async def scalars(self, statement):
        return self.session.scalars(statement)

    def add(self, instance):
        # SQLite does not autoincrement the PostgreSQL BIGINT event identity.
        if isinstance(instance, JobEvent):
            instance.id = self.next_event_id
            self.next_event_id += 1
        self.session.add(instance)


@pytest.mark.parametrize("status,reserved,settled", [
    (JobStatus.QUEUED, 4, 0),
    (JobStatus.PROCESSING, 4, 0),
    (JobStatus.PROCESSING, 0, 4),
])
def test_recovery_preserves_deleted_account_fence(monkeypatch, status, reserved, settled):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    active_user, deleted_user = uuid4(), uuid4()
    active_job, deleted_job = uuid4(), uuid4()
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    with Session(engine) as session, session.begin():
        for user_id, job_id, user_status in (
            (active_user, active_job, UserStatus.ACTIVE),
            (deleted_user, deleted_job, UserStatus.DELETED),
        ):
            project_id = uuid4()
            session.add(User(id=user_id, clerk_subject=str(user_id), status=user_status))
            session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                                source_ref="private", source_fingerprint="private"))
            session.add(Job(id=job_id, user_id=user_id, project_id=project_id,
                            type=JobType.FULL_RENDER, status=status, request={}, reserved_credits=reserved,
                            settled_credits=settled, started_at=stale))

    monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: lambda: AsyncSessionAdapter(engine))
    dispatched = []

    class Queue:
        async def enqueue_gpu_job(self, job_id):
            dispatched.append(job_id)

    try:
        count = asyncio.run(gpu_worker.recover_dispatchable_jobs(Queue()))
        assert deleted_job not in dispatched
        assert dispatched == ([active_job] if reserved else [])
        assert count == (1 if reserved else 0)
        with Session(engine) as session:
            assert session.get(Job, deleted_job).status is status
            assert session.get(Job, active_job).status is (
                JobStatus.QUEUED if reserved else JobStatus.COMPLETED
            )
    finally:
        engine.dispose()

@pytest.mark.parametrize("fence_first,reserved,settled", [
    (True, 4, 0), (True, 0, 4), (False, 4, 0), (False, 0, 4), ("enqueue", 4, 0),
])
def test_postgres_recovery_serializes_account_fence(monkeypatch, fence_first, reserved, settled):
    url = os.getenv("RECOVERY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RECOVERY_TEST_DATABASE_URL is required")
    async def scenario():
        schema = f"recovery_test_{uuid4().hex}"
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        user_id, project_id, job_id = uuid4(), uuid4(), uuid4()
        selected, resume = asyncio.Event(), asyncio.Event()
        class PausedRecoverySession(AsyncSession):
            async def scalars(self, statement, *args, **kwargs):
                result = await super().scalars(statement, *args, **kwargs)
                if fence_first is False and statement.column_descriptions[0].get("expr") is Job and statement._for_update_arg is not None:
                    selected.set()
                    await resume.wait()
                return result
        recovery_factory = async_sessionmaker(engine, class_=PausedRecoverySession, expire_on_commit=False)
        dispatched = []
        class Queue:
            async def enqueue_gpu_job(self, job_id):
                if fence_first == "enqueue":
                    selected.set()
                    await resume.wait()
                dispatched.append(job_id)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as session, session.begin():
                session.add(User(id=user_id, clerk_subject=str(user_id), status=UserStatus.ACTIVE))
                await session.flush()
                session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                                    source_ref="private", source_fingerprint="private"))
                await session.flush()
                session.add(Job(id=job_id, user_id=user_id, project_id=project_id, type=JobType.FULL_RENDER,
                                status=JobStatus.PROCESSING, request={}, reserved_credits=reserved,
                                settled_credits=settled, started_at=datetime.now(timezone.utc) - timedelta(hours=1)))
            monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: factory if fence_first is True else recovery_factory)
            if fence_first is True:
                async with factory() as deletion, deletion.begin():
                    user = await deletion.scalar(select(User).where(User.id == user_id).with_for_update())
                    user.status = UserStatus.DELETED
                    await deletion.flush()
                    assert await asyncio.wait_for(gpu_worker.recover_dispatchable_jobs(Queue()), 5) == 0
                    assert not dispatched
                    async with factory() as check:
                        assert (await check.get(Job, job_id)).status is JobStatus.PROCESSING
            else:
                task = asyncio.create_task(gpu_worker.recover_dispatchable_jobs(Queue()))
                blocked = False
                try:
                    await asyncio.wait_for(selected.wait(), 5)
                    try:
                        async with factory() as deletion, deletion.begin():
                            user = await deletion.scalar(select(User).where(User.id == user_id).with_for_update(nowait=True))
                            user.status = UserStatus.DELETED
                    except DBAPIError as exc:
                        assert exc.orig.sqlstate == "55P03"
                        blocked = True
                finally:
                    resume.set()
                    await asyncio.wait_for(task, 5)
                assert blocked, "Account deletion committed while recovery held only a Job lock"
        finally:
            assert schema.startswith("recovery_test_") and len(schema) == 46
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["enqueue", "commit", "timeout"])
def test_recovery_dispatch_failure_rolls_back_mutation(monkeypatch, failure):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    user_id, project_id, job_id = uuid4(), uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=user_id, clerk_subject=str(user_id), status=UserStatus.ACTIVE))
        session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                            source_ref="private", source_fingerprint="private"))
        session.add(Job(id=job_id, user_id=user_id, project_id=project_id, type=JobType.FULL_RENDER,
                        status=JobStatus.PROCESSING, request={}, reserved_credits=4,
                        started_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    class FailingCommitSession(AsyncSessionAdapter):
        @asynccontextmanager
        async def begin(self):
            with self.session.begin():
                yield
                if failure == "commit":
                    raise RuntimeError("commit failed")
    dispatched = []
    class Queue:
        async def enqueue_gpu_job(self, job_id):
            dispatched.append(job_id)
            if failure == "timeout":
                await asyncio.Event().wait()
            if failure == "enqueue":
                raise RuntimeError("enqueue failed")
    monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: lambda: FailingCommitSession(engine))
    try:
        with pytest.raises(TimeoutError if failure == "timeout" else RuntimeError):
            asyncio.run(gpu_worker.recover_dispatchable_jobs(Queue()))
        assert dispatched == [job_id]
        with Session(engine) as session:
            assert session.get(Job, job_id).status is JobStatus.PROCESSING
    finally:
        engine.dispose()
