from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.db.base import Base
from backend.db.models import Asset, CreditWallet, Job, JobStatus, Project, SourceType, User, UserStatus
from backend.services.billing import ledger
from backend.services.queue import job_service
from backend.services.storage import validated_uploads
from backend.workers import gpu_worker, production_runner


@pytest.mark.integration
def test_postgres_atomic_admission_crash_upload_and_settlement_recovery(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Isolated TEST_DATABASE_URL required")

    async def scenario():
        schema = f"fix_production_{uuid4().hex}"
        admin = create_async_engine(url, poolclass=NullPool)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            for module in (job_service, validated_uploads, gpu_worker, ledger, production_runner):
                monkeypatch.setattr(module, "get_session_factory", lambda: factory)
            user_id, project_id = uuid4(), uuid4()
            async with factory() as session, session.begin():
                session.add(User(id=user_id, clerk_subject=str(user_id)))
                await session.flush()
                session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD, source_ref="source", source_fingerprint="a"*64))
                session.add(CreditWallet(user_id=user_id, available=100, reserved=0))
            repo = job_service.SqlAlchemyJobRepository()
            async def submit(key):
                return await repo.create_queued(user_id=user_id, project_id=project_id, job_type="full_render", request={}, idempotency_key=key, estimated_credits=20, max_active_jobs=1)
            outcomes = await asyncio.gather(submit("first"), submit("second"), return_exceptions=True)
            admitted = [item for item in outcomes if isinstance(item, job_service.DurableJob)]
            assert len(admitted) == 1
            assert sum(isinstance(item, job_service.ActiveJobLimitReached) for item in outcomes) == 1
            job_id = admitted[0].id
            original_reserve = ledger.reserve_in_session
            async def crash_after_reserve(*args, **kwargs):
                await original_reserve(*args, **kwargs)
                raise RuntimeError("crash after debit before commit")
            with monkeypatch.context() as patch:
                patch.setattr(ledger, "reserve_in_session", crash_after_reserve)
                with pytest.raises(RuntimeError, match="crash after debit"):
                    await repo.create_queued(user_id=user_id, project_id=project_id, job_type="full_render", request={}, idempotency_key="crash", estimated_credits=20)
            async with factory() as session:
                assert len((await session.scalars(select(Job))).all()) == 1
                wallet = await session.get(CreditWallet, user_id)
                assert (wallet.available, wallet.reserved) == (80, 20)
            upload = dict(user_id=user_id, storage_key=f"uploads/{user_id}/one.mp4", content_type="video/mp4", size_bytes=100, duration_seconds=13, sha256="b"*64)
            ids = await asyncio.gather(validated_uploads.persist_validated_upload(**upload), validated_uploads.persist_validated_upload(**upload))
            assert ids[0] == ids[1]
            async with factory() as session:
                assert len((await session.scalars(select(Asset))).all()) == 1
                assert (await session.get(Project, ids[0])).duration_seconds == 13
            async with factory() as session, session.begin():
                job = await session.get(Job, job_id)
                job.status = JobStatus.PROCESSING
            await ledger.settle(user_id, job_id, 20, f"settle:worker:{job_id}")
            queue = SimpleNamespace(enqueue_gpu_job=AsyncMock())
            assert await gpu_worker.recover_dispatchable_jobs(queue) == 0
            queue.enqueue_gpu_job.assert_not_awaited()
            async with factory() as session:
                job = await session.get(Job, job_id)
                assert job.status is JobStatus.COMPLETED
                assert job.reserved_credits == 0 and job.settled_credits == 20
            # Publication keeps the user fence until storage and Asset commit.
            async with factory() as session, session.begin():
                (await session.get(Job, job_id)).status = JobStatus.PROCESSING
            started, finish, deleted = asyncio.Event(), asyncio.Event(), asyncio.Event()
            async def upload():
                started.set()
                await finish.wait()
            async def tombstone():
                async with factory() as session, session.begin():
                    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
                    user.status = UserStatus.DELETED
                deleted.set()
            with TemporaryDirectory() as directory:
                source = Path(directory) / "result.mp4"
                source.write_bytes(b"rendered")
                kwargs = dict(context=SimpleNamespace(user_id=user_id, job_id=job_id, project_id=project_id), upload=upload, storage_key=f"outputs/{user_id}/{job_id}/result.mp4", source=source, sha256="c"*64, content_type="video/mp4")
                publication = asyncio.create_task(production_runner.SqlAlchemyProductionJobRepository().publish_output(**kwargs))
                await asyncio.wait_for(started.wait(), timeout=5)
                deletion = asyncio.create_task(tombstone())
                await asyncio.sleep(0.05)
                assert not deleted.is_set()
                finish.set()
                await asyncio.wait_for(asyncio.gather(publication, deletion), timeout=5)
                rejected_upload = AsyncMock()
                kwargs["upload"] = rejected_upload
                with pytest.raises(production_runner.DeterministicJobError, match="Account is not active"):
                    await production_runner.SqlAlchemyProductionJobRepository().publish_output(**kwargs)
                rejected_upload.assert_not_awaited()
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())


@pytest.mark.integration
def test_redis_duplicate_upload_completion_creates_one_validation_job(monkeypatch):
    url = os.getenv("TEST_REDIS_URL", "")
    if not url:
        pytest.skip("Isolated TEST_REDIS_URL required")
    from arq import create_pool
    from arq.connections import RedisSettings
    from backend.services.storage.media_validation import ArqMediaValidationQueue
    from backend.services.storage.object_store import UploadedObjectMetadata

    async def scenario():
        pool = await create_pool(RedisSettings.from_dsn(url))
        user_id = uuid4()
        metadata = UploadedObjectMetadata(f"uploads/{user_id}/one.mp4", "video/mp4", 100)
        queue = ArqMediaValidationQueue(url)
        job_id = ""
        try:
            ids = await asyncio.gather(*(queue.enqueue(user_id=user_id, metadata=metadata) for _ in range(4)))
            assert len(set(ids)) == 1
            job_id = ids[0]
            assert await pool.exists(f"arq:job:{job_id}") == 1
            assert await pool.zscore("arq:queue", job_id) is not None
        finally:
            if job_id:
                await pool.zrem("arq:queue", job_id)
                await pool.delete(f"arq:job:{job_id}", f"arq:result:{job_id}")
            await pool.delete(f"godtier:upload-validation:{user_id}")
            await pool.aclose()
    asyncio.run(scenario())
