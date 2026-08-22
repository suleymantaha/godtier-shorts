from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import UPLOAD_MAX_FILE_SIZE
from backend.db.models import Asset
from backend.services.storage.object_store import (
    DEFAULT_DOWNLOAD_URL_EXPIRES_SECONDS,
    DEFAULT_UPLOAD_URL_EXPIRES_SECONDS,
    ObjectNotFoundError,
    ObjectStoreError,
    PresignedUpload,
    UploadedObjectMetadata,
    UploadValidationError,
    validate_upload_metadata,
)


class AssetRepository(Protocol):
    async def get_owned_storage_key(
        self, user_id: UUID, asset_id: UUID
    ) -> str | None: ...


class SqlAlchemyAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_owned_storage_key(
        self, user_id: UUID, asset_id: UUID
    ) -> str | None:
        return await self._session.scalar(
            select(Asset.storage_key).where(
                Asset.id == asset_id,
                Asset.user_id == user_id,
            )
        )


class R2ObjectStore:
    def __init__(
        self,
        *,
        client: Any,
        bucket_name: str,
        asset_repository: AssetRepository | None = None,
        max_upload_bytes: int = UPLOAD_MAX_FILE_SIZE,
    ) -> None:
        if not bucket_name.strip():
            raise ValueError("R2 bucket name is required")
        self._client = client
        self._bucket_name = bucket_name
        self._assets = asset_repository
        self._max_upload_bytes = max_upload_bytes

    async def create_upload_url(
        self, user_id: UUID, filename: str, content_type: str, size_bytes: int
    ) -> PresignedUpload:
        extension = validate_upload_metadata(
            filename, content_type, size_bytes, self._max_upload_bytes
        )
        normalized_type = content_type.strip().lower()
        storage_key = f"uploads/{user_id}/{uuid4()}{extension}"
        try:
            url = await asyncio.to_thread(
                self._client.generate_presigned_url,
                "put_object",
                Params={
                    "Bucket": self._bucket_name,
                    "Key": storage_key,
                    "ContentType": normalized_type,
                },
                ExpiresIn=DEFAULT_UPLOAD_URL_EXPIRES_SECONDS,
            )
        except Exception as exc:
            raise ObjectStoreError("Upload URL could not be signed") from exc
        return PresignedUpload(
            url=url,
            storage_key=storage_key,
            required_headers={"Content-Type": normalized_type},
            expires_seconds=DEFAULT_UPLOAD_URL_EXPIRES_SECONDS,
        )

    async def create_download_url(
        self,
        user_id: UUID,
        asset_id: UUID,
        expires_seconds: int = DEFAULT_DOWNLOAD_URL_EXPIRES_SECONDS,
    ) -> str:
        if not 1 <= expires_seconds <= 604800:
            raise ValueError("Signed URL expiry must be between 1 and 604800 seconds")
        if self._assets is None:
            raise RuntimeError("Asset repository is required for signed downloads")
        storage_key = await self._assets.get_owned_storage_key(user_id, asset_id)
        if storage_key is None:
            raise ObjectNotFoundError("Asset not found")
        try:
            return await asyncio.to_thread(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket_name, "Key": storage_key},
                ExpiresIn=expires_seconds,
            )
        except Exception as exc:
            raise ObjectStoreError("Download URL could not be signed") from exc

    async def put_internal(
        self, key: str, file_path: str | Path, content_type: str
    ) -> None:
        try:
            await asyncio.to_thread(
                self._client.upload_file,
                str(file_path),
                self._bucket_name,
                key,
                {"ContentType": content_type},
            )
        except Exception as exc:
            raise ObjectStoreError("Object upload failed") from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket_name,
                Key=key,
            )
        except Exception as exc:
            raise ObjectStoreError("Object deletion failed") from exc

    async def verify_uploaded_object(
        self, user_id: UUID, storage_key: str
    ) -> UploadedObjectMetadata:
        prefix = f"uploads/{user_id}/"
        if not storage_key.startswith(prefix) or "/" in storage_key[len(prefix) :]:
            raise ObjectNotFoundError("Uploaded object not found")
        try:
            metadata = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket_name,
                Key=storage_key,
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code") or "")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError("Uploaded object not found") from exc
            raise ObjectStoreError("Object storage unavailable") from exc
        except Exception as exc:
            raise ObjectStoreError("Object storage unavailable") from exc
        content_type = str(metadata.get("ContentType") or "").strip().lower()
        size_bytes = int(metadata.get("ContentLength") or 0)
        filename = Path(storage_key).name
        validate_upload_metadata(
            filename, content_type, size_bytes, self._max_upload_bytes
        )
        return UploadedObjectMetadata(
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
        )
