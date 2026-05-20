"""Shared request/render contract helpers for layout and duration handling."""

from __future__ import annotations

from typing import Final

DEFAULT_AUTO_DURATION_MIN: Final[float] = 120.0
DEFAULT_AUTO_DURATION_MAX: Final[float] = 180.0
DEFAULT_DURATION_BOUNDARY_TOLERANCE_SECONDS: Final[float] = 0.5

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
    # pyrefly: ignore [unnecessary-type-conversion]
    resolved_min = float(duration_min) if duration_min is not None else float(default_min)
    # pyrefly: ignore [unnecessary-type-conversion]
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
    tolerance: float = DEFAULT_DURATION_BOUNDARY_TOLERANCE_SECONDS,
) -> str:
    if end_time <= start_time:
        return "invalid"

    # pyrefly: ignore [unnecessary-type-conversion]
    duration = float(end_time) - float(start_time)
    # pyrefly: ignore [unnecessary-type-conversion]
    tolerance = max(0.0, float(tolerance))
    # pyrefly: ignore [unnecessary-type-conversion]
    if duration < float(duration_min) - tolerance:
        return "too_short"
    # pyrefly: ignore [unnecessary-type-conversion]
    if duration > float(duration_max) + tolerance:
        return "too_long"
    return "ok"
