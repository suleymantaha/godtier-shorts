from __future__ import annotations

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import jobs as jobs_routes
from backend.api.websocket import manager


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(jobs_routes.router)
    return app


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    monkeypatch.setenv("API_BEARER_TOKENS", "token-a:operator;token-b:operator")
    monkeypatch.setenv("MAX_ACTIVE_JOBS_PER_SUBJECT", "1")
    monkeypatch.setenv("MAX_PENDING_JOBS_PER_SUBJECT", "3")
    manager.jobs.clear()
    return {
        "a": {"Authorization": "Bearer token-a"},
        "b": {"Authorization": "Bearer token-b"},
    }


def test_subject_job_counts_distinguish_processing_and_queued() -> None:
    isolated_manager = manager.__class__()
    isolated_manager.jobs["queued"] = {"subject": "subject-a", "status": "queued"}
    isolated_manager.jobs["processing"] = {"subject": "subject-a", "status": "processing"}
    isolated_manager.jobs["foreign"] = {"subject": "subject-b", "status": "queued"}

    assert isolated_manager.subject_job_counts("subject-a") == (1, 1)


def test_start_job_rejects_when_subject_pending_limit_is_reached(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    async def _noop_run_gpu_job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_routes, "run_gpu_job", _noop_run_gpu_job)
    subject_a = _static_subject("token-a")
    for index in range(3):
        manager.jobs[f"queued-{index}"] = {
            "job_id": f"queued-{index}",
            "status": "queued",
            "progress": 0,
            "last_message": "queued",
            "created_at": float(index),
            "subject": subject_a,
        }

    client = TestClient(_build_app())
    response = client.post(
        "/api/start-job",
        headers=auth_headers["a"],
        json={"youtube_url": "https://youtube.com/watch?v=test"},
    )

    assert response.status_code == 429
    body = response.json()
    assert body["code"] == "RATE_LIMITED"


def test_other_subject_can_enqueue_when_foreign_queue_is_full(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    async def _noop_run_gpu_job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_routes, "run_gpu_job", _noop_run_gpu_job)
    subject_a = _static_subject("token-a")
    for index in range(3):
        manager.jobs[f"queued-{index}"] = {
            "job_id": f"queued-{index}",
            "status": "queued",
            "progress": 0,
            "last_message": "queued",
            "created_at": float(index),
            "subject": subject_a,
        }

    client = TestClient(_build_app())
    response = client.post(
        "/api/start-job",
        headers=auth_headers["b"],
        json={"youtube_url": "https://youtube.com/watch?v=test"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
