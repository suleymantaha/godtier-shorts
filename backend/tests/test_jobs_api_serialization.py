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


def test_jobs_endpoint_omits_runtime_task_objects(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")
    manager.jobs.clear()
    manager.jobs["job-1"] = {
        "job_id": "job-1",
        "url": "https://example.com",
        "style": "TIKTOK",
        "status": "processing",
        "progress": 50,
        "last_message": "running",
        "created_at": 123.0,
        "task": object(),
    }

    client = TestClient(_build_app())
    response = client.get("/api/jobs", headers={"Authorization": "Bearer token123"})

    assert response.status_code == 200
    body = response.json()
    assert "jobs" in body and len(body["jobs"]) == 1
    assert body["jobs"][0]["job_id"] == "job-1"
    assert "task" not in body["jobs"][0]
