import asyncio
from uuid import uuid4

import pytest

from backend.services.storage.r2_store import R2ObjectStore
from backend.tests.test_private_object_storage import FakeR2Client, reservations


def test_signer_is_not_called_when_durable_quota_rejects():
    from backend.services.storage.upload_reservations import UploadQuotaExceeded
    client = FakeR2Client()
    quota = reservations()
    quota.reserve.side_effect = UploadQuotaExceeded("Storage full")
    store = R2ObjectStore(client=client, bucket_name="private", upload_reservations=quota)
    with pytest.raises(UploadQuotaExceeded):
        asyncio.run(store.create_upload_url(uuid4(), "source.mp4", "video/mp4", 123))
    assert client.presign_calls == []


def test_signing_failure_never_releases_ambiguous_put_reservation():
    from backend.services.storage.object_store import ObjectStoreError
    client = FakeR2Client()
    client.generate_presigned_url = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("signer failed"))
    quota = reservations()
    store = R2ObjectStore(client=client, bucket_name="private", upload_reservations=quota)
    with pytest.raises(ObjectStoreError):
        asyncio.run(store.create_upload_url(uuid4(), "source.mp4", "video/mp4", 123))
    quota.reserve.assert_awaited_once()


def test_presign_without_durable_admission_fails_closed():
    from backend.services.storage.object_store import ObjectStoreError
    client = FakeR2Client()
    store = R2ObjectStore(client=client, bucket_name="private")
    with pytest.raises(ObjectStoreError, match="Durable upload admission"):
        asyncio.run(store.create_upload_url(uuid4(), "source.mp4", "video/mp4", 123))
    assert client.presign_calls == []


def test_quota_rejection_returns_actionable_429_without_url():
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from backend.tests.test_upload_routes import _app, FakeObjectStore, FakeValidationQueue
    from backend.services.storage.upload_reservations import UploadQuotaExceeded
    store = FakeObjectStore()
    store.create_upload_url = AsyncMock(side_effect=UploadQuotaExceeded(
        "Upload storage limit reached. Pending and unfinished uploads also use storage; contact support if an unfinished upload is blocking capacity."
    ))
    response = TestClient(_app(store, FakeValidationQueue())).post(
        "/api/uploads/presign", json={"filename": "source.mp4", "content_type": "video/mp4", "size_bytes": 123},
    )
    assert response.status_code == 429
    assert "unfinished uploads" in response.json()["detail"]
    assert "url" not in response.json()


def test_store_completion_retry_does_not_reserve_again():
    user_id = uuid4()
    quota = reservations()
    store = R2ObjectStore(client=FakeR2Client(), bucket_name="private", upload_reservations=quota)
    upload = asyncio.run(store.create_upload_url(user_id, "source.mp4", "video/mp4", 123))
    first = asyncio.run(store.verify_uploaded_object(user_id, upload.storage_key))
    second = asyncio.run(store.verify_uploaded_object(user_id, upload.storage_key))
    assert first == second
    quota.reserve.assert_awaited_once()
    assert quota.verify.await_count == 2
