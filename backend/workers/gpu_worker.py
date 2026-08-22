from __future__ import annotations

import asyncio
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

from arq.connections import RedisSettings
from loguru import logger
from sqlalchemy import exists, select

from backend.db.models import Job, JobEvent, JobStatus
from backend.db.session import get_session_factory
from backend.config import LOGS_DIR
from backend.observability import capture_exception, configure_error_reporting, configure_logging
from backend.observability.monitor import GPU_WORKER_HEARTBEAT_KEY
from backend.services.queue.client import ArqQueueClient
from backend.workers.gpu_tasks import GpuJobWorker, SqlAlchemyWorkerJobStore, run_gpu_job
from backend.workers.media_validation import validate_uploaded_media


async def recover_stuck_jobs(store, queue, *, stale_after_seconds: int = 300) -> int:
    """Small recovery port used by tests and alternate worker supervisors."""
    job_ids = await store.claim_stuck(stale_after_seconds)
    for job_id in job_ids:
        await queue.enqueue_gpu_job(job_id)
    return len(job_ids)


async def publish_worker_heartbeat(
    redis: Any,
    *,
    worker_id: str,
    ttl_seconds: int,
) -> None:
    await redis.set(GPU_WORKER_HEARTBEAT_KEY, worker_id, ex=ttl_seconds)


async def _heartbeat_loop(ctx: dict[str, Any]) -> None:
    interval = int(os.getenv("GPU_WORKER_HEARTBEAT_SECONDS", "30"))
    ttl = int(os.getenv("GPU_WORKER_HEARTBEAT_TTL_SECONDS", "90"))
    worker_id = os.getenv("GPU_WORKER_ID", "").strip() or socket.gethostname()
    stop: asyncio.Event = ctx["gpu_heartbeat_stop"]
    while not stop.is_set():
        try:
            await publish_worker_heartbeat(
                ctx["redis"], worker_id=worker_id, ttl_seconds=ttl
            )
        except Exception as exc:
            logger.bind(event="gpu_worker_heartbeat_failed", worker_id=worker_id).error(
                "gpu worker heartbeat failed"
            )
            capture_exception(exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue


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
    configure_logging(os.getenv("APP_ENV", "development"), LOGS_DIR)
    configure_error_reporting()
    runner = ctx.get("gpu_runner")
    if runner is None:
        from backend.workers.production_runner import build_production_runner

        runner = build_production_runner()
    queue = ArqQueueClient(ctx["redis"])
    ctx["gpu_job_worker"] = GpuJobWorker(SqlAlchemyWorkerJobStore(), queue, runner)
    await recover_dispatchable_jobs(queue)
    ctx["gpu_heartbeat_stop"] = asyncio.Event()
    ctx["gpu_heartbeat_task"] = asyncio.create_task(_heartbeat_loop(ctx))


async def shutdown(ctx: dict[str, Any]) -> None:
    stop = ctx.get("gpu_heartbeat_stop")
    task = ctx.get("gpu_heartbeat_task")
    if stop is not None:
        stop.set()
    if task is not None:
        await task


class WorkerSettings:
    functions = [run_gpu_job, validate_uploaded_media]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 1
    job_timeout = 6 * 60 * 60
    max_tries = 3
