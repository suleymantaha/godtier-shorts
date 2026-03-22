from __future__ import annotations

from pathlib import Path

import backend.config as config
from backend.core.workflow_helpers import extract_youtube_video_id, persist_debug_artifacts
from backend.services.ownership import build_owner_scoped_project_id


def test_persist_debug_artifacts_returns_none_when_debug_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEBUG_RENDER_ARTIFACTS", raising=False)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    project = config.ProjectPaths(build_owner_scoped_project_id("proj", "subject-a", "one"))

    result = persist_debug_artifacts(
        project=project,
        clip_name="clip_1.mp4",
        render_report={},
        subtitle_layout_quality={},
        snap_report=None,
        debug_timing=None,
    )

    assert result is None


def test_persist_debug_artifacts_writes_bundle_and_moves_overlay(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEBUG_RENDER_ARTIFACTS", "1")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    project = config.ProjectPaths(build_owner_scoped_project_id("proj", "subject-a", "two"))
    overlay_temp = tmp_path / "overlay.mp4"
    overlay_temp.write_bytes(b"overlay")

    result = persist_debug_artifacts(
        project=project,
        clip_name="clip_2.mp4",
        render_report={
            "debug_tracking": {"timeline": [{"frame": 1, "mode": "tracked"}]},
            "debug_overlay_temp_path": str(overlay_temp),
            "debug_artifacts_status": "complete",
        },
        subtitle_layout_quality={"chunk_dump": [{"text": "hello", "start": 0.0, "end": 1.0, "words": []}]},
        snap_report={"enabled": True, "boundary_snaps_applied": 1},
        debug_timing={"merged_output_drift_ms": 12.5},
    )

    assert result == {
        "tracking_timeline": "debug/clip_2/tracking_timeline.json",
        "subtitle_chunks": "debug/clip_2/subtitle_chunks.json",
        "boundary_snap": "debug/clip_2/boundary_snap.json",
        "timing_report": "debug/clip_2/timing_report.json",
        "tracking_overlay": "debug/clip_2/tracking_overlay.mp4",
        "status": "complete",
    }
    assert not overlay_temp.exists()
    assert (project.root / result["tracking_overlay"]).exists()


def test_persist_debug_artifacts_marks_missing_overlay_as_partial(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEBUG_RENDER_ARTIFACTS", "1")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    project = config.ProjectPaths(build_owner_scoped_project_id("proj", "subject-a", "three"))

    result = persist_debug_artifacts(
        project=project,
        clip_name="clip_3.mp4",
        render_report={"debug_tracking": {"timeline": []}},
        subtitle_layout_quality={"chunk_dump": []},
        snap_report=None,
        debug_timing={"merged_output_drift_ms": 0.0},
    )

    assert result is not None
    assert result["status"] == "partial"
    assert "tracking_overlay" not in result


def test_extract_youtube_video_id_supports_common_url_shapes() -> None:
    assert extract_youtube_video_id("mvYVI3wbY_g") == "mvYVI3wbY_g"
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=mvYVI3wbY_g&t=2s") == "mvYVI3wbY_g"
    assert extract_youtube_video_id("https://youtu.be/mvYVI3wbY_g?si=test") == "mvYVI3wbY_g"
    assert extract_youtube_video_id("https://www.youtube.com/shorts/mvYVI3wbY_g") == "mvYVI3wbY_g"


def test_extract_youtube_video_id_returns_none_for_non_youtube_urls() -> None:
    assert extract_youtube_video_id("https://example.com/watch?v=mvYVI3wbY_g") is None
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=short") is None
