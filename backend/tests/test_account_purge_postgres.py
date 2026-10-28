"""Real PostgreSQL transaction smoke; remote services remain deterministic fakes."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models import Asset, AssetKind, Job, JobStatus, JobType, Project, SourceType, User, UserStatus
from backend.services import account_purge as purge


def test_postgres_fence_scrub_and_retry_preserves_financial_fk_skeleton(monkeypatch):
    url = os.getenv("ACCOUNT_PURGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ACCOUNT_PURGE_TEST_DATABASE_URL is required")

    async def scenario():
        schema = f"account_purge_test_{uuid4().hex}"
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        user_id, project_id, job_id = uuid4(), uuid4(), uuid4()
        key = f"uploads/{user_id}/source.mp4"
        objects = {key}

        class Remote:
            async def cancel(self, key):
                return False  # No queue record for a completed job.

            async def keys(self, prefix):
                return [key for key in objects if key.startswith(prefix)]

            async def delete(self, key):
                objects.discard(key)

        @asynccontextmanager
        async def remote():
            yield Remote()

        monkeypatch.setattr(purge, "get_session_factory", lambda: factory)
        monkeypatch.setattr(purge, "_production_remote", remote)
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as session, session.begin():
                session.add(User(id=user_id, clerk_subject="pg-owner", status=UserStatus.ACTIVE))
                await session.flush()
                session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
                                    source_ref=key, source_fingerprint="private"))
                await session.flush()
                session.add(Job(id=job_id, user_id=user_id, project_id=project_id, type=JobType.FULL_RENDER,
                                status=JobStatus.COMPLETED, request={"private": "text"}, reserved_credits=0))
                await session.flush()
                session.add(Asset(id=uuid4(), user_id=user_id, project_id=project_id, storage_key=key,
                                  job_id=job_id, kind=AssetKind.SOURCE, mime_type="video/mp4", size_bytes=1,
                                  sha256="0" * 64))
            assert (await purge._purge_production("pg-owner"))["reason"] == "upload_url_expiry"
            async with factory() as session, session.begin():
                user = await session.get(User, user_id)
                assert user.status is UserStatus.DELETED
                user.deletion_requested_at = datetime.now(timezone.utc) - timedelta(seconds=1000)
            assert (await purge._purge_production("pg-owner"))["reason"] == "storage_finalization_unverified"
            assert not objects
            async with factory() as session:
                assert await session.scalar(select(Asset.id)) is None
                assert (await session.get(Job, job_id)).request == {}
                assert (await session.get(Project, project_id)).source_ref == ""
                assert (await session.get(User, user_id)).data_purged_at is None
        finally:
            # This test owns exactly its unique schema; no shared database is dropped.
            assert schema.startswith("account_purge_test_") and len(schema) == 51
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await engine.dispose()

    asyncio.run(scenario())
