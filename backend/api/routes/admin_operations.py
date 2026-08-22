from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.billing import get_iyzico_client
from backend.api.security import AuthContext, require_policy
from backend.db.session import get_db_session
from backend.services.admin_operations import (
    AdminOperationError,
    AdminService,
    AuditContext,
    SqlAlchemyAdminService,
)
from backend.services.billing.ledger import LedgerError
from backend.services.queue.client import ArqQueueClient


router = APIRouter(prefix="/api/admin", tags=["admin"])


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 10:
            raise ValueError("reason en az 10 karakter olmali")
        return normalized


class CreditAdjustmentRequest(ReasonRequest):
    amount: int = Field(ge=-1_000_000, le=1_000_000)

    @field_validator("amount")
    @classmethod
    def nonzero_amount(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount sifir olamaz")
        return value


class OverviewResponse(BaseModel):
    users: int
    subscriptions: int
    jobs: int
    failed_jobs: int
    risk_events: int
    recent_users: list[dict] = Field(default_factory=list)
    recent_subscriptions: list[dict] = Field(default_factory=list)
    recent_jobs: list[dict] = Field(default_factory=list)
    recent_risk_events: list[dict] = Field(default_factory=list)


class CreditAdjustmentResponse(BaseModel):
    available_credits: int


class SubscriptionSyncResponse(BaseModel):
    status: str


class RedisAdminQueue:
    async def enqueue_gpu_job(self, job_id: UUID) -> None:
        pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
        try:
            await ArqQueueClient(pool).enqueue_gpu_job(job_id)
        finally:
            await pool.aclose()


class LazyIyzicoAdminProvider:
    async def get_subscription(self, reference_code: str):
        return await get_iyzico_client().get_subscription(reference_code)


async def get_admin_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminService:
    return SqlAlchemyAdminService(session, LazyIyzicoAdminProvider(), RedisAdminQueue())


def _audit_context(request: Request, auth: AuthContext) -> AuditContext:
    request_id = str(
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or "missing-request-id"
    )[:120]
    return AuditContext(actor_id=auth.user_id, request_id=request_id)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, AdminOperationError):
        message = str(exc)
        code = 404 if "bulunamadi" in message else 409
        return HTTPException(status_code=code, detail=message)
    if isinstance(exc, LedgerError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=502, detail="Admin operation dependency unavailable")


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    _auth: Annotated[AuthContext, Depends(require_policy("admin"))],
    service: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    return await service.overview()


@router.post("/users/{user_id}/credit-adjustments", response_model=CreditAdjustmentResponse)
async def adjust_credit(
    user_id: UUID,
    payload: CreditAdjustmentRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_policy("admin"))],
    service: Annotated[AdminService, Depends(get_admin_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> CreditAdjustmentResponse:
    try:
        available = await service.adjust_credit(
            user_id,
            payload.amount,
            reason=payload.reason,
            idempotency_key=idempotency_key,
            audit=_audit_context(request, auth),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return CreditAdjustmentResponse(available_credits=available)


@router.post("/users/{user_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
async def suspend_user(
    user_id: UUID,
    payload: ReasonRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_policy("admin"))],
    service: Annotated[AdminService, Depends(get_admin_service)],
) -> Response:
    try:
        await service.suspend_user(user_id, reason=payload.reason, audit=_audit_context(request, auth))
    except Exception as exc:
        raise _error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/subscriptions/{subscription_id}/sync", response_model=SubscriptionSyncResponse)
async def sync_subscription(
    subscription_id: UUID,
    payload: ReasonRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_policy("admin"))],
    service: Annotated[AdminService, Depends(get_admin_service)],
) -> SubscriptionSyncResponse:
    try:
        result = await service.sync_subscription(
            subscription_id,
            reason=payload.reason,
            audit=_audit_context(request, auth),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return SubscriptionSyncResponse(status=result)


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_job(
    job_id: UUID,
    payload: ReasonRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_policy("admin"))],
    service: Annotated[AdminService, Depends(get_admin_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> dict[str, str]:
    try:
        await service.retry_failed_job(
            job_id,
            reason=payload.reason,
            idempotency_key=idempotency_key,
            audit=_audit_context(request, auth),
        )
    except Exception as exc:
        raise _error(exc) from exc
    return {"status": "queued"}
