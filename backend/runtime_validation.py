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

    if upload_limit is not None and request_limit is not None and request_limit < upload_limit:
        raise RuntimeError(
            "REQUEST_BODY_HARD_LIMIT_BYTES, UPLOAD_MAX_FILE_SIZE degerinden kucuk olamaz"
        )

    _validate_optional_http_url("FRONTEND_URL")
    _validate_optional_http_url("PUBLIC_APP_URL")
    _validate_optional_http_url("POSTIZ_API_BASE_URL")
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
