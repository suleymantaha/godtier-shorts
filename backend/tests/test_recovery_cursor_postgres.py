"""Bounded recovery scan must progress past locked users between heartbeats."""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models import Job, JobStatus, JobType, Project, SourceType, User, UserStatus
from backend.workers import gpu_worker


def test_heartbeat_cursor_passes_locked_prefix_and_restart_resets_scan(monkeypatch):
    url = os.getenv("RECOVERY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RECOVERY_TEST_DATABASE_URL is required")

    async def scenario():
        schema = f"recovery_cursor_{uuid4().hex}"
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        users, jobs = [uuid4() for _ in range(11)], [uuid4() for _ in range(11)]
        created = datetime.now(timezone.utc) - timedelta(hours=1)
        dispatched = []
        class Queue:
            async def enqueue_gpu_job(self, job_id):
                dispatched.append(job_id)
        async def reconcile():
            return 0
        async def publish(*args, **kwargs):
            pass
        monkeypatch.setattr(gpu_worker, "get_session_factory", lambda: factory)
        monkeypatch.setattr(gpu_worker, "ArqQueueClient", lambda _redis: Queue())
        monkeypatch.setattr(gpu_worker, "reconcile_failed_reservations", reconcile)
        monkeypatch.setattr(gpu_worker, "publish_worker_heartbeat", publish)
        monkeypatch.setenv("GPU_WORKER_HEARTBEAT_SECONDS", "0")
        recover = gpu_worker.recover_dispatchable_jobs
        async def heartbeats(count):
            ctx, calls = {"redis": None, "gpu_heartbeat_stop": asyncio.Event()}, []
            async def tracked(queue, **kwargs):
                result = await recover(queue, **kwargs)
                calls.append(result)
                if len(calls) == count:
                    ctx["gpu_heartbeat_stop"].set()
                return result
            monkeypatch.setattr(gpu_worker, "recover_dispatchable_jobs", tracked)
            await asyncio.wait_for(gpu_worker._heartbeat_loop(ctx), 10)
            return ctx, calls
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as session, session.begin():
                for index, user_id in enumerate(users):
                    project_id = uuid4()
                    session.add(User(id=user_id, clerk_subject=str(user_id), status=UserStatus.ACTIVE))
                    await session.flush()
                    session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                                        source_ref="private", source_fingerprint="private"))
                    await session.flush()
                    session.add(Job(id=jobs[index], user_id=user_id, project_id=project_id,
                                    type=JobType.FULL_RENDER, status=JobStatus.QUEUED, request={},
                                    reserved_credits=4, created_at=created + timedelta(seconds=index)))
            async with factory() as blocker, blocker.begin():
                await blocker.scalars(select(User).where(User.id.in_(users[:10])).with_for_update())
                original, calls = await heartbeats(3)
                assert dispatched == [jobs[10]]
                assert calls == [0, 1, 0]
                restarted, calls = await heartbeats(1)
                assert calls == [0]  # Restart scans the locked prefix again, without a spin loop.
                assert restarted["gpu_recovery_cursor"] is not original["gpu_recovery_cursor"]
                assert restarted["gpu_recovery_cursor"]["after"] == (created + timedelta(seconds=9), jobs[9])
        finally:
            assert schema.startswith("recovery_cursor_") and len(schema) == 48
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await engine.dispose()

    asyncio.run(scenario())
