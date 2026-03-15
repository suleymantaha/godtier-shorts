"""Helpers to keep sensitive values out of logs and generic error payloads."""

from __future__ import annotations

import hashlib
import re
from typing import Any


_PATH_PATTERNS = [
    re.compile(r"/home/arch/godtier-shorts/[^\s'\"]+"),
    re.compile(r"/[^\s'\"]*workspace/projects/[^\s'\"]+"),
]


def sanitize_subject(subject: str | None) -> str:
    normalized = (subject or "").strip()
    if not normalized or normalized == "anonymous":
        return "anonymous"
    return f"subject:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]}"


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, str):
        sanitized = value
        for pattern in _PATH_PATTERNS:
            sanitized = pattern.sub("[redacted-path]", sanitized)
        return sanitized

    if isinstance(value, dict):
        return {key: sanitize_log_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_log_value(item) for item in value)

    return value
