from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Iterable

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.security import AuthContext, require_policy
from backend.db.models import Job, JobStatus, JobUsageMetric
from backend.db.session import get_db_session


router = APIRouter(prefix="/api/admin", tags=["admin"])
_SIX_PLACES = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class EconomicsRow:
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    source_seconds: int
    render_seconds: int
    output_count: int
    estimated_cost: Decimal


class JobEconomicsResponse(BaseModel):
    total_jobs: int
    success_rate: float
    review_required_rate: float
    cost_per_source_hour_usd: Decimal
    cost_per_short_usd: Decimal
    average_queue_wait_seconds: float
    average_render_seconds: float


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0.000000")
    return (numerator / denominator).quantize(_SIX_PLACES, rounding=ROUND_HALF_UP)


def aggregate_job_economics(rows: Iterable[EconomicsRow]) -> JobEconomicsResponse:
    values = list(rows)
    total = len(values)
    successful = sum(row.status in {JobStatus.COMPLETED, JobStatus.REVIEW_REQUIRED} for row in values)
    review_required = sum(row.status is JobStatus.REVIEW_REQUIRED for row in values)
    total_cost = sum((row.estimated_cost for row in values), Decimal(0))
    source_hours = Decimal(sum(row.source_seconds for row in values)) / Decimal(3600)
    outputs = Decimal(sum(row.output_count for row in values))
    queue_waits = [(row.started_at - row.created_at).total_seconds() for row in values if row.started_at]
    renders = [row.render_seconds for row in values if row.render_seconds > 0]
    return JobEconomicsResponse(
        total_jobs=total,
        success_rate=successful / total if total else 0.0,
        review_required_rate=review_required / total if total else 0.0,
        cost_per_source_hour_usd=_ratio(total_cost, source_hours),
        cost_per_short_usd=_ratio(total_cost, outputs),
        average_queue_wait_seconds=sum(queue_waits) / len(queue_waits) if queue_waits else 0.0,
        average_render_seconds=sum(renders) / len(renders) if renders else 0.0,
    )


@router.get("/job-economics", response_model=JobEconomicsResponse)
async def get_job_economics(
    _auth: Annotated[AuthContext, Depends(require_policy("admin"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobEconomicsResponse:
    result = await session.execute(
        select(
            Job.status,
            Job.created_at,
            Job.started_at,
            JobUsageMetric.source_seconds,
            JobUsageMetric.render_seconds,
            JobUsageMetric.output_count,
            JobUsageMetric.estimated_internal_cost_usd,
        ).outerjoin(JobUsageMetric, JobUsageMetric.job_id == Job.id)
    )
    return aggregate_job_economics(
        EconomicsRow(
            status,
            created_at,
            started_at,
            source_seconds or 0,
            render_seconds or 0,
            output_count or 0,
            estimated_cost or Decimal(0),
        )
        for status, created_at, started_at, source_seconds, render_seconds, output_count, estimated_cost in result.all()
    )
