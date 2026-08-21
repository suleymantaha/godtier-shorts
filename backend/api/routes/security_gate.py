from __future__ import annotations

import os
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.services.abuse.turnstile import (
    TurnstileProviderError,
    TurnstileValidationError,
    TurnstileVerifier,
)


router = APIRouter(prefix="/api/security/turnstile", tags=["security"])


class TurnstileVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=2048)
    action: Literal["signup"]


class TurnstileVerifyResponse(BaseModel):
    verified: bool


def get_turnstile_verifier() -> TurnstileVerifier:
    frontend_url = os.getenv("FRONTEND_URL", "").strip()
    expected_hostname = urlparse(frontend_url).hostname if frontend_url else None
    return TurnstileVerifier(
        secret_key=os.getenv("TURNSTILE_SECRET_KEY", ""),
        expected_hostname=expected_hostname,
        timeout_seconds=float(os.getenv("TURNSTILE_TIMEOUT_SECONDS", "8")),
    )


async def verify_or_raise(
    verifier: TurnstileVerifier,
    *,
    token: str,
    action: str,
    remote_ip: str | None,
) -> None:
    try:
        await verifier.validate(
            token,
            expected_action=action,
            remote_ip=remote_ip,
        )
    except TurnstileValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Turnstile verification failed",
        ) from exc
    except TurnstileProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Turnstile provider unavailable",
        ) from exc


@router.post("/verify", response_model=TurnstileVerifyResponse)
async def verify_turnstile(
    payload: TurnstileVerifyRequest,
    request: Request,
    verifier: Annotated[TurnstileVerifier, Depends(get_turnstile_verifier)],
) -> TurnstileVerifyResponse:
    await verify_or_raise(
        verifier,
        token=payload.token,
        action=payload.action,
        remote_ip=request.client.host if request.client else None,
    )
    return TurnstileVerifyResponse(verified=True)
