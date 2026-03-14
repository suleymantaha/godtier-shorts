from __future__ import annotations

from backend.config import MASTER_VIDEO, OUTPUTS_DIR, ProjectPaths
from backend.core import workflow_runtime


def test_create_subtitle_renderer_uses_named_style_preset(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeStyleManager:
        @staticmethod
        def get_preset(style_name: str) -> str:
            observed["style_name"] = style_name
            return "resolved-style"

    class FakeSubtitleRenderer:
        def __init__(self, style: str):
            observed["style"] = style

    monkeypatch.setattr(workflow_runtime, "StyleManager", FakeStyleManager)
    monkeypatch.setattr(workflow_runtime, "SubtitleRenderer", FakeSubtitleRenderer)

    renderer = workflow_runtime.create_subtitle_renderer("HORMOZI")

    assert isinstance(renderer, FakeSubtitleRenderer)
    assert observed == {"style_name": "HORMOZI", "style": "resolved-style"}


def test_resolve_project_master_video_uses_existing_project() -> None:
    project, master_video = workflow_runtime.resolve_project_master_video(
        "workflow_runtime_existing",
        generated_prefix="manual",
    )

    assert project.root.name == "workflow_runtime_existing"
    assert master_video == str(project.master_video)


def test_resolve_project_master_video_uses_prefixed_workspace_when_project_missing() -> None:
    project, master_video = workflow_runtime.resolve_project_master_video(
        None,
        generated_prefix="batch",
        timestamp_provider=lambda: 4242,
    )

    assert project.root.name == "batch_4242"
    assert master_video == str(MASTER_VIDEO)


def test_resolve_output_video_path_uses_project_outputs_when_project_present() -> None:
    output_path = workflow_runtime.resolve_output_video_path("clip.mp4", "workflow_runtime_outputs")

    assert output_path == str(ProjectPaths("workflow_runtime_outputs").outputs / "clip.mp4")


def test_resolve_output_video_path_uses_legacy_outputs_without_project() -> None:
    output_path = workflow_runtime.resolve_output_video_path("clip.mp4", None)

    assert output_path == str(OUTPUTS_DIR / "clip.mp4")
