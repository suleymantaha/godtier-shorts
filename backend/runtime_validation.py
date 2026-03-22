"""Runtime configuration validation helpers."""

from __future__ import annotations

import os
from urllib.parse import urlparse


def validate_runtime_configuration() -> None:
    """Fail fast on malformed runtime configuration values."""
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
    _validate_optional_choice("SOCIAL_CONNECTION_MODE", {"managed", "manual_api_key"})
    _validate_optional_bool("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK")
    _validate_optional_bool("REQUIRE_CUDA_FOR_APP")
    _validate_optional_bool("REQUIRE_NVENC_FOR_APP")
    _validate_optional_bool("LOG_ACCELERATOR_STATUS_ON_STARTUP")

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
