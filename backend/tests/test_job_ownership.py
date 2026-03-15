from __future__ import annotations

import hashlib
import threading

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
    monkeypatch.setenv("API_BEARER_TOKENS", "token-a:viewer,operator;token-b:viewer,operator")
    manager.jobs.clear()
    return {
        "a": {"Authorization": "Bearer token-a"},
        "b": {"Authorization": "Bearer token-b"},
    }


def test_jobs_endpoint_lists_only_callers_subject_jobs(auth_headers: dict[str, dict[str, str]]) -> None:
    manager.jobs["job-a"] = {
        "job_id": "job-a",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "created_at": 1.0,
        "subject": _static_subject("token-a"),
    }
    manager.jobs["job-b"] = {
        "job_id": "job-b",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "created_at": 2.0,
        "subject": _static_subject("token-b"),
    }

    client = TestClient(_build_app())
    response = client.get("/api/jobs", headers=auth_headers["a"])

    assert response.status_code == 200
    assert [job["job_id"] for job in response.json()["jobs"]] == ["job-a"]


def test_foreign_job_cancel_returns_not_found(auth_headers: dict[str, dict[str, str]]) -> None:
    manager.jobs["job-b"] = {
        "job_id": "job-b",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "created_at": 2.0,
        "subject": _static_subject("token-b"),
        "cancel_event": threading.Event(),
    }

    client = TestClient(_build_app())
    response = client.post("/api/cancel-job/job-b", headers=auth_headers["a"])

    assert response.status_code == 404


def test_owner_can_cancel_own_job(auth_headers: dict[str, dict[str, str]]) -> None:
    manager.jobs["job-a"] = {
        "job_id": "job-a",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "created_at": 1.0,
        "subject": _static_subject("token-a"),
        "cancel_event": threading.Event(),
    }

    client = TestClient(_build_app())
    response = client.post("/api/cancel-job/job-a", headers=auth_headers["a"])

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert manager.jobs["job-a"]["status"] == "cancelled"
