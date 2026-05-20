"""Pipeline status helpers for WebSocket/UI payloads."""

from __future__ import annotations

from typing import Any, Callable

StatusExtra = dict[str, Any]
StatusCallback = Callable[[str, int], None] | Callable[[str, int, StatusExtra | None], None]


def emit_pipeline_status(
    callback: StatusCallback | None,
    message: str,
    progress: int,
    *,
    severity: str = "info",
    **extra: Any,
) -> None:
    if callback is None:
        return

    payload: StatusExtra = {"severity": severity, **extra}
    try:
        callback(message, progress, payload)
    except TypeError:
        callback(message, progress)


def orchestrator_status_callback(
    update_status: Callable[[str, int, dict[str, Any] | None], None],
) -> StatusCallback:
    def callback(message: str, progress: int, extra: StatusExtra | None = None) -> None:
        update_status(message, progress, extra)

    return callback
