from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.security import AuthContext, authenticate_request
from backend.api.routes.security_gate import get_turnstile_verifier, verify_or_raise
from backend.db.session import get_db_session
from backend.services.preview.adapters import (
    DisabledLimitedTranscriber,
    LocalPreviewAnalyzer,
    RemoteLimitedTranscriber,
    YtDlpCaptionSource,
)
from backend.services.preview.repository import SqlAlchemyPreviewEntitlements
from backend.services.preview.rate_limit import RedisPreviewRateLimiter
from backend.services.preview.service import (
    PreviewAlreadyUsedError,
    PreviewError,
    PreviewMetadata,
    PreviewRateLimitedError,
    PreviewResult,
    PreviewService,
)
from backend.services.abuse.turnstile import TurnstileVerifier


router = APIRouter(prefix="/api/preview", tags=["preview"])


class PreviewAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
    turnstile_token: str = Field(min_length=1, max_length=2048)


class PreviewAnalyzeResponse(BaseModel):
    source: PreviewMetadata
    transcript: list[dict[str, Any]]
    transcript_source: str
    candidates: list[dict[str, Any]]
    preview_mode: str


async def get_preview_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PreviewService:
    transcription_enabled = os.getenv(
        "PREVIEW_LIMITED_TRANSCRIPTION_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    transcriber = (
        RemoteLimitedTranscriber(
            endpoint_url=os.getenv("PREVIEW_TRANSCRIPTION_ENDPOINT_URL", ""),
            api_key=os.getenv("PREVIEW_TRANSCRIPTION_API_KEY", ""),
            model=os.getenv("PREVIEW_TRANSCRIPTION_MODEL", "whisper-1"),
            timeout_seconds=int(os.getenv("PREVIEW_TRANSCRIPTION_TIMEOUT_SECONDS", "60")),
        )
        if transcription_enabled
        else DisabledLimitedTranscriber()
    )
    return PreviewService(
        source=YtDlpCaptionSource(
            timeout_seconds=int(os.getenv("PREVIEW_METADATA_TIMEOUT_SECONDS", "30"))
        ),
        entitlements=SqlAlchemyPreviewEntitlements(session),
        transcriber=transcriber,
        analyzer=LocalPreviewAnalyzer(),
        rate_limiter=RedisPreviewRateLimiter(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            window_seconds=int(os.getenv("PREVIEW_REQUEST_WINDOW_SECONDS", "30")),
        ),
        max_source_seconds=int(os.getenv("PREVIEW_MAX_SOURCE_SECONDS", "3600")),
        max_transcription_seconds=int(
            os.getenv("PREVIEW_MAX_TRANSCRIPTION_SECONDS", "900")
        ),
    )


@router.post("/analyze", response_model=PreviewAnalyzeResponse)
async def analyze_preview(
    payload: PreviewAnalyzeRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    service: Annotated[PreviewService, Depends(get_preview_service)],
    verifier: Annotated[TurnstileVerifier, Depends(get_turnstile_verifier)],
) -> PreviewResult:
    if auth.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preview identity unavailable",
        )
    await verify_or_raise(
        verifier,
        token=payload.turnstile_token,
        action="preview_analyze",
        remote_ip=request.client.host if request.client else None,
    )
    try:
        return await service.analyze(
            url=payload.url, user_id=auth.user_id, identity=auth.subject
        )
    except (PreviewAlreadyUsedError, PreviewRateLimitedError) as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PreviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Preview provider unavailable") from exc
