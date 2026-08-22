from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.services.queue.client import ArqQueueClient


class FakeArqRedis:
    def __init__(self) -> None:
        self.calls = []

    async def enqueue_job(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return object()

    async def publish(self, channel, payload):
        self.calls.append((("publish", channel, payload), {}))


def test_arq_client_dispatches_only_job_id_and_uses_stable_deduplication_key() -> None:
    redis = FakeArqRedis()
    job_id = uuid4()
    client = ArqQueueClient(redis)

    asyncio.run(client.enqueue_gpu_job(job_id))

    assert redis.calls == [
        (("run_gpu_job", str(job_id)), {"_job_id": f"gpu:{job_id}"})
    ]
