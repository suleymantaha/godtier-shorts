"""Shared runtime helpers for workflow modules."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

from loguru import logger

from backend.config import MASTER_VIDEO, OUTPUTS_DIR, ProjectPaths
from backend.services.ownership import build_owner_scoped_project_id
from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.subtitle_styles import (
    LOGICAL_CANVAS_HEIGHT,
    LOGICAL_CANVAS_WIDTH,
    StyleManager,
)
from backend.services.video_processor import VideoProcessor

TimestampProvider = Callable[[], int]


@dataclass(frozen=True)
class SubtitleRenderPlan:
    canvas_width: int
    canvas_height: int
    requested_layout: str
    resolved_layout: str
    layout_fallback_reason: str | None = None


def create_subtitle_renderer(
    style_name: str,
    *,
    animation_type: str = "default",
    canvas_width: int = LOGICAL_CANVAS_WIDTH,
    canvas_height: int = LOGICAL_CANVAS_HEIGHT,
    layout: str = "single",
) -> SubtitleRenderer:
    """Build a subtitle renderer from a named style preset."""
    return SubtitleRenderer(
        style=StyleManager.resolve_style(style_name, animation_type),
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        layout=layout,
    )


def resolve_subtitle_render_plan(
    *,
    video_processor: VideoProcessor,
    source_video: str,
    start_t: float,
    end_t: float,
    requested_layout: str,
    cut_as_short: bool,
    manual_center_x: float | None = None,
) -> SubtitleRenderPlan:
    """Resolve final canvas size and effective layout before ASS generation."""
    normalized_layout = StyleManager.ensure_valid_layout(requested_layout)

    if cut_as_short:
        resolved_layout, fallback_reason = video_processor.resolve_layout_for_segment(
            input_video=source_video,
            start_time=start_t,
            end_time=end_t,
            requested_layout=normalized_layout,
            manual_center_x=manual_center_x,
        )
        return SubtitleRenderPlan(
            canvas_width=LOGICAL_CANVAS_WIDTH,
            canvas_height=LOGICAL_CANVAS_HEIGHT,
            requested_layout=normalized_layout,
            resolved_layout=resolved_layout,
            layout_fallback_reason=fallback_reason,
        )

    canvas_width, canvas_height = probe_video_canvas(source_video)
    resolved_layout = normalized_layout
    fallback_reason: str | None = None
    if normalized_layout == "split":
        if canvas_width == LOGICAL_CANVAS_WIDTH and canvas_height == LOGICAL_CANVAS_HEIGHT:
            resolved_layout = "split"
        else:
            resolved_layout = "single"
            fallback_reason = "split_requires_short_canvas"

    return SubtitleRenderPlan(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        requested_layout=normalized_layout,
        resolved_layout=resolved_layout,
        layout_fallback_reason=fallback_reason,
    )


def probe_video_canvas(video_path: str) -> tuple[int, int]:
    """Probe a video stream's first video width and height using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        video_path,
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        raw = completed.stdout.strip()
        width_raw, height_raw = raw.split("x", 1)
        width = int(width_raw)
        height = int(height_raw)
        if width <= 0 or height <= 0:
            raise ValueError(raw)
        return width, height
    except Exception as exc:
        logger.warning(f"Video canvas probe başarısız, varsayılan canvas kullanılacak: {exc}")
        return LOGICAL_CANVAS_WIDTH, LOGICAL_CANVAS_HEIGHT


def resolve_project_master_video(
    project_id: Optional[str],
    *,
    generated_prefix: str,
    owner_subject: str | None = None,
    timestamp_provider: Optional[TimestampProvider] = None,
) -> tuple[ProjectPaths, str]:
    """Resolve workflow project context and the source master video path."""
    if project_id:
        project = ProjectPaths(project_id)
        return project, str(project.master_video)

    if not owner_subject:
        raise ValueError("Yeni proje baglami icin owner_subject gerekli")

    now = timestamp_provider or _default_timestamp_provider
    project = ProjectPaths(build_owner_scoped_project_id(generated_prefix, owner_subject, str(now())))
    return project, str(MASTER_VIDEO)


def resolve_output_video_path(clip_name: str, project_id: Optional[str]) -> str:
    """Resolve a clip path either inside a project or the legacy outputs area."""
    if project_id:
        return str(ProjectPaths(project_id).outputs / clip_name)
    return str(OUTPUTS_DIR / clip_name)


def _default_timestamp_provider() -> int:
    return int(time.time())
