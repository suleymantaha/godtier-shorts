from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

from backend.observability import (
    OperationalSnapshot,
    ReadinessChecker,
    build_structured_log,
    evaluate_alerts,
)
from backend.observability.reporting import _scrub_event
from backend.workers.gpu_worker import publish_worker_heartbeat


def test_structured_production_log_is_json_and_redacts_credentials() -> None:
    payload = json.loads(
        build_structured_log(
            {
                "time": datetime(2026, 8, 22, tzinfo=timezone.utc),
                "level": "ERROR",
                "message": "Authorization: Bearer secret-token IYZICO_SECRET_KEY=top-secret",
                "extra": {"request_id": "req-22", "component": "api"},
                "exception": "password=hunter2",
            }
        )
    )

    assert payload["level"] == "error"
    assert payload["request_id"] == "req-22"
    assert payload["component"] == "api"
    assert "secret-token" not in json.dumps(payload)
    assert "top-secret" not in json.dumps(payload)
    assert "hunter2" not in json.dumps(payload)


def test_readiness_checker_reports_each_dependency_without_leaking_error_details() -> None:
    async def healthy() -> None:
        return None

    async def failed() -> None:
        raise RuntimeError("redis://user:secret@redis:6379")

    report = asyncio.run(
        ReadinessChecker({"postgres": healthy, "redis": failed, "r2": healthy}, timeout_seconds=1).check()
    )

    assert report.status == "not_ready"
    assert report.dependencies == {"postgres": "ok", "redis": "failed", "r2": "ok"}
    assert "secret" not in json.dumps(report.dependencies)


def test_operational_thresholds_emit_stable_alert_codes() -> None:
    alerts = evaluate_alerts(
        OperationalSnapshot(
            queue_depth=101,
            gpu_worker_alive=False,
            gpu_daily_cost_usd=Decimal("51.25"),
            disk_free_percent=7.5,
            temp_usage_bytes=25_000,
        ),
        queue_depth_threshold=100,
        gpu_daily_budget_usd=Decimal("50"),
        disk_free_threshold_percent=10,
        temp_usage_threshold_bytes=20_000,
    )

    assert [alert.code for alert in alerts] == [
        "queue_depth_high",
        "gpu_worker_heartbeat_missing",
        "gpu_daily_budget_exceeded",
        "disk_free_low",
        "temp_usage_high",
    ]


def test_gpu_worker_heartbeat_has_expiry_and_contains_no_secret() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.calls = []

        async def set(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    redis = FakeRedis()
    asyncio.run(publish_worker_heartbeat(redis, worker_id="gpu-01", ttl_seconds=90))

    assert redis.calls == [(('godtier:gpu-worker:heartbeat', 'gpu-01'), {'ex': 90})]


def test_error_reporting_scrubs_nested_credential_fields() -> None:
    event = _scrub_event(
        {
            "request": {
                "headers": {"authorization": "Bearer secret"},
                "payment_api_key": "top-secret",
            },
            "message": "safe",
        }
    )

    assert event["request"]["headers"] == "[redacted]"
    assert event["request"]["payment_api_key"] == "[redacted]"
    assert event["message"] == "safe"
