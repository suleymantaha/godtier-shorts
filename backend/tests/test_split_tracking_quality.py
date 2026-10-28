"""Split diagnostics aggregate panel observations, not output video frames."""
from __future__ import annotations

import pytest

from backend.services.video_processor import TrackingDiagnostics


@pytest.mark.parametrize("primary_jump,secondary_jump", [(4.0, 8.0), (0.0, 8.0), (4.0, 0.0)])
def test_split_average_center_jump_includes_both_panels(
    primary_jump: float, secondary_jump: float
) -> None:
    primary = TrackingDiagnostics(mode="tracked", fps=30.0, layout="split")
    secondary = TrackingDiagnostics(mode="tracked", fps=30.0, layout="split")
    for diagnostics, jump in ((primary, primary_jump), (secondary, secondary_jump)):
        diagnostics.register_mode("tracked")
        diagnostics.register_center_jump(jump)

    quality = TrackingDiagnostics.merge(primary, secondary)

    assert quality["avg_center_jump_px"] == (primary_jump + secondary_jump) / 2


def test_split_fallback_counts_panel_observations_and_retains_worst_panel_status() -> None:
    primary = TrackingDiagnostics(mode="tracked", fps=30.0, layout="split")
    secondary = TrackingDiagnostics(mode="tracked", fps=30.0, layout="split")
    for _ in range(360):
        primary.register_mode("tracked")
    for index in range(360):
        secondary.register_mode("grace" if index < 215 else "tracked")

    quality = TrackingDiagnostics.merge(primary, secondary)

    assert quality["total_frames"] == 720
    assert quality["fallback_frames"] == 215
    assert quality["grace_hold_frames"] == 215
    assert quality["status"] == "fallback"
