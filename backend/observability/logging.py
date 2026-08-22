from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from loguru import logger


_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)([a-z0-9_-]*(?:password|secret|token|api[_-]?key|private[_-]?key|cookie)[a-z0-9_-]*\s*[:=]\s*)[^\s,;]+"
    ),
)
_ALLOWED_CONTEXT = frozenset(
    {
        "action",
        "alert_code",
        "component",
        "event",
        "job_id",
        "provider",
        "request_id",
        "status",
        "threshold",
        "value",
        "worker_id",
    }
)
_configured_mode: str | None = None


def _redact_text(value: object) -> str:
    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[redacted]", text)
    return text


def _iso_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        current = value
    else:
        current = datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_structured_log(record: dict[str, Any]) -> str:
    level = record.get("level")
    level_name = getattr(level, "name", level)
    payload: dict[str, object] = {
        "timestamp": _iso_timestamp(record.get("time")),
        "level": str(level_name or "INFO").lower(),
        "message": _redact_text(record.get("message")),
    }
    extra = record.get("extra")
    if isinstance(extra, dict):
        for key in sorted(_ALLOWED_CONTEXT):
            value = extra.get(key)
            if value is not None:
                payload[key] = _redact_text(value)
    exception = record.get("exception")
    if exception:
        payload["exception"] = _redact_text(exception)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class JsonLogSink:
    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, message: Any) -> None:
        self._stream.write(build_structured_log(message.record) + "\n")
        self._stream.flush()


def configure_logging(app_env: str, logs_dir: Path) -> None:
    global _configured_mode
    mode = "production" if app_env.strip().lower() == "production" else "development"
    if _configured_mode == mode:
        return
    logger.remove()
    if mode == "production":
        logger.add(JsonLogSink(sys.stderr), level="INFO", backtrace=False, diagnose=False)
    else:
        logger.add(sys.stderr, level="DEBUG")
        logger.add(
            str(logs_dir / "api_server_{time:YYYY-MM-DD}.log"),
            rotation="50 MB",
            retention="10 days",
            level="DEBUG",
        )
    _configured_mode = mode
