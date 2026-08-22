from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import uploads
from backend.api.security import AuthContext, authenticate_request
from backend.services.storage.object_store import (
    ObjectNotFoundError,
    PresignedUpload,
    UploadedObjectMetadata,
)


class FakeObjectStore:
    def __init__(self) -> None:
        self.upload_user_id = None
        self.download_user_id = None
        self.verify_user_id = None
        self.fail_download = False

    async def create_upload_url(self, user_id, filename, content_type, size_bytes):
        self.upload_user_id = user_id
        return PresignedUpload(
            url="https://signed.invalid/put",
            storage_key=f"uploads/{user_id}/opaque.mp4",
            required_headers={"Content-Type": content_type},
            expires_seconds=900,
        )

    async def create_download_url(self, user_id, asset_id, expires_seconds=600):
        self.download_user_id = user_id
        if self.fail_download:
            raise ObjectNotFoundError("Asset not found")
        return "https://signed.invalid/get"

    async def verify_uploaded_object(self, user_id, storage_key):
        self.verify_user_id = user_id
        return UploadedObjectMetadata(storage_key, "video/mp4", 123)


class FakeValidationQueue:
    def __init__(self) -> None:
        self.calls = []

    async def enqueue(self, *, user_id, metadata):
        self.calls.append((user_id, metadata))
        return "validation-job-1"


def _app(store: FakeObjectStore, queue: FakeValidationQueue, *, authenticated=True):
    app = FastAPI()
    app.include_router(uploads.router)
    app.dependency_overrides[uploads.get_object_store] = lambda: store
    app.dependency_overrides[uploads.get_media_validation_queue] = lambda: queue
    if authenticated:
        user_id = uuid4()
        app.state.test_user_id = user_id
        app.dependency_overrides[authenticate_request] = lambda: AuthContext(
            subject="user-1",
            roles={"member"},
            token_type="jwt",
            auth_mode="clerk_jwt",
            user_id=user_id,
        )
    return app


def test_presign_upload_uses_authenticated_database_identity() -> None:
    store = FakeObjectStore()
    app = _app(store, FakeValidationQueue())

    response = TestClient(app).post(
        "/api/uploads/presign",
        json={"filename": "video.mp4", "content_type": "video/mp4", "size_bytes": 123},
    )

    assert response.status_code == 200
    assert store.upload_user_id == app.state.test_user_id
    assert response.json()["storage_key"].startswith(
        f"uploads/{app.state.test_user_id}/"
    )


def test_complete_upload_verifies_r2_metadata_then_enqueues_media_validation() -> None:
    store = FakeObjectStore()
    queue = FakeValidationQueue()
    app = _app(store, queue)
    storage_key = f"uploads/{app.state.test_user_id}/opaque.mp4"

    response = TestClient(app).post(
        "/api/uploads/complete", json={"storage_key": storage_key}
    )

    assert response.status_code == 202
    assert store.verify_user_id == app.state.test_user_id
    assert queue.calls[0][0] == app.state.test_user_id
    assert queue.calls[0][1].storage_key == storage_key
    assert response.json() == {
        "validation_job_id": "validation-job-1",
        "status": "queued",
    }


def test_download_hides_another_users_asset() -> None:
    store = FakeObjectStore()
    store.fail_download = True
    app = _app(store, FakeValidationQueue())

    response = TestClient(app).post(f"/api/uploads/assets/{uuid4()}/download")

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found"}


def test_upload_routes_require_authentication() -> None:
    app = _app(FakeObjectStore(), FakeValidationQueue(), authenticated=False)

    response = TestClient(app).post(
        "/api/uploads/presign",
        json={"filename": "video.mp4", "content_type": "video/mp4", "size_bytes": 123},
    )

    assert response.status_code == 401
