from __future__ import annotations

import os
from typing import Any


_SENSITIVE_EVENT_KEYS = frozenset(
    {"authorization", "cookie", "cookies", "data", "headers", "password", "request_body", "secret", "token", "user"}
)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return normalized in _SENSITIVE_EVENT_KEYS or any(
        marker in normalized
        for marker in ("api_key", "password", "private_key", "secret", "token")
    )


def _scrub_event(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if _is_sensitive_key(key) else _scrub_event(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_event(item) for item in value]
    return value


def configure_error_reporting() -> bool:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    import sentry_sdk

    traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0"))
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("APP_ENV", "development"),
        release=os.getenv("APP_RELEASE", "").strip() or None,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=traces_sample_rate,
        before_send=lambda event, _hint: _scrub_event(event),
    )
    return True


def capture_exception(exc: Exception) -> None:
    if not os.getenv("SENTRY_DSN", "").strip():
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        return


def capture_message(message: str, *, level: str = "error") -> None:
    if not os.getenv("SENTRY_DSN", "").strip():
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level=level)
    except Exception:
        return
