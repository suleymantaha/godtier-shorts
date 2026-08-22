from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.services.storage.object_store import UploadedObjectMetadata


class MediaValidationQueue(Protocol):
    async def enqueue(
        self, *, user_id: UUID, metadata: UploadedObjectMetadata
    ) -> str: ...


class ArqMediaValidationQueue:
    """Dispatch uploaded media to the worker that performs ffprobe validation."""

    def __init__(self, redis_url: str) -> None:
        if not redis_url.strip():
            raise ValueError("REDIS_URL is required")
        self._redis_url = redis_url

    async def enqueue(
        self, *, user_id: UUID, metadata: UploadedObjectMetadata
    ) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        try:
            job = await pool.enqueue_job(
                "validate_uploaded_media",
                str(user_id),
                metadata.storage_key,
                metadata.content_type,
                metadata.size_bytes,
            )
            if job is None:
                raise RuntimeError("Media validation job could not be enqueued")
            return job.job_id
        finally:
            await pool.aclose()
