"""Runtime configuration validation helpers."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from backend.core.usage_metering import gpu_hourly_cost_from_env


APP_ENV_CHOICES = {"development", "test", "production"}
WORKER_MODE_CHOICES = {"local", "api", "gpu"}
PRODUCTION_API_REQUIRED_ENV = frozenset(
    {
        "CLERK_AUDIENCE",
        "CLERK_ISSUER_URL",
        "DATABASE_URL",
        "FRONTEND_URL",
        "IYZICO_API_BASE_URL",
        "IYZICO_API_KEY",
        "IYZICO_CALLBACK_URL",
        "IYZICO_MERCHANT_ID",
        "IYZICO_PLAN_REFERENCES_JSON",
        "IYZICO_SECRET_KEY",
        "R2_ACCESS_KEY_ID",
        "R2_BUCKET_NAME",
        "R2_ENDPOINT_URL",
        "R2_SECRET_ACCESS_KEY",
        "REDIS_URL",
        "SOCIAL_ENCRYPTION_SECRET",
        "TURNSTILE_SECRET_KEY",
        "TURNSTILE_SITE_KEY",
    }
)
PRODUCTION_GPU_REQUIRED_ENV = frozenset(
    {
        "DATABASE_URL",
        "GPU_HOURLY_COST_USD",
        "R2_ACCESS_KEY_ID",
        "R2_BUCKET_NAME",
        "R2_ENDPOINT_URL",
        "R2_SECRET_ACCESS_KEY",
        "REDIS_URL",
    }
)


def validate_runtime_configuration() -> None:
    """Fail fast on malformed runtime configuration values."""
    app_env = _validate_choice("APP_ENV", "development", APP_ENV_CHOICES)
    worker_mode = _validate_choice("WORKER_MODE", "local", WORKER_MODE_CHOICES)
    _validate_optional_port("API_PORT")
    upload_limit = _validate_optional_positive_int("UPLOAD_MAX_FILE_SIZE")
    request_limit = _validate_optional_positive_int("REQUEST_BODY_HARD_LIMIT_BYTES")
    _validate_optional_positive_int("SOCIAL_SCHEDULER_POLL_SECONDS")
    _validate_optional_positive_int("SOCIAL_SCHEDULER_CONCURRENCY")
    _validate_optional_positive_int("MAX_ACTIVE_JOBS_PER_SUBJECT")
    _validate_optional_positive_int("MAX_PENDING_JOBS_PER_SUBJECT")
    _validate_optional_positive_int("YTDLP_DOWNLOAD_IDLE_TIMEOUT_SECONDS")
    _validate_optional_positive_int("YTDLP_DOWNLOAD_TOTAL_TIMEOUT_SECONDS")
    _validate_optional_positive_int("YTDLP_PROGRESS_MIN_EMIT_INTERVAL_MS")
    _validate_optional_positive_int("BILLING_CHECKOUT_COOLDOWN_SECONDS")
    _validate_optional_positive_int("BILLING_CHECKOUT_REQUEST_LIMIT")
    _validate_optional_positive_int("BILLING_CHECKOUT_REQUEST_WINDOW_SECONDS")
    _validate_optional_positive_int("BILLING_FAILED_CHECKOUT_LIMIT")
    _validate_optional_positive_int("BILLING_FAILED_CHECKOUT_WINDOW_SECONDS")
    _validate_optional_positive_int("BILLING_PAST_DUE_GRACE_DAYS")
    _validate_optional_positive_int("PREVIEW_MAX_SOURCE_SECONDS")
    _validate_optional_positive_int("PREVIEW_MAX_TRANSCRIPTION_SECONDS")
    _validate_optional_positive_int("PREVIEW_METADATA_TIMEOUT_SECONDS")
    _validate_optional_positive_int("PREVIEW_REQUEST_WINDOW_SECONDS")
    _validate_optional_positive_int("PREVIEW_REQUEST_LIMIT")
    _validate_optional_positive_int("PREVIEW_TRANSCRIPTION_TIMEOUT_SECONDS")
    _validate_optional_positive_int("TURNSTILE_TIMEOUT_SECONDS")
    _validate_optional_positive_int("JOB_START_REQUEST_LIMIT")
    _validate_optional_positive_int("JOB_START_REQUEST_WINDOW_SECONDS")
    _validate_optional_choice("SOCIAL_CONNECTION_MODE", {"managed", "manual_api_key"})
    _validate_optional_bool("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK")
    _validate_optional_bool("REQUIRE_CUDA_FOR_APP")
    _validate_optional_bool("REQUIRE_NVENC_FOR_APP")
    _validate_optional_bool("LOG_ACCELERATOR_STATUS_ON_STARTUP")
    _validate_optional_bool("PREVIEW_LIMITED_TRANSCRIPTION_ENABLED")
    gpu_hourly_cost_from_env()

    preview_transcription_enabled = os.getenv(
        "PREVIEW_LIMITED_TRANSCRIPTION_ENABLED", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if preview_transcription_enabled:
        endpoint = os.getenv("PREVIEW_TRANSCRIPTION_ENDPOINT_URL", "").strip()
        if not endpoint:
            raise RuntimeError("PREVIEW_TRANSCRIPTION_ENDPOINT_URL gerekli")
        if not os.getenv("PREVIEW_TRANSCRIPTION_API_KEY", "").strip():
            raise RuntimeError("PREVIEW_TRANSCRIPTION_API_KEY gerekli")
        _validate_https_url("PREVIEW_TRANSCRIPTION_ENDPOINT_URL", endpoint)

    if upload_limit is not None and request_limit is not None and request_limit < upload_limit:
        raise RuntimeError(
            "REQUEST_BODY_HARD_LIMIT_BYTES, UPLOAD_MAX_FILE_SIZE degerinden kucuk olamaz"
        )

    _validate_optional_http_url("FRONTEND_URL")
    _validate_optional_http_url("PUBLIC_APP_URL")
    _validate_optional_http_url("POSTIZ_API_BASE_URL")
    _validate_optional_http_url("SOCIAL_OAUTH_CALLBACK_URL")
    _validate_optional_http_url("SOCIAL_OAUTH_RETURN_URL")
    _validate_optional_positive_int("SOCIAL_OAUTH_STATE_TTL_SECONDS")
    _validate_optional_url_list("CORS_ORIGINS")

    if app_env == "production" and worker_mode == "api":
        _validate_production_api_configuration()
    if app_env == "production" and worker_mode == "gpu":
        _validate_production_gpu_configuration()


def _validate_choice(name: str, default: str, choices: set[str]) -> str:
    value = os.getenv(name, default).strip().lower() or default
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise RuntimeError(f"{name} su degerlerden biri olmali: {allowed}")
    return value


def _validate_production_api_configuration() -> None:
    missing = sorted(
        name for name in PRODUCTION_API_REQUIRED_ENV if not os.getenv(name, "").strip()
    )
    if missing:
        raise RuntimeError(
            "Production API configuration eksik: " + ", ".join(missing)
        )

    _validate_url_schemes(
        "DATABASE_URL",
        os.environ["DATABASE_URL"],
        {"postgresql", "postgresql+asyncpg"},
    )
    _validate_url_schemes("REDIS_URL", os.environ["REDIS_URL"], {"redis", "rediss"})
    for name in (
        "R2_ENDPOINT_URL",
        "IYZICO_API_BASE_URL",
        "IYZICO_CALLBACK_URL",
        "CLERK_ISSUER_URL",
        "FRONTEND_URL",
    ):
        _validate_https_url(name, os.environ[name])
    _validate_iyzico_plan_references(os.environ["IYZICO_PLAN_REFERENCES_JSON"])
    _validate_production_cors_configuration()
    if urlparse(os.environ["IYZICO_API_BASE_URL"]).hostname != "api.iyzipay.com":
        raise RuntimeError("IYZICO_API_BASE_URL production ortaminda api.iyzipay.com olmali")


def _validate_production_cors_configuration() -> None:
    frontend_origin = os.environ["FRONTEND_URL"].strip().rstrip("/")
    raw = os.getenv("CORS_ORIGINS", "").strip()
    origins = (
        [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
        if raw
        else [frontend_origin]
    )

    if frontend_origin not in origins:
        raise RuntimeError("CORS_ORIGINS production ortaminda FRONTEND_URL originini icermeli")

    for origin in origins:
        parsed = urlparse(origin)
        if (
            origin == "*"
            or parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "CORS_ORIGINS production ortaminda yalniz tam HTTPS originleri icermeli"
            )


def _validate_production_gpu_configuration() -> None:
    missing = sorted(
        name for name in PRODUCTION_GPU_REQUIRED_ENV if not os.getenv(name, "").strip()
    )
    if missing:
        raise RuntimeError(
            "Production GPU configuration eksik: " + ", ".join(missing)
        )
    for name in ("REQUIRE_CUDA_FOR_APP", "REQUIRE_NVENC_FOR_APP"):
        if os.getenv(name, "").strip().lower() not in {"1", "true", "yes", "on"}:
            raise RuntimeError(f"{name} production GPU worker icin true olmali")
    _validate_url_schemes(
        "DATABASE_URL",
        os.environ["DATABASE_URL"],
        {"postgresql", "postgresql+asyncpg"},
    )
    _validate_url_schemes("REDIS_URL", os.environ["REDIS_URL"], {"redis", "rediss"})
    _validate_https_url("R2_ENDPOINT_URL", os.environ["R2_ENDPOINT_URL"])


def _validate_iyzico_plan_references(raw: str) -> None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("IYZICO_PLAN_REFERENCES_JSON gecerli JSON olmali") from exc
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError("IYZICO_PLAN_REFERENCES_JSON en az bir plan icermeli")
    required = {"product_reference_code", "monthly", "yearly"}
    pricing_references: list[str] = []
    for plan_code, references in payload.items():
        if (
            not isinstance(plan_code, str)
            or not plan_code.strip()
            or not isinstance(references, dict)
            or any(not str(references.get(name) or "").strip() for name in required)
        ):
            raise RuntimeError("IYZICO_PLAN_REFERENCES_JSON plan mapping eksik")
        pricing_references.extend(str(references[name]).strip() for name in ("monthly", "yearly"))
    if len(pricing_references) != len(set(pricing_references)):
        raise RuntimeError("IYZICO_PLAN_REFERENCES_JSON pricing referanslari benzersiz olmali")


def _validate_url_schemes(name: str, value: str, schemes: set[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in schemes or not parsed.netloc:
        allowed = ", ".join(sorted(schemes))
        raise RuntimeError(f"{name} su URL semalarindan birini kullanmali: {allowed}")


def _validate_https_url(name: str, value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(f"{name} mutlak bir https URL olmali")
    if parsed.query or parsed.fragment:
        raise RuntimeError(f"{name} query veya fragment icermemeli")


def _validate_optional_port(name: str) -> int | None:
    value = _validate_optional_positive_int(name)
    if value is None:
        return None
    if value > 65535:
        raise RuntimeError(f"{name} 1-65535 araliginda olmali")
    return value


def _validate_optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} pozitif bir tam sayi olmali") from exc
    if value <= 0:
        raise RuntimeError(f"{name} pozitif bir tam sayi olmali")
    return value


def _validate_optional_bool(name: str) -> None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return
    if raw.lower() not in {"0", "1", "true", "false", "yes", "no", "on", "off"}:
        raise RuntimeError(f"{name} boolean bir deger olmali")


def _validate_optional_choice(name: str, choices: set[str]) -> None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return
    if raw not in choices:
        allowed = ", ".join(sorted(choices))
        raise RuntimeError(f"{name} su degerlerden biri olmali: {allowed}")


def _validate_optional_url_list(name: str) -> None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if not values:
        raise RuntimeError(f"{name} en az bir gecerli origin icermeli")
    for value in values:
        _validate_http_url(name, value)


def _validate_optional_http_url(name: str) -> None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return
    _validate_http_url(name, raw)


def _validate_http_url(name: str, value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{name} mutlak bir http(s) URL olmali")
    if parsed.query or parsed.fragment:
        raise RuntimeError(f"{name} query veya fragment icermemeli")
