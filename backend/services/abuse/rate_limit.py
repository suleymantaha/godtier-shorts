from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""
SCOPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class RateLimitStorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter(Protocol):
    async def consume(
        self,
        *,
        scope: str,
        subject: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision: ...

    async def status(
        self,
        *,
        scope: str,
        subject: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision: ...


class RedisFixedWindowRateLimiter:
    def __init__(
        self,
        redis_url: str,
        *,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._client_factory = client_factory

    async def consume(
        self,
        *,
        scope: str,
        subject: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        self._validate(scope, subject, limit, window_seconds)
        client = self._client()
        try:
            count, ttl = await client.eval(
                FIXED_WINDOW_SCRIPT,
                1,
                self._key(scope, subject),
                window_seconds,
            )
            return self._decision(
                int(count), int(ttl), limit, window_seconds, allow_at_limit=True
            )
        except RedisError as exc:
            raise RateLimitStorageError("rate limit storage is unavailable") from exc
        finally:
            await client.aclose()

    async def status(
        self,
        *,
        scope: str,
        subject: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        self._validate(scope, subject, limit, window_seconds)
        client = self._client()
        try:
            key = self._key(scope, subject)
            raw_count = await client.get(key)
            count = int(raw_count or 0)
            ttl = int(await client.ttl(key)) if count else window_seconds
            return self._decision(
                count, ttl, limit, window_seconds, allow_at_limit=False
            )
        except RedisError as exc:
            raise RateLimitStorageError("rate limit storage is unavailable") from exc
        finally:
            await client.aclose()

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        return Redis.from_url(self._redis_url, decode_responses=True)

    @staticmethod
    def _key(scope: str, subject: str) -> str:
        subject_hash = hashlib.sha256(
            f"rate-limit-v1:{scope}:{subject}".encode()
        ).hexdigest()
        return f"godtier:rate:{scope}:{subject_hash}"

    @staticmethod
    def _decision(
        count: int,
        ttl: int,
        limit: int,
        window_seconds: int,
        *,
        allow_at_limit: bool,
    ) -> RateLimitDecision:
        retry_after = ttl if ttl > 0 else window_seconds
        return RateLimitDecision(
            allowed=count <= limit if allow_at_limit else count < limit,
            remaining=max(0, limit - count),
            retry_after_seconds=retry_after,
        )

    @staticmethod
    def _validate(scope: str, subject: str, limit: int, window_seconds: int) -> None:
        if not SCOPE_PATTERN.fullmatch(scope):
            raise ValueError("rate limit scope is invalid")
        if not subject:
            raise ValueError("rate limit subject is required")
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("rate limit values must be positive")
