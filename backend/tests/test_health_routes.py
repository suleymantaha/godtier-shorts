from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.api.server as server_module
from backend.api.server import create_app
from backend.services.social.scheduler import SocialPublishScheduler
from backend.services.video_processor import VideoProcessor


@pytest.fixture(autouse=True)
def local_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WORKER_MODE", "local")
    monkeypatch.setenv(
        "API_BEARER_TOKENS",
        "test-static-token-value-1234567890:admin",
    )
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.delenv("POSTIZ_API_KEY", raising=False)
    scheduler = SocialPublishScheduler()
    monkeypatch.setattr(server_module, "get_social_scheduler", lambda: scheduler)


def test_health_routes_expose_live_and_ready_state() -> None:
    app = create_app()

    assert getattr(app.state, "ready", False) is False
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert client.get("/health/ready").status_code == 200

    assert app.state.ready is False


def test_api_startup_does_not_initialize_gpu_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_initialized(*args, **kwargs):
        raise AssertionError("API startup GPU processor olusturmamali")

    monkeypatch.setattr(VideoProcessor, "__init__", fail_if_initialized)

    with TestClient(create_app()) as client:
        assert client.get("/health/ready").status_code == 200


def test_ready_returns_503_when_a_production_dependency_is_unavailable() -> None:
    class FailedReadiness:
        async def check(self):
            from backend.observability import ReadinessReport

            return ReadinessReport(
                status="not_ready",
                dependencies={"postgres": "ok", "redis": "failed", "r2": "ok"},
            )

    app = create_app()
    app.state.ready = True
    app.state.readiness_checker = FailedReadiness()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"postgres": "ok", "redis": "failed", "r2": "ok"},
    }
