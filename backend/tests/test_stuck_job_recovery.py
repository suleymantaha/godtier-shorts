from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.workers.gpu_worker import recover_stuck_jobs


class FakeStore:
    async def claim_stuck(self, stale_after_seconds):
        assert stale_after_seconds == 300
        return [uuid4(), uuid4()]


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_gpu_job(self, job_id):
        self.jobs.append(job_id)


def test_stuck_jobs_are_claimed_from_postgres_and_requeued() -> None:
    queue = FakeQueue()
    count = asyncio.run(recover_stuck_jobs(FakeStore(), queue, stale_after_seconds=300))

    assert count == 2
    assert len(queue.jobs) == 2
