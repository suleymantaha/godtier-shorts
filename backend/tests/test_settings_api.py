from __future__ import annotations

import hashlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import settings as settings_routes


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(settings_routes.router)
    return app


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("API_BEARER_TOKENS", "devtoken:admin")
    return {"Authorization": "Bearer devtoken"}


def test_get_ai_status(auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-123456")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-xxxxxxxxxxxxxxxx")

    client = TestClient(_build_app())
    response = client.get("/api/settings/ai-status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["effective_default_engine"] == "nvidia"
    assert data["engines"]["nvidia"]["configured"] is True
    assert data["engines"]["cloud"]["configured"] is False
    assert data["engines"]["cloud"]["fallback_to_nvidia"] is True


def test_test_ai_engine(auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key-123456")

    client = TestClient(_build_app())
    response = client.post(
        "/api/settings/test-ai",
        headers=auth_headers,
        json={"engine": "nvidia"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "engine" in data
    assert data["engine"] == "nvidia"
