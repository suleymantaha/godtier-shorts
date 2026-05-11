from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import backend.config as config
from backend.core.workflow_artifacts import assess_layout_safety
from backend.core.workflow_helpers import build_pipeline_render_key, extract_youtube_video_id, persist_debug_artifacts
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


def test_build_pipeline_render_key_includes_layout_safety_contract(monkeypatch) -> None:
    monkeypatch.setenv("LAYOUT_SAFETY_MODE", "enforce")

    _render_key, payload = build_pipeline_render_key(
        analysis_key="analysis-key",
        style_name="HORMOZI",
        animation_type="default",
        layout="auto",
        skip_subtitles=False,
        video_model_identifier="yolo11x.pt",
    )

    assert payload["layout_safety_mode"] == "enforce"
    assert payload["layout_safety_contract_version"] == 1


def test_assess_layout_safety_marks_listener_lock_for_auto_repair() -> None:
    render_plan = SimpleNamespace(
        resolved_layout="single",
        layout_safety_status="safe",
        layout_safety_mode="shadow",
        layout_safety_contract_version=1,
        layout_fallback_reason="split_not_stable",
        layout_auto_fix_reason="split_face_safety",
        layout_auto_fix_applied=True,
        scene_class="dual_overlap_risky",
        speaker_count_peak=3,
        dominant_speaker_confidence=None,
    )

    safety = assess_layout_safety(
        render_plan=render_plan,
        requested_layout="auto",
        tracking_quality={
            "status": "good",
            "listener_lock_suspected": True,
            "listener_lock_suspected_frames": 6,
            "startup_settle_ms": 500.0,
            "speaker_activity_confidence": 0.5,
        },
        manual_center_x=None,
    )

    assert safety["layout_safety_status"] == "degraded"
    assert safety["render_publication_status"] == "auto_repair"
    assert safety["auto_repair_recommended"] is True
    assert safety["review_recommended"] is False
    assert set(safety["quality_gate_reasons"]) >= {
        "listener_lock_suspected",
        "startup_settle_slow",
        "split_layout_fallback",
    }
