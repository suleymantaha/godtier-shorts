from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.rate_limit import enforce_rate_limit, get_rate_limiter
from backend.api.security import AuthContext, require_policy
from backend.core.source_url_policy import SourceUrlPolicy
from backend.db.models import (
    Asset,
    AssetKind,
    Job,
    JobEvent,
    JobStatus,
    JobType,
    Plan,
    Project,
    RiskEvent,
    SourceType,
    Subscription,
    SubscriptionStatus,
)
from backend.db.session import get_db_session
from backend.models.schemas import CancelJobRequest
from backend.services.abuse.rate_limit import RedisFixedWindowRateLimiter
from backend.services.billing import ledger
from backend.services.billing.pricing import JobPricingRequest, estimate_job_cost
from backend.services.billing.subscription_service import paid_entitlement_is_active
from backend.services.queue.client import ArqQueueClient
from backend.services.queue.job_service import (
    DistributedJobService,
    LedgerCreditReservations,
    SqlAlchemyJobRepository,
    SubmittedJob,
)

router = APIRouter(prefix="/api", tags=["jobs"])


class ProductionStartJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    num_clips: int = Field(ge=1, le=20)
    resolution: str = "1080p"
    layout: str = "auto"
    style_name: str = "TIKTOK"
    animation_type: str = "default"
    skip_subtitles: bool = False
    priority: bool = False


class ProductionJobGateway:
    def __init__(self, session: AsyncSession, queue: ArqQueueClient) -> None:
        self._session, self._queue = session, queue

    async def start(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        payload: ProductionStartJobRequest,
        idempotency_key: str,
    ) -> SubmittedJob:
        project = await self._session.scalar(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if not project.duration_seconds:
            raise HTTPException(status_code=422, detail="Project media validation is incomplete")
        if project.source_type is SourceType.YOUTUBE:
            await asyncio.to_thread(SourceUrlPolicy().validate, project.source_ref)
        else:
            source_asset = await self._session.scalar(
                select(Asset.id).where(
                    Asset.project_id == project_id,
                    Asset.user_id == user_id,
                    Asset.kind == AssetKind.SOURCE,
                )
            )
            if source_asset is None:
                raise HTTPException(status_code=422, detail="Validated source asset is required")

        latest_risk_decision = await self._session.scalar(
            select(RiskEvent)
            .where(
                RiskEvent.user_id == user_id,
                RiskEvent.signal == "risk_decision",
            )
            .order_by(RiskEvent.created_at.desc())
            .limit(1)
        )
        if _is_blocked(latest_risk_decision):
            raise HTTPException(status_code=403, detail="Account requires risk review")

        request_data = payload.model_dump(mode="json")
        existing = await self._session.scalar(
            select(Job)
            .where(
                Job.user_id == user_id,
                Job.project_id == project_id,
                Job.type == JobType.FULL_RENDER,
                Job.request == request_data,
                Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.COMPLETED]),
            )
            .order_by(Job.created_at.desc())
        )
        if existing is not None:
            result_status = (
                "cached"
                if existing.status is JobStatus.COMPLETED
                else existing.status.value
            )
            return SubmittedJob(existing.id, result_status)

        subscription_result = await self._session.execute(
            select(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]
                ),
            )
            .order_by(Subscription.created_at.desc())
        )
        row = subscription_result.first()
        if row is None or not paid_entitlement_is_active(
            row[0].status, grace_until=row[0].entitlement_grace_until
        ):
            raise HTTPException(status_code=402, detail="Paid entitlement required")
        _, plan = row
        active_jobs = await self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.user_id == user_id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]),
            )
        )
        if int(active_jobs or 0) >= plan.max_active_jobs:
            raise HTTPException(status_code=429, detail="Active job limit reached")
        estimate = estimate_job_cost(
            JobPricingRequest(
                job_type=JobType.FULL_RENDER,
                source_seconds=project.duration_seconds,
                requested_clips=payload.num_clips,
                resolution=payload.resolution,
                layout=payload.layout,
                priority=payload.priority,
            ),
            plan,
        )
        return await DistributedJobService(
            SqlAlchemyJobRepository(), LedgerCreditReservations(), self._queue
        ).submit(
            user_id=user_id,
            project_id=project_id,
            job_type=JobType.FULL_RENDER.value,
            request=request_data,
            estimated_credits=estimate.wallet_credits,
            idempotency_key=idempotency_key,
        )

    async def cancel(self, *, user_id: UUID, job_id: UUID) -> str:
        job = await self._session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.user_id == user_id)
            .with_for_update()
        )
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status is JobStatus.CANCELLED:
            await self._settle_cancelled_reservation(job)
            return "cancelled"
        if job.status in {
            JobStatus.COMPLETED,
            JobStatus.ERROR,
            JobStatus.REVIEW_REQUIRED,
        }:
            return "ignored"
        previous = job.status
        await self._queue.cancel_gpu_job(job_id)
        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.now(timezone.utc)
        job.last_message = "Cancelled by user"
        self._session.add(
            JobEvent(
                job_id=job.id,
                status=JobStatus.CANCELLED,
                progress=job.progress,
                message=job.last_message,
                source="api",
            )
        )
        await self._session.commit()
        await self._settle_cancelled_reservation(job, previous_status=previous)
        return "cancelled"

    async def _settle_cancelled_reservation(
        self,
        job: Job,
        *,
        previous_status: JobStatus | None = None,
    ) -> None:
        reserved = job.reserved_credits
        if reserved > 0:
            was_queued = (
                previous_status is JobStatus.QUEUED
                if previous_status is not None
                else job.started_at is None
            )
            if was_queued:
                await ledger.release(
                    job.user_id,
                    job.id,
                    f"release:cancel:{job.id}",
                )
            else:
                await ledger.settle(
                    job.user_id,
                    job.id,
                    reserved,
                    f"settle:cancel:{job.id}",
                )


async def get_job_gateway(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[ProductionJobGateway]:
    pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
    try:
        yield ProductionJobGateway(session, ArqQueueClient(pool))
    finally:
        await pool.aclose()


def _user_id(auth: AuthContext) -> UUID:
    if auth.user_id is None:
        raise HTTPException(status_code=503, detail="Database identity unavailable")
    return auth.user_id


def _is_blocked(event: RiskEvent | None) -> bool:
    if event is None or not isinstance(event.metadata_json, dict):
        return False
    return event.metadata_json.get("decision") == "block"


@router.post("/start-job")
async def start_job(
    payload: ProductionStartJobRequest,
    auth: Annotated[AuthContext, Depends(require_policy("start_job"))],
    gateway: Annotated[ProductionJobGateway, Depends(get_job_gateway)],
    limiter: Annotated[RedisFixedWindowRateLimiter, Depends(get_rate_limiter)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ],
):
    idempotency_key = idempotency_key.strip()
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")
    user_id = _user_id(auth)
    await enforce_rate_limit(
        limiter,
        scope="start_job",
        subject=str(user_id),
        limit=int(os.getenv("JOB_START_REQUEST_LIMIT", "10")),
        window_seconds=int(os.getenv("JOB_START_REQUEST_WINDOW_SECONDS", "60")),
    )
    result = await gateway.start(
        user_id=user_id,
        project_id=payload.project_id,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    return {
        "status": result.status,
        "job_id": str(result.id),
        "project_id": str(payload.project_id),
        "cache_hit": result.status == "cached",
    }


@router.post("/cancel-job/{job_id}")
async def cancel_job(
    job_id: UUID,
    payload: CancelJobRequest,
    auth: Annotated[AuthContext, Depends(require_policy("cancel_job"))],
    gateway: Annotated[ProductionJobGateway, Depends(get_job_gateway)],
):
    if payload.confirmed is not True:
        raise HTTPException(status_code=400, detail="Cancel confirmation required")
    result = await gateway.cancel(user_id=_user_id(auth), job_id=job_id)
    return {"status": result}
