from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import production_jobs
from backend.api.security import AuthContext, authenticate_request
from backend.services.queue.job_service import SubmittedJob


class FakeGateway:
    def __init__(self) -> None: self.calls = []
    async def start(self, **kwargs):
        self.calls.append(("start", kwargs))
        return SubmittedJob(uuid4())
    async def cancel(self, **kwargs):
        self.calls.append(("cancel", kwargs))
        return "cancelled"


def _app(gateway: FakeGateway):
    app = FastAPI()
    app.include_router(production_jobs.router)
    user_id = uuid4()
    app.state.user_id = user_id
    app.dependency_overrides[authenticate_request] = lambda: AuthContext(
        subject="user", roles={"member"}, token_type="jwt",
        auth_mode="clerk_jwt", user_id=user_id,
    )
    app.dependency_overrides[production_jobs.get_job_gateway] = lambda: gateway
    return app


def test_production_start_job_uses_authenticated_user_and_idempotency_key() -> None:
    gateway = FakeGateway()
    app = _app(gateway)
    project_id = uuid4()

    response = TestClient(app).post(
        "/api/start-job",
        headers={"Idempotency-Key": "render-1"},
        json={"project_id": str(project_id), "num_clips": 3, "resolution": "1080p", "layout": "auto"},
    )

    assert response.status_code == 200
    call = gateway.calls[0][1]
    assert call["user_id"] == app.state.user_id
    assert call["idempotency_key"] == "render-1"
    assert call["project_id"] == project_id


def test_production_cancel_is_owner_scoped() -> None:
    gateway = FakeGateway()
    app = _app(gateway)
    job_id = uuid4()

    response = TestClient(app).post(
        f"/api/cancel-job/{job_id}", json={"confirmed": True, "source": "ui"}
    )

    assert response.status_code == 200
    assert gateway.calls[0][1] == {"user_id": app.state.user_id, "job_id": job_id}


def test_production_start_job_rejects_blank_idempotency_key() -> None:
    gateway = FakeGateway()
    app = _app(gateway)

    response = TestClient(app).post(
        "/api/start-job",
        headers={"Idempotency-Key": "   "},
        json={"project_id": str(uuid4()), "num_clips": 3},
    )

    assert response.status_code == 422
    assert gateway.calls == []


def test_only_explicit_block_risk_decision_denies_paid_render() -> None:
    assert production_jobs._is_blocked(None) is False
    assert production_jobs._is_blocked(
        SimpleNamespace(metadata_json={"decision": "high"})
    ) is False
    assert production_jobs._is_blocked(
        SimpleNamespace(metadata_json={"decision": "block"})
    ) is True
