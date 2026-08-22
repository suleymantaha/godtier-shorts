from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import UUID


class QueueDispatchError(RuntimeError):
    pass


class QueueClient(Protocol):
    async def enqueue_gpu_job(self, job_id: UUID) -> None: ...

    async def publish_progress(self, job_id: UUID, event: dict[str, Any]) -> None: ...


class ArqQueueClient:
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def enqueue_gpu_job(self, job_id: UUID) -> None:
        try:
            queued = await self._redis.enqueue_job(
                "run_gpu_job",
                str(job_id),
                _job_id=f"gpu:{job_id}",
            )
        except Exception as exc:
            raise QueueDispatchError("Redis queue dispatch failed") from exc
        # ARQ returns None when this stable job id is already queued. Treat the
        # duplicate as idempotent success; connection failures raise above.

    async def publish_progress(self, job_id: UUID, event: dict[str, Any]) -> None:
        try:
            await self._redis.publish(
                f"jobs:{job_id}:progress",
                json.dumps(event, separators=(",", ":"), sort_keys=True),
            )
        except Exception as exc:
            raise QueueDispatchError("Redis progress publish failed") from exc
