from __future__ import annotations

import asyncio

import pytest
from redis.exceptions import RedisError

from backend.services.abuse.rate_limit import (
    RateLimitStorageError,
    RedisFixedWindowRateLimiter,
)


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.closed = False
        self.fail = False

    async def eval(self, _script: str, _keys: int, key: str, window: int):
        if self.fail:
            raise RedisError("unavailable")
        self.counts[key] = self.counts.get(key, 0) + 1
        self.ttls.setdefault(key, int(window))
        return [self.counts[key], self.ttls[key]]

    async def get(self, key: str):
        if self.fail:
            raise RedisError("unavailable")
        return self.counts.get(key)

    async def ttl(self, key: str):
        return self.ttls.get(key, -2)

    async def aclose(self) -> None:
        self.closed = True


def test_fixed_window_counter_is_subject_hashed_and_denies_after_limit() -> None:
    redis = FakeRedis()
    limiter = RedisFixedWindowRateLimiter(
        "redis://unused", client_factory=lambda: redis
    )

    first = asyncio.run(
        limiter.consume(scope="preview", subject="user@example.com", limit=2, window_seconds=30)
    )
    second = asyncio.run(
        limiter.consume(scope="preview", subject="user@example.com", limit=2, window_seconds=30)
    )
    denied = asyncio.run(
        limiter.consume(scope="preview", subject="user@example.com", limit=2, window_seconds=30)
    )

    assert first.allowed is True and first.remaining == 1
    assert second.allowed is True and second.remaining == 0
    assert denied.allowed is False and denied.retry_after_seconds == 30
    key = next(iter(redis.counts))
    assert key.startswith("godtier:rate:preview:")
    assert "user@example.com" not in key


def test_status_does_not_consume_failure_budget() -> None:
    redis = FakeRedis()
    limiter = RedisFixedWindowRateLimiter(
        "redis://unused", client_factory=lambda: redis
    )
    asyncio.run(
        limiter.consume(
            scope="checkout_failed", subject="user-1", limit=2, window_seconds=600
        )
    )

    status = asyncio.run(
        limiter.status(
            scope="checkout_failed", subject="user-1", limit=2, window_seconds=600
        )
    )

    assert status.allowed is True
    assert status.remaining == 1
    assert sum(redis.counts.values()) == 1

    asyncio.run(
        limiter.consume(
            scope="checkout_failed", subject="user-1", limit=2, window_seconds=600
        )
    )
    exhausted = asyncio.run(
        limiter.status(
            scope="checkout_failed", subject="user-1", limit=2, window_seconds=600
        )
    )
    assert exhausted.allowed is False


def test_redis_failure_is_fail_closed_for_protected_operations() -> None:
    redis = FakeRedis()
    redis.fail = True
    limiter = RedisFixedWindowRateLimiter(
        "redis://unused", client_factory=lambda: redis
    )

    with pytest.raises(RateLimitStorageError, match="unavailable"):
        asyncio.run(
            limiter.consume(
                scope="start_job", subject="user-1", limit=10, window_seconds=60
            )
        )

    assert redis.closed is True
