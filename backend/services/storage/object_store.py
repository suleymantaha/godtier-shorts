from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID


ALLOWED_UPLOAD_TYPES = {
    "video/mp4": {".mp4", ".m4v"},
    "video/quicktime": {".mov"},
    "video/x-m4v": {".m4v"},
}
DEFAULT_UPLOAD_URL_EXPIRES_SECONDS = 900
DEFAULT_DOWNLOAD_URL_EXPIRES_SECONDS = 600


class ObjectStoreError(RuntimeError):
    pass


class UploadValidationError(ObjectStoreError):
    pass


class ObjectNotFoundError(ObjectStoreError):
    pass


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    storage_key: str
    required_headers: dict[str, str]
    expires_seconds: int


@dataclass(frozen=True, slots=True)
class UploadedObjectMetadata:
    storage_key: str
    content_type: str
    size_bytes: int


class ObjectStore(Protocol):
    async def create_upload_url(
        self, user_id: UUID, filename: str, content_type: str, size_bytes: int
    ) -> PresignedUpload: ...

    async def create_download_url(
        self, user_id: UUID, asset_id: UUID, expires_seconds: int = 600
    ) -> str: ...

    async def put_internal(
        self, key: str, file_path: str | Path, content_type: str
    ) -> None: ...

    async def delete(self, key: str) -> None: ...


def validate_upload_metadata(
    filename: str, content_type: str, size_bytes: int, max_upload_bytes: int
) -> str:
    normalized_type = content_type.strip().lower()
    allowed_extensions = ALLOWED_UPLOAD_TYPES.get(normalized_type)
    if allowed_extensions is None:
        raise UploadValidationError("Unsupported upload content type")
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        raise UploadValidationError("Upload extension does not match content type")
    if size_bytes <= 0:
        raise UploadValidationError("Upload size must be positive")
    if size_bytes > max_upload_bytes:
        raise UploadValidationError("Upload exceeds the configured size limit")
    return extension
