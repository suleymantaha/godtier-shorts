from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.db.models import Job, JobEvent, JobStatus, JobType
from backend.db.session import get_session_factory
from backend.services.billing import ledger

from backend.services.queue.client import QueueClient, QueueDispatchError


class JobRepository(Protocol):
    async def create_queued(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        job_type: str,
        request: dict[str, Any],
        idempotency_key: str,
    ) -> DurableJob | UUID: ...

    async def mark_dispatch_failed(self, job_id: UUID, message: str) -> None: ...


class CreditReservations(Protocol):
    async def reserve(
        self,
        *,
        user_id: UUID,
        amount: int,
        job_id: UUID,
        idempotency_key: str,
    ) -> None: ...

    async def release(
        self, *, user_id: UUID, job_id: UUID, idempotency_key: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class SubmittedJob:
    id: UUID
    status: str = "queued"


@dataclass(frozen=True, slots=True)
class DurableJob:
    id: UUID
    created: bool


class DistributedJobService:
    def __init__(
        self,
        jobs: JobRepository,
        credits: CreditReservations,
        queue: QueueClient,
    ) -> None:
        self._jobs = jobs
        self._credits = credits
        self._queue = queue

    async def submit(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        job_type: str,
        request: dict[str, Any],
        estimated_credits: int,
        idempotency_key: str,
    ) -> SubmittedJob:
        if estimated_credits <= 0:
            raise ValueError("estimated_credits must be positive")
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise ValueError("idempotency_key must not be blank")
        durable = await self._jobs.create_queued(
            user_id=user_id,
            project_id=project_id,
            job_type=job_type,
            request=request,
            idempotency_key=idempotency_key,
        )
        job_id = durable.id if isinstance(durable, DurableJob) else durable
        if isinstance(durable, DurableJob) and not durable.created:
            return SubmittedJob(job_id)
        try:
            await self._credits.reserve(
                user_id=user_id,
                amount=estimated_credits,
                job_id=job_id,
                idempotency_key=f"reserve:{idempotency_key}",
            )
        except Exception:
            await self._jobs.mark_dispatch_failed(job_id, "Credit reservation failed")
            raise
        try:
            await self._queue.enqueue_gpu_job(job_id)
        except QueueDispatchError as exc:
            await self._jobs.mark_dispatch_failed(job_id, str(exc))
            await self._credits.release(
                user_id=user_id,
                job_id=job_id,
                idempotency_key=f"release:dispatch:{job_id}",
            )
            raise
        return SubmittedJob(job_id)


class SqlAlchemyJobRepository:
    async def create_queued(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        job_type: str,
        request: dict[str, Any],
        idempotency_key: str,
    ) -> DurableJob:
        factory = get_session_factory()
        async with factory() as session:
            existing = await session.scalar(
                select(Job).where(
                    Job.user_id == user_id,
                    Job.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.project_id != project_id or existing.type != JobType(job_type) or existing.request != request:
                    raise ValueError("Idempotency key was already used for another job request")
                return DurableJob(existing.id, created=False)

        job_id = uuid4()
        try:
            async with factory() as session, session.begin():
                session.add(Job(
                    id=job_id,
                    user_id=user_id,
                    project_id=project_id,
                    type=JobType(job_type),
                    status=JobStatus.QUEUED,
                    request=request,
                    idempotency_key=idempotency_key,
                    progress=0,
                    last_message="Job queued",
                ))
                session.add(JobEvent(
                    job_id=job_id,
                    status=JobStatus.QUEUED,
                    progress=0,
                    message="Job queued",
                    source="api",
                ))
        except IntegrityError:
            async with factory() as session:
                existing = await session.scalar(
                    select(Job).where(Job.user_id == user_id, Job.idempotency_key == idempotency_key)
                )
                if existing is None or existing.project_id != project_id or existing.type != JobType(job_type) or existing.request != request:
                    raise ValueError("Idempotency key conflict")
                return DurableJob(existing.id, created=False)
        return DurableJob(job_id, created=True)

    async def mark_dispatch_failed(self, job_id: UUID, message: str) -> None:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            job = await session.scalar(
                select(Job).where(Job.id == job_id).with_for_update()
            )
            if job is None:
                return
            job.status = JobStatus.ERROR
            job.error_code = "QUEUE_DISPATCH_FAILED"
            job.error_message = message
            job.last_message = "Job could not be dispatched"
            job.finished_at = datetime.now(timezone.utc)
            session.add(
                JobEvent(
                    job_id=job_id,
                    status=JobStatus.ERROR,
                    progress=job.progress,
                    message=job.last_message,
                    source="api",
                )
            )


class LedgerCreditReservations:
    async def reserve(self, **kwargs) -> None:
        await ledger.reserve(**kwargs)

    async def release(self, **kwargs) -> None:
        await ledger.release(**kwargs)


__all__ = ["DistributedJobService", "QueueDispatchError", "SubmittedJob"]
