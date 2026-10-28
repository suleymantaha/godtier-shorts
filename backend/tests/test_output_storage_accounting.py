from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.db.base import Base
from backend.db.models import Asset, Job, JobStatus, JobType, Project, SourceType, UploadReservation, User
from backend.services.storage import upload_reservations
from backend.workers import production_runner


@pytest.fixture
def postgres(monkeypatch):
    url = os.getenv("UPLOAD_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Isolated UPLOAD_TEST_DATABASE_URL or TEST_DATABASE_URL required")
    monkeypatch.setenv("UPLOAD_STORAGE_QUOTA_BYTES", "10")
    return url


async def scenario(url, monkeypatch, tmp_path, check):
    schema = f"output_quota_{uuid4().hex}"
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    for module in (upload_reservations, production_runner):
        monkeypatch.setattr(module, "get_session_factory", lambda: factory)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.run_sync(Base.metadata.create_all)
        user_id, project_id, job_id = uuid4(), uuid4(), uuid4()
        async with factory() as session, session.begin():
            session.add(User(id=user_id, clerk_subject=str(user_id)))
            await session.flush()
            session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.YOUTUBE, source_ref="source", source_fingerprint="a" * 64))
            await session.flush()
            session.add(Job(id=job_id, user_id=user_id, project_id=project_id, type=JobType.FULL_RENDER, status=JobStatus.PROCESSING, request={}))
        context = production_runner.ProductionJobContext(job_id, user_id, project_id, "source", None, 30)
        source = tmp_path / "result.mp4"
        source.write_bytes(b"123456")
        uploaded = []
        async def upload():
            uploaded.append(True)
        kwargs = dict(context=context, source=source, storage_key=f"outputs/{user_id}/{job_id}/result.mp4", sha256="b" * 64, content_type="video/mp4", upload=upload)
        async def reserve(size=6):
            await upload_reservations.SqlAlchemyUploadReservations().reserve(user_id=user_id, storage_key=f"uploads/{user_id}/{uuid4()}.mp4", content_type="video/mp4", size_bytes=size, expires_at=datetime.now(timezone.utc) + timedelta(minutes=15))
        await check(factory, production_runner.SqlAlchemyProductionJobRepository(), kwargs, reserve, uploaded)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest.mark.integration
def test_postgres_presign_and_output_share_atomic_budget(postgres, monkeypatch, tmp_path):
    async def check(factory, repo, kwargs, reserve, uploaded):
        results = await asyncio.gather(reserve(), repo.publish_output(**kwargs), return_exceptions=True)
        assert sum(result is None for result in results) == 1, results
        assert sum(isinstance(result, (upload_reservations.UploadQuotaExceeded, production_runner.DeterministicJobError)) for result in results) == 1
        async with factory() as session:
            charges = (await session.scalars(select(UploadReservation))).all()
            assert sum(row.size_bytes for row in charges) == 6
            assert len(uploaded) == len((await session.scalars(select(Asset))).all())
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["upload", "metadata", "cancel"])
def test_postgres_output_failure_retains_charge_and_retry_counts_once(postgres, monkeypatch, tmp_path, failure):
    async def check(factory, repo, kwargs, reserve, uploaded):
        original_upload = kwargs["upload"]
        original_record = repo._record_output
        async def broken_upload():
            # The charge must be visible to another connection BEFORE remote I/O.
            async with factory() as session:
                assert (await session.get(UploadReservation, kwargs["storage_key"])).size_bytes == 6
            if failure == "cancel":
                raise asyncio.CancelledError()
            raise RuntimeError("remote failed")
        async def broken_record(*args, **kw):
            raise RuntimeError("metadata failed")
        if failure == "metadata":
            repo._record_output = broken_record
        else:
            kwargs["upload"] = broken_upload
        with pytest.raises(asyncio.CancelledError if failure == "cancel" else RuntimeError):
            await repo.publish_output(**kwargs)
        async with factory() as session:
            assert (await session.get(UploadReservation, kwargs["storage_key"])).size_bytes == 6
            assert (await session.scalars(select(Asset))).all() == []
        with pytest.raises(upload_reservations.UploadQuotaExceeded):
            await reserve(5)
        kwargs["upload"] = original_upload
        repo._record_output = original_record
        await repo.publish_output(**kwargs)
        await repo.publish_output(**kwargs)
        async with factory() as session:
            assert len((await session.scalars(select(UploadReservation))).all()) == 1
            assert len((await session.scalars(select(Asset))).all()) == 1
        await reserve(4)  # Asset + durable output charge count once.
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))


@pytest.mark.integration
def test_postgres_published_output_cannot_be_overwritten_with_different_bytes(postgres, monkeypatch, tmp_path):
    async def check(factory, repo, kwargs, reserve, uploaded):
        await repo.publish_output(**kwargs)
        kwargs["sha256"] = "c" * 64
        with pytest.raises(production_runner.DeterministicJobError, match="conflict"):
            await repo.publish_output(**kwargs)
        assert len(uploaded) == 1
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))

@pytest.mark.integration
def test_postgres_concurrent_outputs_share_budget(postgres, monkeypatch, tmp_path):
    async def check(factory, repo, kwargs, reserve, uploaded):
        second = {**kwargs, "storage_key": kwargs["storage_key"].replace("result.mp4", "second.mp4")}
        results = await asyncio.gather(repo.publish_output(**kwargs), repo.publish_output(**second), return_exceptions=True)
        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, production_runner.DeterministicJobError) for result in results) == 1
        assert len(uploaded) == 1
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))


@pytest.mark.integration
def test_postgres_existing_output_gets_durable_charge_without_double_count(postgres, monkeypatch, tmp_path):
    from backend.db.models import AssetKind
    async def check(factory, repo, kwargs, reserve, uploaded):
        context = kwargs["context"]
        async with factory() as session, session.begin():
            session.add(Asset(id=uuid4(), user_id=context.user_id, project_id=context.project_id,
                job_id=context.job_id, kind=AssetKind.SHORT, storage_key=kwargs["storage_key"],
                mime_type="video/mp4", size_bytes=6, sha256=kwargs["sha256"]))
        await reserve(4)
        await repo.publish_output(**kwargs)
        assert uploaded == []
        async with factory() as session:
            assert (await session.get(UploadReservation, kwargs["storage_key"])).size_bytes == 6
        with pytest.raises(upload_reservations.UploadQuotaExceeded):
            await reserve(1)
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))
@pytest.mark.integration
def test_postgres_outer_publication_cancel_retains_user_fence_until_remote_stops(postgres, monkeypatch, tmp_path):
    from sqlalchemy.exc import DBAPIError

    async def check(factory, repo, kwargs, reserve, uploaded):
        started, finish = asyncio.Event(), asyncio.Event()
        async def remote_write():
            started.set()
            await finish.wait()
            uploaded.append(True)
        kwargs["upload"] = remote_write
        publication = asyncio.create_task(repo.publish_output(**kwargs))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            publication.cancel()
            # This is a real second PostgreSQL connection, not a scheduling-only
            # sleep: the lock timeout proves the outer cancellation kept User.
            async with factory() as session, session.begin():
                await session.execute(text("SET LOCAL lock_timeout = '150ms'"))
                with pytest.raises(DBAPIError, match="lock timeout"):
                    await session.scalar(select(User).where(User.id == kwargs["context"].user_id).with_for_update())
            assert not publication.done()
        finally:
            finish.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(publication, timeout=5)
        assert uploaded == [True]
        async with factory() as session, session.begin():
            assert await session.scalar(select(User).where(User.id == kwargs["context"].user_id).with_for_update()) is not None
            assert (await session.get(UploadReservation, kwargs["storage_key"])).size_bytes == 6
            assert (await session.scalars(select(Asset))).all() == []
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))
