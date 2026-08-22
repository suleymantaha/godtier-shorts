from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.services.storage.object_store import (
    ObjectNotFoundError,
    UploadValidationError,
)
from backend.services.storage.r2_store import R2ObjectStore


class FakeR2Client:
    def __init__(self) -> None:
        self.presign_calls: list[tuple[str, dict, int]] = []
        self.upload_calls: list[tuple[str, str, str, dict]] = []
        self.delete_calls: list[dict] = []
        self.head_response = {"ContentLength": 123, "ContentType": "video/mp4"}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.presign_calls.append((operation, Params, ExpiresIn))
        return f"https://signed.invalid/{operation}"

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.upload_calls.append((filename, bucket, key, ExtraArgs))

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)

    def head_object(self, **_kwargs):
        return self.head_response


class FakeAssetRepository:
    def __init__(self, storage_key: str | None) -> None:
        self.storage_key = storage_key

    async def get_owned_storage_key(self, user_id: UUID, asset_id: UUID) -> str | None:
        return self.storage_key


@pytest.mark.asyncio
async def test_upload_url_uses_opaque_uuid_key_and_signed_content_type() -> None:
    client = FakeR2Client()
    user_id = uuid4()
    store = R2ObjectStore(client=client, bucket_name="private-assets")

    upload = await store.create_upload_url(
        user_id, "My Holiday Video.mp4", "video/mp4", 123
    )

    assert upload.storage_key.startswith(f"uploads/{user_id}/")
    assert "My Holiday Video" not in upload.storage_key
    UUID(Path(upload.storage_key).stem)
    assert upload.required_headers == {"Content-Type": "video/mp4"}
    assert client.presign_calls == [
        (
            "put_object",
            {
                "Bucket": "private-assets",
                "Key": upload.storage_key,
                "ContentType": "video/mp4",
            },
            900,
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content_type", "size_bytes"),
    [
        ("video.exe", "video/mp4", 123),
        ("video.mp4", "application/octet-stream", 123),
        ("video.mp4", "video/mp4", 0),
        ("video.mp4", "video/mp4", 1025),
    ],
)
async def test_upload_url_rejects_invalid_media_metadata(
    filename: str, content_type: str, size_bytes: int
) -> None:
    store = R2ObjectStore(
        client=FakeR2Client(), bucket_name="private-assets", max_upload_bytes=1024
    )

    with pytest.raises(UploadValidationError):
        await store.create_upload_url(uuid4(), filename, content_type, size_bytes)


@pytest.mark.asyncio
async def test_download_url_requires_asset_ownership_and_defaults_to_ten_minutes() -> None:
    client = FakeR2Client()
    store = R2ObjectStore(
        client=client,
        bucket_name="private-assets",
        asset_repository=FakeAssetRepository("assets/result.mp4"),
    )

    url = await store.create_download_url(uuid4(), uuid4())

    assert url.endswith("get_object")
    assert client.presign_calls == [
        (
            "get_object",
            {"Bucket": "private-assets", "Key": "assets/result.mp4"},
            600,
        )
    ]


@pytest.mark.asyncio
async def test_download_url_does_not_sign_another_users_asset() -> None:
    client = FakeR2Client()
    store = R2ObjectStore(
        client=client,
        bucket_name="private-assets",
        asset_repository=FakeAssetRepository(None),
    )

    with pytest.raises(ObjectNotFoundError):
        await store.create_download_url(uuid4(), uuid4())

    assert client.presign_calls == []


@pytest.mark.asyncio
async def test_internal_put_and_delete_keep_bucket_private(tmp_path: Path) -> None:
    source = tmp_path / "render.mp4"
    source.write_bytes(b"video")
    client = FakeR2Client()
    store = R2ObjectStore(client=client, bucket_name="private-assets")

    await store.put_internal("renders/opaque.mp4", source, "video/mp4")
    await store.delete("renders/opaque.mp4")

    assert client.upload_calls == [
        (
            str(source),
            "private-assets",
            "renders/opaque.mp4",
            {"ContentType": "video/mp4"},
        )
    ]
    assert client.delete_calls == [
        {"Bucket": "private-assets", "Key": "renders/opaque.mp4"}
    ]


@pytest.mark.asyncio
async def test_uploaded_object_metadata_is_verified_before_validation_job() -> None:
    user_id = uuid4()
    client = FakeR2Client()
    store = R2ObjectStore(client=client, bucket_name="private-assets")
    upload = await store.create_upload_url(user_id, "source.mp4", "video/mp4", 123)

    metadata = await store.verify_uploaded_object(user_id, upload.storage_key)

    assert metadata.size_bytes == 123
    assert metadata.content_type == "video/mp4"


@pytest.mark.asyncio
async def test_uploaded_object_key_must_belong_to_authenticated_user() -> None:
    store = R2ObjectStore(client=FakeR2Client(), bucket_name="private-assets")

    with pytest.raises(ObjectNotFoundError):
        await store.verify_uploaded_object(uuid4(), f"uploads/{uuid4()}/{uuid4()}.mp4")
