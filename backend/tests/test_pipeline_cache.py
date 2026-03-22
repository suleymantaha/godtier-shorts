from __future__ import annotations

import json
from pathlib import Path

import backend.config as config
from backend.core.clip_events import NullClipEventPort
from backend.core.workflow_helpers import (
    build_pipeline_cache_identity,
    build_segments_signature,
    load_pipeline_render_cache_hit,
    record_pipeline_analysis_cache,
    record_pipeline_render_cache,
    write_json_atomic,
)
from backend.services.ownership import build_owner_scoped_project_id


def _build_project(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "pipeline-cache-test-secret")
    project_id = build_owner_scoped_project_id("yt", "subject-a", "video123")
    project = config.ProjectPaths(project_id)
    project.master_video.write_bytes(b"master-video")
    project.master_audio.write_bytes(b"master-audio")
    project.transcript.write_text(json.dumps([{"text": "hello"}]), encoding="utf-8")
    return project


def _build_identity(project: config.ProjectPaths):
    return build_pipeline_cache_identity(
        project=project,
        ai_engine="local",
        num_clips=1,
        duration_min=120.0,
        duration_max=180.0,
        style_name="TIKTOK",
        animation_type="default",
        layout="auto",
        skip_subtitles=False,
        video_model_identifier="yolo11x.pt",
    )


class _RecordingClipEventPort(NullClipEventPort):
    def __init__(self) -> None:
        self.invalidate_calls: list[str] = []

    def invalidate_clips_cache(self, *, reason: str) -> None:
        self.invalidate_calls.append(reason)


def _write_clip_assets(
    project: config.ProjectPaths,
    clip_name: str,
    *,
    analysis_key: str,
    render_key: str,
) -> None:
    stem = Path(clip_name).stem
    (project.outputs / clip_name).write_bytes(b"clip")
    (project.outputs / f"{stem}_raw.mp4").write_bytes(b"raw")
    write_json_atomic(
        project.outputs / f"{stem}.json",
        {
            "transcript": [],
            "render_metadata": {
                "analysis_key": analysis_key,
                "render_key": render_key,
            },
        },
    )


def test_pipeline_render_cache_hit_requires_matching_assets(monkeypatch, tmp_path: Path) -> None:
    project = _build_project(monkeypatch, tmp_path)
    identity = _build_identity(project)
    viral_results = {
        "segments": [
            {"start_time": 0.0, "end_time": 10.0, "hook_text": "Hook", "ui_title": "Title", "viral_score": 0.9},
        ],
    }
    write_json_atomic(project.viral_meta, viral_results)
    record_pipeline_analysis_cache(project, identity=identity, viral_results=viral_results)

    clip_name = "short_1_hook.mp4"
    _write_clip_assets(project, clip_name, analysis_key=identity.analysis_key, render_key=identity.render_key)
    record_pipeline_render_cache(
        project,
        identity=identity,
        segments_signature=build_segments_signature(viral_results["segments"]),
        clip_names=[clip_name],
        skip_subtitles=False,
    )

    hit = load_pipeline_render_cache_hit(
        project,
        render_key=identity.render_key,
        segments_signature=build_segments_signature(viral_results["segments"]),
    )
    assert hit is not None
    assert hit.clip_count == 1

    (project.outputs / clip_name).unlink()
    missed = load_pipeline_render_cache_hit(
        project,
        render_key=identity.render_key,
        segments_signature=build_segments_signature(viral_results["segments"]),
    )
    assert missed is None


def test_record_pipeline_render_cache_removes_previous_active_set(monkeypatch, tmp_path: Path) -> None:
    project = _build_project(monkeypatch, tmp_path)
    identity = _build_identity(project)
    viral_results = {
        "segments": [
            {"start_time": 0.0, "end_time": 10.0, "hook_text": "Hook", "ui_title": "Title", "viral_score": 0.9},
        ],
    }
    write_json_atomic(project.viral_meta, viral_results)
    record_pipeline_analysis_cache(project, identity=identity, viral_results=viral_results)

    clip_event_port = _RecordingClipEventPort()

    old_clip = "short_1_old.mp4"
    _write_clip_assets(project, old_clip, analysis_key=identity.analysis_key, render_key=identity.render_key)
    record_pipeline_render_cache(
        project,
        identity=identity,
        segments_signature="old-signature",
        clip_names=[old_clip],
        skip_subtitles=False,
        clip_event_port=clip_event_port,
    )

    new_clip = "short_1_new.mp4"
    _write_clip_assets(project, new_clip, analysis_key=identity.analysis_key, render_key=identity.render_key)
    deleted_count = record_pipeline_render_cache(
        project,
        identity=identity,
        segments_signature="new-signature",
        clip_names=[new_clip],
        skip_subtitles=False,
        clip_event_port=clip_event_port,
    )

    assert deleted_count == 3
    assert not (project.outputs / old_clip).exists()
    assert not (project.outputs / "short_1_old.json").exists()
    assert not (project.outputs / "short_1_old_raw.mp4").exists()
    assert (project.outputs / new_clip).exists()
    assert project.master_video.exists()
    assert project.master_audio.exists()
    assert project.transcript.exists()
    assert project.viral_meta.exists()
    assert clip_event_port.invalidate_calls == [f"pipeline_render_cleanup:{project.root.name}"]
