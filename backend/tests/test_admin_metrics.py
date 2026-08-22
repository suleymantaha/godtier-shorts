from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import admin_metrics
from backend.api.routes.admin_metrics import EconomicsRow, aggregate_job_economics
from backend.db.models import JobStatus


def test_job_economics_kpis_are_derived_from_persisted_usage() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        EconomicsRow(JobStatus.COMPLETED, now, now + timedelta(seconds=10), 3600, 120, 2, Decimal("1.20")),
        EconomicsRow(JobStatus.REVIEW_REQUIRED, now, now + timedelta(seconds=30), 1800, 240, 1, Decimal("0.60")),
        EconomicsRow(JobStatus.ERROR, now, None, 0, 0, 0, Decimal("0")),
    ]

    result = aggregate_job_economics(rows)

    assert result.total_jobs == 3
    assert result.success_rate == 2 / 3
    assert result.review_required_rate == 1 / 3
    assert result.cost_per_source_hour_usd == Decimal("1.200000")
    assert result.cost_per_short_usd == Decimal("0.600000")
    assert result.average_queue_wait_seconds == 20
    assert result.average_render_seconds == 180


def test_job_economics_endpoint_requires_admin_auth(monkeypatch) -> None:
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    app = FastAPI()
    app.include_router(admin_metrics.router)

    response = TestClient(app).get("/api/admin/job-economics")

    assert response.status_code == 401
