from __future__ import annotations

import subprocess

from backend.config import MASTER_VIDEO, OUTPUTS_DIR, ProjectPaths
from backend.core import workflow_runtime
from backend.services.ownership import build_owner_scoped_project_id


def test_create_subtitle_renderer_uses_named_style_preset_and_canvas(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeStyleManager:
        @staticmethod
        def resolve_style(style_name: str, animation_type: str) -> str:
            observed["style_name"] = style_name
            observed["animation_type"] = animation_type
            return "resolved-style"

    class FakeSubtitleRenderer:
        def __init__(
            self,
            style: str,
            *,
            canvas_width: int,
            canvas_height: int,
            layout: str,
            safe_area_profile: str,
            lower_third_detection: dict[str, object] | None,
        ):
            observed["style"] = style
            observed["canvas_width"] = canvas_width
            observed["canvas_height"] = canvas_height
            observed["layout"] = layout
            observed["safe_area_profile"] = safe_area_profile
            observed["lower_third_detection"] = lower_third_detection

    monkeypatch.setattr(workflow_runtime, "StyleManager", FakeStyleManager)
    monkeypatch.setattr(workflow_runtime, "SubtitleRenderer", FakeSubtitleRenderer)

    renderer = workflow_runtime.create_subtitle_renderer(
        "HORMOZI",
        animation_type="shake",
        canvas_width=720,
        canvas_height=1280,
        layout="split",
        safe_area_profile="lower_third_safe",
        lower_third_detection={"lower_third_collision_detected": True, "lower_third_band_height_ratio": 0.11},
    )

    assert isinstance(renderer, FakeSubtitleRenderer)
    assert observed == {
        "style_name": "HORMOZI",
        "animation_type": "shake",
        "style": "resolved-style",
        "canvas_width": 720,
        "canvas_height": 1280,
        "layout": "split",
        "safe_area_profile": "lower_third_safe",
        "lower_third_detection": {"lower_third_collision_detected": True, "lower_third_band_height_ratio": 0.11},
    }


def test_resolve_subtitle_render_plan_short_uses_video_processor_layout() -> None:
    class FakeVideoProcessor:
        def resolve_layout_for_segment(self, **kwargs) -> tuple[str, str | None]:
            assert kwargs["requested_layout"] == "split"
            return "single", "split_not_stable"

        def _extract_probe_frame(self, *_args, **_kwargs):
            return None

    plan = workflow_runtime.resolve_subtitle_render_plan(
        video_processor=FakeVideoProcessor(),
        source_video="master.mp4",
        start_t=1.0,
        end_t=3.0,
        requested_layout="split",
        cut_as_short=True,
        manual_center_x=None,
    )

    assert plan.canvas_width == 1080
    assert plan.canvas_height == 1920
    assert plan.requested_layout == "split"
    assert plan.resolved_layout == "single"
    assert plan.layout_fallback_reason == "split_not_stable"
    assert plan.safe_area_profile == "default"


def test_resolve_subtitle_render_plan_non_short_probes_canvas(monkeypatch) -> None:
    monkeypatch.setattr(workflow_runtime, "probe_video_canvas", lambda _path: (1920, 1080))

    class FakeVideoProcessor:
        def resolve_layout_for_segment(self, **kwargs) -> tuple[str, str | None]:
            raise AssertionError("should not be called for cut_as_short=False")

        def _extract_probe_frame(self, *_args, **_kwargs):
            return None

    plan = workflow_runtime.resolve_subtitle_render_plan(
        video_processor=FakeVideoProcessor(),
        source_video="clip.mp4",
        start_t=0.0,
        end_t=5.0,
        requested_layout="split",
        cut_as_short=False,
        manual_center_x=None,
    )

    assert plan.canvas_width == 1920
    assert plan.canvas_height == 1080
    assert plan.resolved_layout == "single"
    assert plan.layout_fallback_reason == "split_requires_short_canvas"
    assert plan.safe_area_profile == "default"


def test_resolve_subtitle_render_plan_uses_lower_third_safe_area_when_detected(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_runtime,
        "_resolve_safe_area_detection",
        lambda **_kwargs: {
            "safe_area_profile": "lower_third_safe",
            "lower_third_collision_detected": True,
            "lower_third_band_height_ratio": 0.14,
        },
    )

    class FakeVideoProcessor:
        def resolve_layout_for_segment(self, **_kwargs) -> tuple[str, str | None]:
            return "single", None

    plan = workflow_runtime.resolve_subtitle_render_plan(
        video_processor=FakeVideoProcessor(),
        source_video="master.mp4",
        start_t=5.0,
        end_t=35.0,
        requested_layout="auto",
        cut_as_short=True,
        manual_center_x=None,
    )

    assert plan.safe_area_profile == "lower_third_safe"
    assert plan.lower_third_collision_detected is True
    assert plan.lower_third_band_height_ratio == 0.14


def test_probe_video_canvas_uses_ffprobe(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=["ffprobe"], returncode=0, stdout="1920x1080\n", stderr="")

    monkeypatch.setattr(workflow_runtime.subprocess, "run", fake_run)
    assert workflow_runtime.probe_video_canvas("video.mp4") == (1920, 1080)


def test_probe_video_canvas_falls_back_to_default_on_error(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=["ffprobe"])

    monkeypatch.setattr(workflow_runtime.subprocess, "run", fake_run)
    assert workflow_runtime.probe_video_canvas("missing.mp4") == (1080, 1920)


def test_resolve_project_master_video_uses_existing_project() -> None:
    project_id = build_owner_scoped_project_id("proj", "workflow-owner", "runtime-existing")
    project, master_video = workflow_runtime.resolve_project_master_video(
        project_id,
        generated_prefix="manual",
    )

    assert project.root.name == project_id
    assert master_video == str(project.master_video)


def test_resolve_project_master_video_uses_owner_scoped_prefix_when_project_missing() -> None:
    project, master_video = workflow_runtime.resolve_project_master_video(
        None,
        generated_prefix="batch",
        owner_subject="workflow-owner",
        timestamp_provider=lambda: 4242,
    )

    expected_project_id = build_owner_scoped_project_id("batch", "workflow-owner", "4242")
    assert project.root.name == expected_project_id
    assert master_video == str(MASTER_VIDEO)


def test_resolve_output_video_path_uses_project_outputs_when_project_present() -> None:
    project_id = build_owner_scoped_project_id("proj", "workflow-owner", "runtime-outputs")
    output_path = workflow_runtime.resolve_output_video_path("clip.mp4", project_id)
    assert output_path == str(ProjectPaths(project_id).outputs / "clip.mp4")


def test_resolve_output_video_path_uses_legacy_outputs_without_project() -> None:
    output_path = workflow_runtime.resolve_output_video_path("clip.mp4", None)
    assert output_path == str(OUTPUTS_DIR / "clip.mp4")
