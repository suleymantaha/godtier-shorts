from __future__ import annotations

from backend.core.render_contracts import (
    ensure_valid_requested_layout,
    resolve_duration_range,
    resolve_duration_validation_status,
)


def test_resolve_duration_range_uses_shared_defaults() -> None:
    assert resolve_duration_range(None, None) == (120.0, 180.0)


def test_resolve_duration_range_swaps_reversed_values() -> None:
    assert resolve_duration_range(180.0, 120.0) == (120.0, 180.0)


def test_resolve_duration_validation_status_reports_bounds() -> None:
    assert resolve_duration_validation_status(0.0, 130.0, duration_min=120.0, duration_max=180.0) == "ok"
    assert resolve_duration_validation_status(0.0, 90.0, duration_min=120.0, duration_max=180.0) == "too_short"
    assert resolve_duration_validation_status(0.0, 220.0, duration_min=120.0, duration_max=180.0) == "too_long"


def test_ensure_valid_requested_layout_accepts_auto() -> None:
    assert ensure_valid_requested_layout("auto") == "auto"
    assert ensure_valid_requested_layout("split") == "split"
