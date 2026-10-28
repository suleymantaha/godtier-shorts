from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import Asset, AssetKind, Project, SourceType, User
from backend.tests.test_production_persistence import AsyncSessionPort
from backend.services.storage import upload_reservations


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    user_id = uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=user_id, clerk_subject=str(user_id)))
    monkeypatch.setattr(upload_reservations, "get_session_factory", lambda: lambda: AsyncSessionPort(engine))
    yield engine, user_id
    engine.dispose()


def reserve(user_id, key, size=5 * 1024**3):
    return upload_reservations.SqlAlchemyUploadReservations().reserve(
        user_id=user_id, storage_key=key, content_type="video/mp4", size_bytes=size,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )


def test_six_large_presigns_cannot_reserve_thirty_gib(database):
    engine, user_id = database
    asyncio.run(reserve(user_id, f"uploads/{user_id}/first.mp4"))
    for number in range(5):
        with pytest.raises(upload_reservations.UploadQuotaExceeded):
            asyncio.run(reserve(user_id, f"uploads/{user_id}/{number}.mp4"))
    with Session(engine) as session:
        assert len(session.scalars(select(upload_reservations.UploadReservation)).all()) == 1


def test_expired_orphan_still_counts_without_r2_finality(database):
    engine, user_id = database
    key = f"uploads/{user_id}/orphan.mp4"
    asyncio.run(reserve(user_id, key))
    with Session(engine) as session, session.begin():
        session.get(upload_reservations.UploadReservation, key).expires_at = datetime.now(timezone.utc) - timedelta(days=3)
    with pytest.raises(upload_reservations.UploadQuotaExceeded):
        asyncio.run(reserve(user_id, f"uploads/{user_id}/new.mp4"))


def test_asset_and_its_reservation_count_once(database):
    engine, user_id = database
    key = f"uploads/{user_id}/validated.mp4"
    asyncio.run(reserve(user_id, key, 3 * 1024**3))
    with Session(engine) as session, session.begin():
        project_id = uuid4()
        session.add(Project(id=project_id, user_id=user_id, source_type=SourceType.UPLOAD, source_ref=key, source_fingerprint="a"*64))
        session.flush()
        session.add(Asset(id=uuid4(), user_id=user_id, project_id=project_id, kind=AssetKind.SOURCE, storage_key=key, mime_type="video/mp4", size_bytes=3 * 1024**3, sha256="a"*64))
    asyncio.run(reserve(user_id, f"uploads/{user_id}/second.mp4", 2 * 1024**3))
    with pytest.raises(upload_reservations.UploadQuotaExceeded):
        asyncio.run(reserve(user_id, f"uploads/{user_id}/third.mp4", 1))


def test_complete_metadata_must_match_durable_reservation(database):
    _, user_id = database
    key = f"uploads/{user_id}/source.mp4"
    asyncio.run(reserve(user_id, key, 123))
    repo = upload_reservations.SqlAlchemyUploadReservations()
    asyncio.run(repo.verify(user_id=user_id, storage_key=key, content_type="video/mp4", size_bytes=123))
    asyncio.run(repo.verify(user_id=user_id, storage_key=key, content_type="video/mp4", size_bytes=123))
    with pytest.raises(upload_reservations.UploadValidationError):
        asyncio.run(repo.verify(user_id=user_id, storage_key=key, content_type="video/mp4", size_bytes=124))


def test_complete_failure_and_retry_keep_one_durable_charge(database):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from backend.api.routes.uploads import CompleteUploadRequest, complete_upload
    from backend.api.security import AuthContext
    from backend.services.storage.media_validation import UploadAdmissionError
    from backend.services.storage.r2_store import R2ObjectStore
    from backend.tests.test_private_object_storage import FakeR2Client

    engine, user_id = database
    store = R2ObjectStore(client=FakeR2Client(), bucket_name="private", upload_reservations=upload_reservations.SqlAlchemyUploadReservations())
    upload = asyncio.run(store.create_upload_url(user_id, "source.mp4", "video/mp4", 123))
    auth = AuthContext(subject="owner", roles={"member"}, token_type="jwt", auth_mode="clerk_jwt", user_id=user_id)
    queue = SimpleNamespace(enqueue=AsyncMock(side_effect=[UploadAdmissionError("busy"), "validation-job"]))
    payload = CompleteUploadRequest(storage_key=upload.storage_key)
    with pytest.raises(HTTPException) as failed:
        asyncio.run(complete_upload(payload, auth, store, queue))
    assert failed.value.status_code == 429
    assert asyncio.run(complete_upload(payload, auth, store, queue)).validation_job_id == "validation-job"
    with Session(engine) as session:
        rows = session.scalars(select(upload_reservations.UploadReservation)).all()
        assert len(rows) == 1 and rows[0].size_bytes == 123


def test_account_purge_retains_charge_and_deletion_fence(monkeypatch, database):
    from contextlib import asynccontextmanager
    from backend.services import account_purge
    from backend.db.models import UserStatus
    engine, user_id = database
    key = f"uploads/{user_id}/orphan.mp4"
    asyncio.run(reserve(user_id, key))
    with Session(engine) as session, session.begin():
        user = session.get(User, user_id)
        user.deletion_requested_at = datetime.now(timezone.utc) - timedelta(hours=1)
    monkeypatch.setattr(account_purge, "get_session_factory", lambda: lambda: AsyncSessionPort(engine))
    class Remote:
        async def keys(self, prefix): return []
        async def cancel(self, key): return False
        async def delete(self, key): raise AssertionError("no remote key was listed")
    @asynccontextmanager
    async def remote(): yield Remote()
    monkeypatch.setattr(account_purge, "_production_remote", remote)
    result = asyncio.run(account_purge._purge_production(str(user_id)))
    assert result["reason"] == "storage_finalization_unverified"
    with Session(engine) as session:
        assert session.get(User, user_id).status is UserStatus.DELETED
        assert session.get(upload_reservations.UploadReservation, key).size_bytes == 5 * 1024**3
    with pytest.raises(upload_reservations.UploadValidationError, match="Account is not active"):
        asyncio.run(reserve(user_id, f"uploads/{user_id}/new.mp4", 1))


@pytest.mark.integration
def test_postgres_concurrent_reservations_serialize_account_budget(monkeypatch):
    import os
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    url = os.getenv("UPLOAD_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Isolated UPLOAD_TEST_DATABASE_URL or TEST_DATABASE_URL required")
    async def scenario():
        schema = f"upload_quota_{uuid4().hex}"
        engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(upload_reservations, "get_session_factory", lambda: factory)
        user_id = uuid4()
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                await conn.run_sync(Base.metadata.create_all)
            async with factory() as session, session.begin():
                session.add(User(id=user_id, clerk_subject=str(user_id)))
            outcomes = await asyncio.gather(*(reserve(user_id, f"uploads/{user_id}/{i}.mp4") for i in range(6)), return_exceptions=True)
            assert sum(item is None for item in outcomes) == 1
            assert sum(isinstance(item, upload_reservations.UploadQuotaExceeded) for item in outcomes) == 5
            async with factory() as session:
                assert len((await session.scalars(select(upload_reservations.UploadReservation))).all()) == 1
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await engine.dispose()
    asyncio.run(scenario())
