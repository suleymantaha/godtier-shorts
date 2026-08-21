from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import RedisError


class RedisPreviewRateLimiter:
    def __init__(self, redis_url: str, *, window_seconds: int) -> None:
        self._redis_url = redis_url
        self._window_seconds = window_seconds

    async def allow(self, *, identity_key_hash: str) -> bool:
        client = Redis.from_url(self._redis_url, decode_responses=True)
        try:
            result = await client.set(
                f"preview:rate:{identity_key_hash}",
                "1",
                ex=self._window_seconds,
                nx=True,
            )
            return bool(result)
        except RedisError as exc:
            raise RuntimeError("preview rate limit storage is unavailable") from exc
        finally:
            await client.aclose()
