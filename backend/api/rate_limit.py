from __future__ import annotations

import os

from fastapi import HTTPException, status

from backend.services.abuse.rate_limit import (
    RateLimiter,
    RateLimitStorageError,
    RedisFixedWindowRateLimiter,
)


def get_rate_limiter() -> RedisFixedWindowRateLimiter:
    return RedisFixedWindowRateLimiter(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )


async def enforce_rate_limit(
    limiter: RateLimiter,
    *,
    scope: str,
    subject: str,
    limit: int,
    window_seconds: int,
    consume: bool = True,
) -> None:
    try:
        operation = limiter.consume if consume else limiter.status
        decision = await operation(
            scope=scope,
            subject=subject,
            limit=limit,
            window_seconds=window_seconds,
        )
    except RateLimitStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit storage unavailable",
            headers={"Retry-After": "5"},
        ) from exc
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
