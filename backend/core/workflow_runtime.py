"""Shared runtime helpers for workflow modules."""

from __future__ import annotations

import time
from typing import Callable, Optional

from backend.config import MASTER_VIDEO, OUTPUTS_DIR, ProjectPaths
from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.subtitle_styles import StyleManager

TimestampProvider = Callable[[], int]


def create_subtitle_renderer(style_name: str) -> SubtitleRenderer:
    """Build a subtitle renderer from a named style preset."""
    return SubtitleRenderer(style=StyleManager.get_preset(style_name))


def resolve_project_master_video(
    project_id: Optional[str],
    *,
    generated_prefix: str,
    timestamp_provider: Optional[TimestampProvider] = None,
) -> tuple[ProjectPaths, str]:
    """Resolve workflow project context and the source master video path."""
    if project_id:
        project = ProjectPaths(project_id)
        return project, str(project.master_video)

    now = timestamp_provider or _default_timestamp_provider
    project = ProjectPaths(f"{generated_prefix}_{now()}")
    return project, str(MASTER_VIDEO)


def resolve_output_video_path(clip_name: str, project_id: Optional[str]) -> str:
    """Resolve a clip path either inside a project or the legacy outputs area."""
    if project_id:
        return str(ProjectPaths(project_id).outputs / clip_name)
    return str(OUTPUTS_DIR / clip_name)


def _default_timestamp_provider() -> int:
    return int(time.time())
