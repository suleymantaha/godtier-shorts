from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.api.server as server_module
import backend.config as config_module
from backend.api.server import create_app
from backend.runtime_validation import validate_runtime_configuration


PRODUCTION_API_ENV = {
    "APP_ENV": "production",
    "WORKER_MODE": "api",
    "DATABASE_URL": "postgresql+asyncpg://godtier:test-password@postgres:5432/godtier",
    "REDIS_URL": "redis://redis:6379/0",
    "R2_ENDPOINT_URL": "https://test-account.r2.cloudflarestorage.com",
    "R2_BUCKET_NAME": "godtier-private",
    "R2_ACCESS_KEY_ID": "test-r2-access-key",
    "R2_SECRET_ACCESS_KEY": "test-r2-secret-key",
    "IYZICO_API_BASE_URL": "https://api.iyzipay.com",
    "IYZICO_API_KEY": "test-iyzico-api-key",
    "IYZICO_CALLBACK_URL": "https://api.godtier.example/api/billing/callback",
    "IYZICO_MERCHANT_ID": "3404590",
    "IYZICO_PLAN_REFERENCES_JSON": '{"creator":{"product_reference_code":"product",'
    '"monthly":"monthly","yearly":"yearly"}}',
    "IYZICO_SECRET_KEY": "test-iyzico-secret-key",
    "TURNSTILE_SITE_KEY": "test-turnstile-site-key",
    "TURNSTILE_SECRET_KEY": "test-turnstile-secret-key",
    "CLERK_ISSUER_URL": "https://test.clerk.accounts.dev",
    "CLERK_AUDIENCE": "godtier-api",
    "FRONTEND_URL": "https://app.godtier.example",
    "SOCIAL_ENCRYPTION_SECRET": "test-social-encryption-secret",
}


def _set_production_api_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in PRODUCTION_API_ENV.items():
        monkeypatch.setenv(name, value)


def test_validate_runtime_configuration_accepts_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("WORKER_MODE", raising=False)
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
    monkeypatch.delenv("GPU_HOURLY_COST_USD", raising=False)

    validate_runtime_configuration()


def test_config_defaults_preserve_local_development_runtime() -> None:
    assert getattr(config_module, "APP_ENV", None) == "development"
    assert getattr(config_module, "WORKER_MODE", None) == "local"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_ENV", "prod"),
        ("WORKER_MODE", "worker"),
    ],
)
def test_validate_runtime_configuration_rejects_invalid_runtime_mode(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=name):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    "missing_name",
    sorted(PRODUCTION_API_ENV.keys() - {"APP_ENV", "WORKER_MODE"}),
)
def test_production_api_requires_complete_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    _set_production_api_env(monkeypatch)
    monkeypatch.delenv(missing_name)

    with pytest.raises(RuntimeError, match=missing_name):
        validate_runtime_configuration()


def test_production_api_accepts_complete_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_api_env(monkeypatch)

    validate_runtime_configuration()


def test_production_gpu_requires_storage_queue_database_and_accelerator_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WORKER_MODE", "gpu")
    monkeypatch.setenv("DATABASE_URL", PRODUCTION_API_ENV["DATABASE_URL"])
    monkeypatch.setenv("REDIS_URL", PRODUCTION_API_ENV["REDIS_URL"])
    monkeypatch.setenv("R2_ENDPOINT_URL", PRODUCTION_API_ENV["R2_ENDPOINT_URL"])
    monkeypatch.setenv("R2_BUCKET_NAME", PRODUCTION_API_ENV["R2_BUCKET_NAME"])
    monkeypatch.setenv("R2_ACCESS_KEY_ID", PRODUCTION_API_ENV["R2_ACCESS_KEY_ID"])
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", PRODUCTION_API_ENV["R2_SECRET_ACCESS_KEY"])
    monkeypatch.setenv("REQUIRE_CUDA_FOR_APP", "1")
    monkeypatch.setenv("GPU_HOURLY_COST_USD", "0.90")
    monkeypatch.delenv("REQUIRE_NVENC_FOR_APP", raising=False)

    with pytest.raises(RuntimeError, match="REQUIRE_NVENC_FOR_APP"):
        validate_runtime_configuration()


def test_production_gpu_accepts_complete_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WORKER_MODE", "gpu")
    for name in (
        "DATABASE_URL",
        "REDIS_URL",
        "R2_ENDPOINT_URL",
        "R2_BUCKET_NAME",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    ):
        monkeypatch.setenv(name, PRODUCTION_API_ENV[name])
    monkeypatch.setenv("REQUIRE_CUDA_FOR_APP", "1")
    monkeypatch.setenv("REQUIRE_NVENC_FOR_APP", "1")
    monkeypatch.setenv("GPU_HOURLY_COST_USD", "0.90")

    validate_runtime_configuration()


def test_runtime_rejects_invalid_gpu_hourly_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GPU_HOURLY_COST_USD", "not-a-price")

    with pytest.raises(RuntimeError, match="GPU_HOURLY_COST_USD"):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("READINESS_TIMEOUT_SECONDS", "0"),
        ("OBSERVABILITY_POLL_SECONDS", "0"),
        ("QUEUE_DEPTH_ALERT_THRESHOLD", "0"),
        ("GPU_DAILY_BUDGET_USD", "0"),
        ("DISK_FREE_ALERT_PERCENT", "101"),
        ("TEMP_USAGE_ALERT_BYTES", "0"),
        ("SENTRY_TRACES_SAMPLE_RATE", "1.1"),
    ],
)
def test_runtime_rejects_invalid_observability_thresholds(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=name):
        validate_runtime_configuration()


def test_runtime_requires_worker_heartbeat_ttl_to_exceed_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GPU_WORKER_HEARTBEAT_SECONDS", "30")
    monkeypatch.setenv("GPU_WORKER_HEARTBEAT_TTL_SECONDS", "30")

    with pytest.raises(RuntimeError, match="GPU_WORKER_HEARTBEAT_TTL_SECONDS"):
        validate_runtime_configuration()


def test_runtime_rejects_insecure_sentry_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "http://public@example.ingest.sentry.io/1")

    with pytest.raises(RuntimeError, match="SENTRY_DSN"):
        validate_runtime_configuration()


def test_production_api_rejects_malformed_iyzico_plan_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_api_env(monkeypatch)
    monkeypatch.setenv("IYZICO_PLAN_REFERENCES_JSON", '{"creator":{"monthly":"only-one"}}')

    with pytest.raises(RuntimeError, match="IYZICO_PLAN_REFERENCES_JSON"):
        validate_runtime_configuration()


def test_production_api_rejects_sandbox_iyzico_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_api_env(monkeypatch)
    monkeypatch.setenv("IYZICO_API_BASE_URL", "https://sandbox-api.iyzipay.com")
    with pytest.raises(RuntimeError, match="api.iyzipay.com"):
        validate_runtime_configuration()


def test_runtime_rejects_invalid_checkout_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BILLING_CHECKOUT_COOLDOWN_SECONDS", "0")
    with pytest.raises(RuntimeError, match="BILLING_CHECKOUT_COOLDOWN_SECONDS"):
        validate_runtime_configuration()


def test_runtime_rejects_invalid_preview_request_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREVIEW_REQUEST_WINDOW_SECONDS", "0")
    with pytest.raises(RuntimeError, match="PREVIEW_REQUEST_WINDOW_SECONDS"):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    "name",
    [
        "PREVIEW_REQUEST_LIMIT",
        "BILLING_CHECKOUT_REQUEST_LIMIT",
        "BILLING_CHECKOUT_REQUEST_WINDOW_SECONDS",
        "BILLING_FAILED_CHECKOUT_LIMIT",
        "BILLING_FAILED_CHECKOUT_WINDOW_SECONDS",
        "JOB_START_REQUEST_LIMIT",
        "JOB_START_REQUEST_WINDOW_SECONDS",
    ],
)
def test_runtime_rejects_non_positive_distributed_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    monkeypatch.setenv(name, "0")

    with pytest.raises(RuntimeError, match=name):
        validate_runtime_configuration()


def test_runtime_requires_transcription_provider_when_preview_fallback_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREVIEW_LIMITED_TRANSCRIPTION_ENABLED", "true")
    monkeypatch.delenv("PREVIEW_TRANSCRIPTION_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("PREVIEW_TRANSCRIPTION_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PREVIEW_TRANSCRIPTION_ENDPOINT_URL"):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DATABASE_URL", "sqlite:///godtier.db"),
        ("REDIS_URL", "http://redis:6379/0"),
        ("R2_ENDPOINT_URL", "http://r2.example.com"),
        ("IYZICO_API_BASE_URL", "http://api.iyzipay.com"),
        ("IYZICO_CALLBACK_URL", "http://api.godtier.example/api/billing/callback"),
        ("CLERK_ISSUER_URL", "http://clerk.example.com"),
        ("FRONTEND_URL", "http://app.godtier.example"),
    ],
)
def test_production_api_rejects_unsafe_service_urls(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    _set_production_api_env(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=name):
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


@pytest.mark.parametrize(
    "cors_origins",
    [
        "http://localhost:5173",
        "https://app.godtier.example/path",
        "https://other.godtier.example",
        "*",
    ],
)
def test_production_rejects_non_exact_or_insecure_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
    cors_origins: str,
) -> None:
    _set_production_api_env(monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", cors_origins)

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
