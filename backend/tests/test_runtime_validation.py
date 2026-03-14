from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app
from backend.runtime_validation import validate_runtime_configuration


def test_validate_runtime_configuration_accepts_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.delenv("UPLOAD_MAX_FILE_SIZE", raising=False)
    monkeypatch.delenv("REQUEST_BODY_HARD_LIMIT_BYTES", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    monkeypatch.delenv("POSTIZ_API_BASE_URL", raising=False)
    monkeypatch.delenv("SOCIAL_SCHEDULER_POLL_SECONDS", raising=False)
    monkeypatch.delenv("SOCIAL_SCHEDULER_CONCURRENCY", raising=False)

    validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_PORT", "70000")

    with pytest.raises(RuntimeError, match="API_PORT"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_frontend_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_URL", "localhost:5173")

    with pytest.raises(RuntimeError, match="FRONTEND_URL"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_cors_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,not-a-url")

    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_smaller_request_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPLOAD_MAX_FILE_SIZE", "1024")
    monkeypatch.setenv("REQUEST_BODY_HARD_LIMIT_BYTES", "512")

    with pytest.raises(RuntimeError, match="REQUEST_BODY_HARD_LIMIT_BYTES"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_postiz_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTIZ_API_BASE_URL", "ftp://postiz.example.com")

    with pytest.raises(RuntimeError, match="POSTIZ_API_BASE_URL"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_scheduler_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_SCHEDULER_CONCURRENCY", "0")

    with pytest.raises(RuntimeError, match="SOCIAL_SCHEDULER_CONCURRENCY"):
        validate_runtime_configuration()


def test_create_app_startup_requires_valid_runtime_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:admin")
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("FRONTEND_URL", "localhost:5173")

    with pytest.raises(RuntimeError, match="FRONTEND_URL"):
        with TestClient(create_app()):
            pass
