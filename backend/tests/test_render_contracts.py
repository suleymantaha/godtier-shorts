from __future__ import annotations

import pytest

from backend.core.render_contracts import (
    ensure_valid_requested_layout,
    resolve_duration_range,
    resolve_duration_validation_status,
    validate_source_window,
)


def test_resolve_duration_range_uses_shared_defaults() -> None:
    assert resolve_duration_range(None, None) == (120.0, 180.0)


def test_resolve_duration_range_swaps_reversed_values() -> None:
    assert resolve_duration_range(180.0, 120.0) == (120.0, 180.0)


def test_resolve_duration_validation_status_reports_bounds() -> None:
    assert resolve_duration_validation_status(0.0, 130.0, duration_min=120.0, duration_max=180.0) == "ok"
    assert resolve_duration_validation_status(0.0, 90.0, duration_min=120.0, duration_max=180.0) == "too_short"
    assert resolve_duration_validation_status(0.0, 220.0, duration_min=120.0, duration_max=180.0) == "too_long"


def test_resolve_duration_validation_status_allows_boundary_snap_drift() -> None:
    assert resolve_duration_validation_status(338.82, 518.92, duration_min=120.0, duration_max=180.0) == "ok"
    assert resolve_duration_validation_status(0.0, 181.0, duration_min=120.0, duration_max=180.0) == "too_long"


def test_ensure_valid_requested_layout_accepts_auto() -> None:
    assert ensure_valid_requested_layout("auto") == "auto"
    assert ensure_valid_requested_layout("split") == "split"


def test_validate_source_window_accepts_valid_cut() -> None:
    validate_source_window(1.0, 5.0, 10.0)


@pytest.mark.parametrize(
    "start,end,duration",
    [(-1.0, 2.0, 10.0), (2.0, 2.0, 10.0), (9.0, 11.0, 10.0), (float("nan"), 2.0, 10.0),
     (10.0, 10.05, 10.0), (10.02, 10.08, 10.0)],
)
def test_validate_source_window_rejects_invalid_cut(start: float, end: float, duration: float) -> None:
    with pytest.raises(ValueError):
        validate_source_window(start, end, duration)
