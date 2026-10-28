from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID

from arq import Retry
from sqlalchemy import select

from backend.db.models import Job, JobEvent, JobStatus, User, UserStatus
from backend.db.session import get_session_factory
from backend.services.billing import ledger
from backend.services.queue.client import QueueClient


class DeterministicJobError(RuntimeError):
    pass


class PostRenderStorageQuotaError(DeterministicJobError):
    """GPU work finished, so publication rejection must consume reserved credits."""


class TransientJobError(RuntimeError):
    pass


class WorkerJobStore(Protocol):
    async def claim(self, job_id: UUID) -> dict[str, Any]: ...
    async def heartbeat(self, job_id: UUID) -> None: ...
    async def progress(self, job_id: UUID, value: int, message: str) -> None: ...
    async def complete(self, job_id: UUID) -> None: ...
    async def fail(self, job_id: UUID, code: str, message: str) -> None: ...
    async def settle(self, job_id: UUID) -> None: ...
    async def settle_failure(self, job_id: UUID, code: str, message: str) -> None: ...
    async def release(self, job_id: UUID) -> None: ...


ProgressReporter = Callable[[int, str], Awaitable[None]]
GpuRunner = Callable[[dict[str, Any], ProgressReporter], Awaitable[None]]


class GpuJobWorker:
    def __init__(self, store: WorkerJobStore, publisher: QueueClient, runner: GpuRunner,
                 *, heartbeat_seconds: int = 30) -> None:
        self._store = store
        self._publisher = publisher
        self._runner = runner
        self._heartbeat_seconds = heartbeat_seconds

    async def execute(self, job_id: UUID, *, retry_count: int = 0) -> None:
        request = await self._store.claim(job_id)
        request["_retry_count"] = max(0, int(retry_count))
        await self._store.heartbeat(job_id)
        stopped = asyncio.Event()

        async def heartbeat_loop() -> None:
            while not stopped.is_set():
                try:
                    await asyncio.wait_for(stopped.wait(), timeout=self._heartbeat_seconds)
                except TimeoutError:
                    await self._store.heartbeat(job_id)

        async def report(progress: int, message: str) -> None:
            value = max(0, min(100, int(progress)))
            await self._store.progress(job_id, value, message)
            await self._publisher.publish_progress(
                job_id,
                {"status": "processing", "progress": value, "message": message},
            )

        heartbeat_task = asyncio.create_task(heartbeat_loop())
        try:
            await self._runner(request, report)
        except PostRenderStorageQuotaError as exc:
            await self._store.settle_failure(job_id, "OUTPUT_STORAGE_QUOTA_EXCEEDED", str(exc))
            return
        except DeterministicJobError as exc:
            await self._store.fail(job_id, "DETERMINISTIC_ERROR", str(exc))
            await self._store.release(job_id)
            return
        except TransientJobError as exc:
            if retry_count >= 2:
                await self._store.fail(job_id, "RETRY_EXHAUSTED", str(exc))
                await self._store.release(job_id)
                return
            raise Retry(defer=30) from exc
        except Exception as exc:
            await self._store.fail(job_id, "UNEXPECTED_WORKER_ERROR", str(exc))
            await self._store.release(job_id)
            return
        else:
            await self._store.settle(job_id)
            await self._store.complete(job_id)
        finally:
            stopped.set()
            await heartbeat_task


class SqlAlchemyWorkerJobStore:
    async def _locked_job(self, session, job_id: UUID) -> Job:
        job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            raise DeterministicJobError("Job not found")
        return job

    async def claim(self, job_id: UUID) -> dict[str, Any]:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            user_id = await session.scalar(select(Job.user_id).where(Job.id == job_id))
            user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None or user.status is not UserStatus.ACTIVE:
                raise DeterministicJobError("Account is not active")
            job = await self._locked_job(session, job_id)
            if job.status not in {JobStatus.QUEUED, JobStatus.PROCESSING}:
                raise DeterministicJobError(f"Job is not runnable: {job.status.value}")
            if job.reserved_credits <= 0:
                raise DeterministicJobError("Job has no active credit reservation")
            job.status = JobStatus.PROCESSING
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.last_message = "GPU worker started"
            session.add(JobEvent(job_id=job.id, status=job.status, progress=job.progress, message=job.last_message, source="gpu-worker"))
            request = dict(job.request)
            request.update(
                {
                    "_job_id": str(job.id),
                    "_user_id": str(job.user_id),
                    "_project_id": str(job.project_id),
                }
            )
            return request

    async def heartbeat(self, job_id: UUID) -> None:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            job = await self._locked_job(session, job_id)
            session.add(JobEvent(job_id=job.id, status=job.status, progress=job.progress, message="heartbeat", source="gpu-worker-heartbeat"))

    async def progress(self, job_id: UUID, value: int, message: str) -> None:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            job = await self._locked_job(session, job_id)
            job.progress, job.last_message = value, message
            session.add(JobEvent(job_id=job.id, status=job.status, progress=value, message=message, source="gpu-worker"))

    async def complete(self, job_id: UUID) -> None:
        await self._finish(job_id, JobStatus.COMPLETED, None, "Job completed")

    async def fail(self, job_id: UUID, code: str, message: str) -> None:
        await self._finish(job_id, JobStatus.ERROR, code, message)

    async def _reservation(self, job_id: UUID) -> tuple[UUID, int]:
        factory = get_session_factory()
        async with factory() as session:
            job = await session.get(Job, job_id)
            if job is None:
                raise DeterministicJobError("Job not found")
            return job.user_id, job.reserved_credits

    async def settle(self, job_id: UUID) -> None:
        user_id, amount = await self._reservation(job_id)
        if amount > 0:
            await ledger.settle(user_id, job_id, amount, f"settle:worker:{job_id}")

    async def settle_failure(self, job_id: UUID, code: str, message: str) -> None:
        """Charge and mark ERROR atomically: recovery must never see paid success."""
        factory = get_session_factory()
        async with factory() as session, session.begin():
            user_id = await session.scalar(select(Job.user_id).where(Job.id == job_id))
            # Match admission/deletion's outer User fence. The ledger then takes
            # its existing wallet -> Job locks; never invert them here.
            await session.scalar(select(User).where(User.id == user_id).with_for_update())
            job = await session.get(Job, job_id)
            if job is None:
                raise DeterministicJobError("Job not found")
            if job.status is JobStatus.ERROR and job.error_code == code and job.settled_credits > 0:
                return
            if job.status is not JobStatus.PROCESSING or job.reserved_credits <= 0:
                raise DeterministicJobError("Job has no active credit reservation")
            await ledger.settle_in_session(
                session, user_id, job_id, job.reserved_credits, f"settle:worker:{job_id}")
            await self._finish_in_session(session, job_id, JobStatus.ERROR, code, message)

    async def release(self, job_id: UUID) -> None:
        user_id, amount = await self._reservation(job_id)
        if amount > 0:
            await ledger.release(user_id, job_id, f"release:worker:{job_id}")

    async def _finish(self, job_id: UUID, status: JobStatus, code: str | None, message: str) -> None:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            await self._finish_in_session(session, job_id, status, code, message)

    async def _finish_in_session(self, session, job_id, status, code, message) -> None:
        job = await self._locked_job(session, job_id)
        job.status, job.last_message = status, message
        job.error_code = code
        job.error_message = message if code else None
        job.progress = 100 if status is JobStatus.COMPLETED else job.progress
        job.finished_at = datetime.now(timezone.utc)
        session.add(JobEvent(job_id=job.id, status=status, progress=job.progress, message=message, source="gpu-worker"))


async def run_gpu_job(ctx: dict[str, Any], job_id: str) -> None:
    worker: GpuJobWorker = ctx["gpu_job_worker"]
    await worker.execute(UUID(job_id), retry_count=max(0, int(ctx.get("job_try", 1)) - 1))
