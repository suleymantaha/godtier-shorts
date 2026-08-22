from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from loguru import logger
from sqlalchemy import func, select

from backend.config import TEMP_DIR
from backend.db.models import JobUsageMetric
from backend.db.session import get_session_factory
from backend.observability.reporting import capture_exception, capture_message


GPU_WORKER_HEARTBEAT_KEY = "godtier:gpu-worker:heartbeat"
ARQ_QUEUE_KEY = "arq:queue"


@dataclass(frozen=True, slots=True)
class OperationalSnapshot:
    queue_depth: int
    gpu_worker_alive: bool
    gpu_daily_cost_usd: Decimal
    disk_free_percent: float
    temp_usage_bytes: int


@dataclass(frozen=True, slots=True)
class OperationalAlert:
    code: str
    value: str
    threshold: str


def evaluate_alerts(
    snapshot: OperationalSnapshot,
    *,
    queue_depth_threshold: int,
    gpu_daily_budget_usd: Decimal,
    disk_free_threshold_percent: float,
    temp_usage_threshold_bytes: int,
) -> list[OperationalAlert]:
    alerts: list[OperationalAlert] = []
    if snapshot.queue_depth > queue_depth_threshold:
        alerts.append(OperationalAlert("queue_depth_high", str(snapshot.queue_depth), str(queue_depth_threshold)))
    if not snapshot.gpu_worker_alive:
        alerts.append(OperationalAlert("gpu_worker_heartbeat_missing", "0", "1"))
    if snapshot.gpu_daily_cost_usd > gpu_daily_budget_usd:
        alerts.append(OperationalAlert("gpu_daily_budget_exceeded", str(snapshot.gpu_daily_cost_usd), str(gpu_daily_budget_usd)))
    if snapshot.disk_free_percent < disk_free_threshold_percent:
        alerts.append(OperationalAlert("disk_free_low", str(snapshot.disk_free_percent), str(disk_free_threshold_percent)))
    if snapshot.temp_usage_bytes > temp_usage_threshold_bytes:
        alerts.append(OperationalAlert("temp_usage_high", str(snapshot.temp_usage_bytes), str(temp_usage_threshold_bytes)))
    return alerts


def emit_alert(code: str, **context: object) -> None:
    safe_context = {key: str(value) for key, value in context.items()}
    logger.bind(event="operational_alert", alert_code=code, **safe_context).error(
        "operational_alert code={}", code
    )
    capture_message(f"operational_alert:{code}", level="error")


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


async def collect_operational_snapshot() -> OperationalSnapshot:
    from redis.asyncio import Redis

    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        queue_depth = int(await redis.zcard(ARQ_QUEUE_KEY))
        gpu_worker_alive = bool(await redis.exists(GPU_WORKER_HEARTBEAT_KEY))
    finally:
        await redis.aclose()

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    factory = get_session_factory()
    async with factory() as session:
        cost = await session.scalar(
            select(func.coalesce(func.sum(JobUsageMetric.estimated_internal_cost_usd), 0)).where(
                JobUsageMetric.created_at >= today
            )
        )
    usage = shutil.disk_usage(TEMP_DIR)
    disk_free_percent = usage.free / usage.total * 100 if usage.total else 0
    temp_usage_bytes = await asyncio.to_thread(_directory_size, TEMP_DIR)
    return OperationalSnapshot(
        queue_depth=queue_depth,
        gpu_worker_alive=gpu_worker_alive,
        gpu_daily_cost_usd=Decimal(str(cost or 0)),
        disk_free_percent=disk_free_percent,
        temp_usage_bytes=temp_usage_bytes,
    )


async def run_operational_monitor(stop: asyncio.Event) -> None:
    poll_seconds = int(os.getenv("OBSERVABILITY_POLL_SECONDS", "60"))
    thresholds = {
        "queue_depth_threshold": int(os.getenv("QUEUE_DEPTH_ALERT_THRESHOLD", "100")),
        "gpu_daily_budget_usd": Decimal(os.getenv("GPU_DAILY_BUDGET_USD", "50")),
        "disk_free_threshold_percent": float(os.getenv("DISK_FREE_ALERT_PERCENT", "10")),
        "temp_usage_threshold_bytes": int(os.getenv("TEMP_USAGE_ALERT_BYTES", str(20 * 1024**3))),
    }
    active_alerts: set[str] = set()
    while not stop.is_set():
        try:
            snapshot = await collect_operational_snapshot()
            alerts = evaluate_alerts(snapshot, **thresholds)
            current_alerts = {alert.code for alert in alerts}
            for alert in alerts:
                if alert.code in active_alerts:
                    continue
                emit_alert(alert.code, value=alert.value, threshold=alert.threshold)
            for code in active_alerts - current_alerts:
                logger.bind(event="operational_alert_recovered").info(
                    "operational alert recovered code={}", code
                )
            active_alerts = current_alerts
        except Exception as exc:
            logger.bind(event="observability_monitor_failed").error("observability monitor failed")
            capture_exception(exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
        except TimeoutError:
            continue
