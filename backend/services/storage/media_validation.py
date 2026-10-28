from __future__ import annotations

import hashlib
import os
from typing import Protocol
from uuid import UUID

from backend.services.storage.object_store import UploadedObjectMetadata
from backend.services.abuse.rate_limit import FIXED_WINDOW_SCRIPT


class UploadAdmissionError(RuntimeError):
    pass


class MediaValidationQueue(Protocol):
    async def status(self, *, user_id: UUID, storage_key: str) -> str: ...

    async def enqueue(
        self, *, user_id: UUID, metadata: UploadedObjectMetadata
    ) -> str: ...


class ArqMediaValidationQueue:
    """Dispatch uploaded media to the worker that performs ffprobe validation."""

    def __init__(self, redis_url: str) -> None:
        if not redis_url.strip():
            raise ValueError("REDIS_URL is required")
        self._redis_url = redis_url

    @staticmethod
    def job_id(user_id: UUID, storage_key: str) -> str:
        digest = hashlib.sha256(f"{user_id}:{storage_key}".encode()).hexdigest()
        return f"validate:{digest}"

    async def status(self, *, user_id: UUID, storage_key: str) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings
        from arq.jobs import Job, JobStatus

        pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        try:
            job = Job(self.job_id(user_id, storage_key), pool)
            state = await job.status()
            if state is JobStatus.complete:
                result = await job.result_info()
                return "failed" if result is not None and not result.success else "pending"
            if state is JobStatus.in_progress:
                return "validating"
            if state in {JobStatus.queued, JobStatus.deferred}:
                return "queued"
            return "pending"
        finally:
            await pool.aclose()

    async def enqueue(
        self, *, user_id: UUID, metadata: UploadedObjectMetadata
    ) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        try:
            job_id = self.job_id(user_id, metadata.storage_key)
            if await pool.exists(f"arq:job:{job_id}", f"arq:result:{job_id}"):
                return job_id
            count, _ttl = await pool.eval(
                FIXED_WINDOW_SCRIPT, 1, f"godtier:upload-validation:{user_id}",
                int(os.getenv("UPLOAD_VALIDATION_WINDOW_SECONDS", "3600")),
            )
            if int(count) > int(os.getenv("UPLOAD_VALIDATION_LIMIT", "5")):
                raise UploadAdmissionError("Upload validation limit reached")
            await pool.enqueue_job(
                "validate_uploaded_media",
                str(user_id),
                metadata.storage_key,
                metadata.content_type,
                metadata.size_bytes,
                _job_id=job_id,
            )
            return job_id
        finally:
            await pool.aclose()
