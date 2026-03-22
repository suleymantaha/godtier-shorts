from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.api.server as server_module
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
    monkeypatch.delenv("SOCIAL_OAUTH_CALLBACK_URL", raising=False)
    monkeypatch.delenv("SOCIAL_OAUTH_RETURN_URL", raising=False)
    monkeypatch.delenv("SOCIAL_OAUTH_STATE_TTL_SECONDS", raising=False)
    monkeypatch.delenv("SOCIAL_SCHEDULER_POLL_SECONDS", raising=False)
    monkeypatch.delenv("SOCIAL_SCHEDULER_CONCURRENCY", raising=False)
    monkeypatch.delenv("MAX_ACTIVE_JOBS_PER_SUBJECT", raising=False)
    monkeypatch.delenv("MAX_PENDING_JOBS_PER_SUBJECT", raising=False)
    monkeypatch.delenv("YTDLP_DOWNLOAD_IDLE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("YTDLP_DOWNLOAD_TOTAL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("YTDLP_PROGRESS_MIN_EMIT_INTERVAL_MS", raising=False)
    monkeypatch.delenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", raising=False)
    monkeypatch.delenv("REQUIRE_CUDA_FOR_APP", raising=False)
    monkeypatch.delenv("REQUIRE_NVENC_FOR_APP", raising=False)
    monkeypatch.delenv("LOG_ACCELERATOR_STATUS_ON_STARTUP", raising=False)

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


def test_validate_runtime_configuration_rejects_invalid_social_oauth_callback_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_OAUTH_CALLBACK_URL", "postiz/callback")

    with pytest.raises(RuntimeError, match="SOCIAL_OAUTH_CALLBACK_URL"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_social_oauth_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_OAUTH_STATE_TTL_SECONDS", "0")

    with pytest.raises(RuntimeError, match="SOCIAL_OAUTH_STATE_TTL_SECONDS"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_scheduler_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_SCHEDULER_CONCURRENCY", "0")

    with pytest.raises(RuntimeError, match="SOCIAL_SCHEDULER_CONCURRENCY"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_download_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YTDLP_DOWNLOAD_IDLE_TIMEOUT_SECONDS", "0")

    with pytest.raises(RuntimeError, match="YTDLP_DOWNLOAD_IDLE_TIMEOUT_SECONDS"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_gpu_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_CUDA_FOR_APP", "maybe")

    with pytest.raises(RuntimeError, match="REQUIRE_CUDA_FOR_APP"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_postiz_fallback_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", "maybe")

    with pytest.raises(RuntimeError, match="ALLOW_ENV_POSTIZ_API_KEY_FALLBACK"):
        validate_runtime_configuration()


def test_validate_runtime_configuration_rejects_invalid_social_connection_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "automatic")

    with pytest.raises(RuntimeError, match="SOCIAL_CONNECTION_MODE"):
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


def test_create_app_startup_requires_accelerator_support_when_validation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:admin")
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setattr(server_module, "validate_accelerator_support_configuration", lambda: (_ for _ in ()).throw(RuntimeError("gpu required")))

    with pytest.raises(RuntimeError, match="gpu required"):
        with TestClient(create_app()):
            pass


def test_create_app_startup_rejects_env_postiz_fallback_without_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:admin")
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.delenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="ALLOW_ENV_POSTIZ_API_KEY_FALLBACK"):
        with TestClient(create_app()):
            pass
