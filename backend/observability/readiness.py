from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy import text

from backend.db.session import get_session_factory


Probe = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    status: str
    dependencies: dict[str, str]


class ReadinessChecker:
    def __init__(self, probes: dict[str, Probe], *, timeout_seconds: float = 3) -> None:
        self._probes = probes
        self._timeout_seconds = timeout_seconds

    async def check(self) -> ReadinessReport:
        async def run(name: str, probe: Probe) -> tuple[str, str]:
            try:
                await asyncio.wait_for(probe(), timeout=self._timeout_seconds)
            except Exception:
                return name, "failed"
            return name, "ok"

        results = await asyncio.gather(
            *(run(name, probe) for name, probe in self._probes.items())
        )
        dependencies = dict(results)
        status = "ready" if all(value == "ok" for value in dependencies.values()) else "not_ready"
        return ReadinessReport(status=status, dependencies=dependencies)


def build_production_readiness_checker() -> ReadinessChecker:
    async def postgres_probe() -> None:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))

    async def redis_probe() -> None:
        from redis.asyncio import Redis

        client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        try:
            if not await client.ping():
                raise RuntimeError("redis ping failed")
        finally:
            await client.aclose()

    async def r2_probe() -> None:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
        await asyncio.to_thread(
            client.head_bucket,
            Bucket=os.environ["R2_BUCKET_NAME"],
        )

    timeout = float(os.getenv("READINESS_TIMEOUT_SECONDS", "3"))
    return ReadinessChecker(
        {"postgres": postgres_probe, "redis": redis_probe, "r2": r2_probe},
        timeout_seconds=timeout,
    )
