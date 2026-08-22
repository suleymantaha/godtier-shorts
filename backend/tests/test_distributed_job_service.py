from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from backend.services.queue.job_service import DistributedJobService, QueueDispatchError


class FakeJobs:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.failed: list[UUID] = []

    async def create_queued(self, **_kwargs) -> UUID:
        self.events.append("durable_job")
        return uuid4()

    async def mark_dispatch_failed(self, job_id: UUID, message: str) -> None:
        self.events.append("job_error")
        self.failed.append(job_id)


class FakeCredits:
    def __init__(self, events: list[str], *, fail=False) -> None:
        self.events = events
        self.fail = fail

    async def reserve(self, **_kwargs) -> None:
        self.events.append("reserve")
        if self.fail:
            raise RuntimeError("no credits")

    async def release(self, **_kwargs) -> None:
        self.events.append("release")


class FakeQueue:
    def __init__(self, events: list[str], *, fail=False) -> None:
        self.events = events
        self.fail = fail

    async def enqueue_gpu_job(self, job_id: UUID) -> None:
        self.events.append("enqueue")
        if self.fail:
            raise QueueDispatchError("redis unavailable")


def test_job_is_reserved_before_redis_dispatch() -> None:
    events: list[str] = []
    service = DistributedJobService(FakeJobs(events), FakeCredits(events), FakeQueue(events))

    asyncio.run(
        service.submit(
            user_id=uuid4(), project_id=uuid4(), job_type="full_render",
            request={"source": "asset"}, estimated_credits=20,
            idempotency_key="job-request-1",
        )
    )

    assert events == ["durable_job", "reserve", "enqueue"]


def test_failed_reservation_never_reaches_redis() -> None:
    events: list[str] = []
    service = DistributedJobService(
        FakeJobs(events), FakeCredits(events, fail=True), FakeQueue(events)
    )

    with pytest.raises(RuntimeError, match="no credits"):
        asyncio.run(
            service.submit(
                user_id=uuid4(), project_id=uuid4(), job_type="full_render",
                request={}, estimated_credits=20, idempotency_key="job-request-2",
            )
        )

    assert events == ["durable_job", "reserve", "job_error"]


def test_redis_failure_marks_job_failed_and_releases_reservation() -> None:
    events: list[str] = []
    jobs = FakeJobs(events)
    service = DistributedJobService(
        jobs, FakeCredits(events), FakeQueue(events, fail=True)
    )

    with pytest.raises(QueueDispatchError):
        asyncio.run(
            service.submit(
                user_id=uuid4(), project_id=uuid4(), job_type="full_render",
                request={}, estimated_credits=20, idempotency_key="job-request-3",
            )
        )

    assert events == ["durable_job", "reserve", "enqueue", "job_error", "release"]
    assert len(jobs.failed) == 1
