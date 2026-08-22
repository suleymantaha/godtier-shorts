from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from arq import Retry

from backend.workers.gpu_tasks import (
    DeterministicJobError,
    GpuJobWorker,
    TransientJobError,
)


class FakeStore:
    def __init__(self) -> None:
        self.events = []

    async def claim(self, job_id):
        self.events.append(("claim", job_id))
        return {"source": "private-object"}

    async def heartbeat(self, job_id): self.events.append(("heartbeat", job_id))
    async def progress(self, job_id, value, message): self.events.append(("progress", value, message))
    async def complete(self, job_id): self.events.append(("complete", job_id))
    async def fail(self, job_id, code, message): self.events.append(("fail", code, message))
    async def settle(self, job_id): self.events.append(("settle", job_id))
    async def release(self, job_id): self.events.append(("release", job_id))


class FakePublisher:
    def __init__(self) -> None: self.events = []
    async def publish_progress(self, job_id, event): self.events.append((job_id, event))


def test_worker_loads_request_records_progress_and_completes() -> None:
    store, publisher = FakeStore(), FakePublisher()

    async def runner(request, report):
        assert request == {"source": "private-object", "_retry_count": 0}
        await report(40, "tracking")

    job_id = uuid4()
    asyncio.run(GpuJobWorker(store, publisher, runner).execute(job_id))

    assert [event[0] for event in store.events] == ["claim", "heartbeat", "progress", "settle", "complete"]
    assert publisher.events[0][1] == {"status": "processing", "progress": 40, "message": "tracking"}


def test_worker_passes_retry_count_to_usage_instrumentation() -> None:
    observed = {}

    async def runner(request, _report):
        observed.update(request)

    asyncio.run(GpuJobWorker(FakeStore(), FakePublisher(), runner).execute(uuid4(), retry_count=3))

    assert observed["_retry_count"] == 3


def test_deterministic_failure_is_terminal_and_not_retried() -> None:
    store = FakeStore()
    async def runner(_request, _report): raise DeterministicJobError("bad media")

    asyncio.run(GpuJobWorker(store, FakePublisher(), runner).execute(uuid4()))

    assert any(event[:2] == ("fail", "DETERMINISTIC_ERROR") for event in store.events)
    assert store.events[-1][0] == "release"


def test_transient_failure_requests_arq_retry_without_terminal_failure() -> None:
    store = FakeStore()
    async def runner(_request, _report): raise TransientJobError("r2 timeout")

    with pytest.raises(Retry):
        asyncio.run(GpuJobWorker(store, FakePublisher(), runner).execute(uuid4()))

    assert not any(event[0] == "fail" for event in store.events)
    assert not any(event[0] == "release" for event in store.events)


def test_unexpected_failure_is_recorded_and_remains_observable() -> None:
    store = FakeStore()
    async def runner(_request, _report): raise RuntimeError("pipeline exploded")

    asyncio.run(GpuJobWorker(store, FakePublisher(), runner).execute(uuid4()))

    assert any(event[:2] == ("fail", "UNEXPECTED_WORKER_ERROR") for event in store.events)
    assert store.events[-1][0] == "release"
