from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import exists, select

from backend.db.models import Job, JobEvent, JobStatus
from backend.db.session import get_session_factory
from backend.services.queue.client import ArqQueueClient
from backend.workers.gpu_tasks import GpuJobWorker, SqlAlchemyWorkerJobStore, run_gpu_job
from backend.workers.media_validation import validate_uploaded_media


async def recover_stuck_jobs(store, queue, *, stale_after_seconds: int = 300) -> int:
    """Small recovery port used by tests and alternate worker supervisors."""
    job_ids = await store.claim_stuck(stale_after_seconds)
    for job_id in job_ids:
        await queue.enqueue_gpu_job(job_id)
    return len(job_ids)


async def recover_dispatchable_jobs(queue: ArqQueueClient, *, stale_seconds: int = 300) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
    factory = get_session_factory()
    async with factory() as session, session.begin():
        recent_heartbeat = exists(
            select(JobEvent.id).where(
                JobEvent.job_id == Job.id,
                JobEvent.source == "gpu-worker-heartbeat",
                JobEvent.created_at >= cutoff,
            )
        )
        statement = (
            select(Job)
            .where(
                (Job.status == JobStatus.QUEUED)
                | (
                    (Job.status == JobStatus.PROCESSING)
                    & (Job.started_at < cutoff)
                    & ~recent_heartbeat
                )
            )
            .with_for_update(skip_locked=True)
        )
        jobs = list((await session.scalars(statement)).all())
        for job in jobs:
            if job.status is JobStatus.PROCESSING:
                job.status = JobStatus.QUEUED
                job.started_at = None
                job.last_message = "Recovered after stale worker heartbeat"
                session.add(JobEvent(job_id=job.id, status=JobStatus.QUEUED, progress=job.progress, message=job.last_message, source="recovery"))
        job_ids = [job.id for job in jobs]
    for job_id in job_ids:
        await queue.enqueue_gpu_job(job_id)
    return len(job_ids)


async def startup(ctx: dict[str, Any]) -> None:
    runner = ctx.get("gpu_runner")
    if runner is None:
        from backend.workers.production_runner import build_production_runner

        runner = build_production_runner()
    queue = ArqQueueClient(ctx["redis"])
    ctx["gpu_job_worker"] = GpuJobWorker(SqlAlchemyWorkerJobStore(), queue, runner)
    await recover_dispatchable_jobs(queue)


class WorkerSettings:
    functions = [run_gpu_job, validate_uploaded_media]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 1
    job_timeout = 6 * 60 * 60
    max_tries = 3
