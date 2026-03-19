"""Shared request/render contract helpers for layout and duration handling."""

from __future__ import annotations

from typing import Final

DEFAULT_AUTO_DURATION_MIN: Final[float] = 120.0
DEFAULT_AUTO_DURATION_MAX: Final[float] = 180.0

VALID_RENDER_LAYOUTS: Final[tuple[str, str]] = ("single", "split")
VALID_REQUEST_LAYOUTS: Final[tuple[str, str, str]] = ("auto", *VALID_RENDER_LAYOUTS)


def ensure_valid_requested_layout(layout: str | None, *, default: str = "auto") -> str:
    normalized = (layout or default).strip().lower()
    if normalized not in VALID_REQUEST_LAYOUTS:
        raise ValueError(f"unknown requested layout: {layout}")
    return normalized


def ensure_valid_render_layout(layout: str | None, *, default: str = "single") -> str:
    normalized = (layout or default).strip().lower()
    if normalized not in VALID_RENDER_LAYOUTS:
        raise ValueError(f"unknown layout: {layout}")
    return normalized


def resolve_duration_range(
    duration_min: float | None,
    duration_max: float | None,
    *,
    default_min: float = DEFAULT_AUTO_DURATION_MIN,
    default_max: float = DEFAULT_AUTO_DURATION_MAX,
) -> tuple[float, float]:
    resolved_min = float(duration_min) if duration_min is not None else float(default_min)
    resolved_max = float(duration_max) if duration_max is not None else float(default_max)
    if resolved_min > resolved_max:
        resolved_min, resolved_max = resolved_max, resolved_min
    return resolved_min, resolved_max


def resolve_duration_validation_status(
    start_time: float,
    end_time: float,
    *,
    duration_min: float,
    duration_max: float,
) -> str:
    if end_time <= start_time:
        return "invalid"

    duration = float(end_time) - float(start_time)
    if duration < float(duration_min):
        return "too_short"
    if duration > float(duration_max):
        return "too_long"
    return "ok"
