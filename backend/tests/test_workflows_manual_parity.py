from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from backend.core.workflows_manual import ManualClipWorkflow


def _transcript() -> list[dict]:
    return [
        {
            "text": "one two",
            "start": 0.0,
            "end": 2.0,
            "words": [
                {"word": "one", "start": 0.0, "end": 1.0, "score": 0.99},
                {"word": "two", "start": 1.0, "end": 2.0, "score": 0.99},
            ],
        },
        {
            "text": "three",
            "start": 2.0,
            "end": 3.0,
            "words": [{"word": "three", "start": 2.0, "end": 3.0, "score": 0.99}],
        },
    ]


def _plan(layout: str) -> SimpleNamespace:
    return SimpleNamespace(
        resolved_layout=layout,
        canvas_width=1080,
        canvas_height=1920,
        safe_area_profile="default",
        lower_third_collision_detected=False,
        lower_third_band_height_ratio=0.0,
        layout_fallback_reason=None,
        layout_safety_status="safe",
        layout_safety_mode="enforce",
        layout_safety_contract_version=1,
        scene_class="dialogue_two",
        speaker_count_peak=2 if layout == "split" else 1,
        dominant_speaker_confidence=0.9,
    )


class _GpuStage:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _FakeVideoProcessor:
    _model_path = "fake-yolo.pt"

    def __init__(self, suggested_start: float = 1.05) -> None:
        self.suggested_start = suggested_start

    def analyze_opening_shot(self, **kwargs) -> dict:
        return {
            "layout_validation_status": "ok",
            "opening_visibility_delay_ms": 50.0,
            "suggested_start_time": self.suggested_start,
            "initial_slot_centers": [320.0, 760.0],
        }


class _FakeSubtitleRenderer:
    generated_payloads: list[list[dict]] = []

    def generate_ass_file(self, shifted_json: str, ass_file: str, max_words_per_screen: int = 3) -> None:
        self.generated_payloads.append(json.loads(Path(shifted_json).read_text(encoding="utf-8")))
        Path(ass_file).write_text("[Script Info]\n", encoding="utf-8")


class _FakeContext:
    def __init__(self, project: SimpleNamespace, master_video: Path, render_reports: list[dict] | None = None) -> None:
        self.project = project
        self.subject = "subject"
        self.video_processor = _FakeVideoProcessor()
        self.clip_event_port = None
        self.master_video = master_video
        self.render_calls: list[dict] = []
        self.committed_metadata: dict | None = None
        self.render_reports = list(render_reports or [{"tracking_quality": {"status": "good"}}])

    def _update_status(self, *_args, **_kwargs) -> None:
        pass

    def _normalize_transcript_payload(self, transcript_data: list) -> list[dict]:
        return transcript_data

    def _load_project_transcript(self) -> list[dict]:
        return _transcript()

    def acquire_gpu_stage(self, **_kwargs) -> _GpuStage:
        return _GpuStage()

    def _cut_and_burn_clip(self, master_video, start_t, end_t, temp_cropped, final_output, ass_file, subtitle_engine, layout="single", center_x=None, initial_slot_centers=None, cut_as_short=True, require_audio=False) -> dict:
        self.render_calls.append({"start_t": start_t, "end_t": end_t, "layout": layout, "initial_slot_centers": initial_slot_centers})
        Path(final_output).parent.mkdir(parents=True, exist_ok=True)
        Path(final_output).write_bytes(b"video")
        return self.render_reports.pop(0) if self.render_reports else {"tracking_quality": {"status": "good"}}

    def _build_clip_metadata(self, transcript_data: list[dict], *, viral_metadata=None, render_metadata=None) -> dict:
        self.committed_metadata = {"transcript_data": transcript_data, "render_metadata": render_metadata or {}}
        return self.committed_metadata


def _install_manual_fakes(monkeypatch, tmp_path: Path, ctx: _FakeContext):
    import backend.core.workflow_runtime as runtime
    import backend.core.workflows_manual as manual

    plan_calls: list[dict] = []

    def fake_resolve_project_master_video(project_id, generated_prefix, owner_subject):
        return ctx.project, str(ctx.master_video)

    def fake_resolve_subtitle_render_plan(**kwargs):
        plan_calls.append(dict(kwargs))
        return _plan(str(kwargs["requested_layout"]) if kwargs["requested_layout"] != "auto" else "split")

    def fake_commit_render_bundle(**kwargs):
        return str(tmp_path / kwargs["clip_filename"])

    monkeypatch.setattr(runtime, "resolve_project_master_video", fake_resolve_project_master_video)
    monkeypatch.setattr(runtime, "resolve_subtitle_render_plan", fake_resolve_subtitle_render_plan)
    monkeypatch.setattr(runtime, "create_subtitle_renderer", lambda *args, **kwargs: _FakeSubtitleRenderer())
    monkeypatch.setattr(manual, "commit_render_bundle", fake_commit_render_bundle)
    monkeypatch.setattr(manual, "build_quarantine_output_path", lambda project, clip_filename: tmp_path / "quarantine" / clip_filename)
    return plan_calls


def _make_context(tmp_path: Path, render_reports: list[dict] | None = None) -> _FakeContext:
    project = SimpleNamespace(root=tmp_path / "project", outputs=tmp_path / "outputs", debug=tmp_path / "debug")
    project.root.mkdir()
    project.outputs.mkdir()
    project.debug.mkdir()
    master_video = tmp_path / "master.mp4"
    master_video.write_bytes(b"source")
    return _FakeContext(project, master_video, render_reports=render_reports)


def test_manual_snap_and_opening_validation_use_resolved_window_for_render_and_subtitles(monkeypatch, tmp_path: Path) -> None:
    ctx = _make_context(tmp_path)
    _FakeSubtitleRenderer.generated_payloads.clear()
    _install_manual_fakes(monkeypatch, tmp_path, ctx)

    asyncio.run(ManualClipWorkflow(ctx).run(0.2, 2.9, _transcript(), output_name="manual.mp4", layout="auto"))

    assert ctx.render_calls[0]["start_t"] == 1.0
    assert ctx.render_calls[0]["end_t"] == 3.0
    assert ctx.render_calls[0]["initial_slot_centers"] == (320.0, 760.0)
    shifted_words = [word for segment in _FakeSubtitleRenderer.generated_payloads[0] for word in segment.get("words", [])]
    assert shifted_words[0]["word"] == "two"
    assert shifted_words[0]["start"] == 0.0
    assert ctx.committed_metadata["render_metadata"]["start_time"] == 1.0
    assert ctx.committed_metadata["render_metadata"]["transcript_quality"]["boundary_snaps_applied"] == 1


def test_manual_split_fallback_rebuilds_single_plan_with_resolved_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYOUT_SAFETY_MODE", "enforce")
    ctx = _make_context(
        tmp_path,
        render_reports=[
            {"tracking_quality": {"status": "good", "layout_safety_status": "unsafe"}},
            {"tracking_quality": {"status": "good", "layout_safety_status": "safe"}},
        ],
    )
    plan_calls = _install_manual_fakes(monkeypatch, tmp_path, ctx)

    asyncio.run(ManualClipWorkflow(ctx).run(0.2, 2.9, _transcript(), output_name="manual.mp4", layout="auto"))

    single_plan_call = [call for call in plan_calls if call["requested_layout"] == "single"][-1]
    assert single_plan_call["start_t"] == 1.0
    assert single_plan_call["end_t"] == 3.0
    assert ctx.render_calls[-1]["layout"] == "single"


def test_manual_debug_artifacts_include_boundary_snap(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEBUG_RENDER_ARTIFACTS", "1")
    ctx = _make_context(tmp_path)
    _install_manual_fakes(monkeypatch, tmp_path, ctx)

    asyncio.run(ManualClipWorkflow(ctx).run(0.2, 2.9, _transcript(), output_name="manual.mp4", layout="auto"))

    boundary_snap = tmp_path / "debug" / "manual" / "boundary_snap.json"
    assert boundary_snap.exists()
    payload = json.loads(boundary_snap.read_text(encoding="utf-8"))
    assert payload["snapped_start_time"] == 1.0
    assert payload["boundary_snaps_applied"] == 1
