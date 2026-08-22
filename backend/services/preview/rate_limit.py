from __future__ import annotations

from backend.services.abuse.rate_limit import RedisFixedWindowRateLimiter


class RedisPreviewRateLimiter:
    def __init__(self, redis_url: str, *, window_seconds: int, limit: int = 1) -> None:
        self._limiter = RedisFixedWindowRateLimiter(redis_url)
        self._window_seconds = window_seconds
        self._limit = limit

    async def allow(self, *, identity_key_hash: str) -> bool:
        decision = await self._limiter.consume(
            scope="preview",
            subject=identity_key_hash,
            limit=self._limit,
            window_seconds=self._window_seconds,
        )
        return decision.allowed
