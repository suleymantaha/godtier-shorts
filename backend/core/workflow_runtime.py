"""Shared runtime helpers for workflow modules."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import numpy as np
from loguru import logger

from backend.config import MASTER_VIDEO, OUTPUTS_DIR, ProjectPaths
from backend.core.external_tools import ffprobe as resolve_ffprobe
from backend.core.render_contracts import ensure_valid_requested_layout
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
    layout_auto_fix_applied: bool = False
    layout_auto_fix_reason: str | None = None
    layout_safety_status: str = "safe"
    layout_safety_mode: str = "off"
    layout_safety_contract_version: int = 1
    scene_class: str = "single_dynamic"
    speaker_count_peak: int = 1
    dominant_speaker_confidence: float | None = None
    safe_area_profile: str = "default"
    lower_third_collision_detected: bool = False
    lower_third_band_height_ratio: float = 0.0


def create_subtitle_renderer(
    style_name: str,
    *,
    animation_type: str = "default",
    canvas_width: int = LOGICAL_CANVAS_WIDTH,
    canvas_height: int = LOGICAL_CANVAS_HEIGHT,
    layout: str = "single",
    safe_area_profile: str = "default",
    lower_third_detection: dict[str, object] | None = None,
) -> SubtitleRenderer:
    """Build a subtitle renderer from a named style preset."""
    return SubtitleRenderer(
        style=StyleManager.resolve_style(style_name, animation_type),
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        layout=layout,
        safe_area_profile=safe_area_profile,
        lower_third_detection=lower_third_detection,
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
    normalized_layout = ensure_valid_requested_layout(requested_layout)

    if cut_as_short:
        layout_decision = video_processor.resolve_layout_for_segment(
            input_video=source_video,
            start_time=start_t,
            end_time=end_t,
            requested_layout=normalized_layout,
            manual_center_x=manual_center_x,
        )
        if isinstance(layout_decision, tuple):
            resolved_layout, fallback_reason = layout_decision
            decision_payload = {
                "resolved_layout": resolved_layout,
                "layout_fallback_reason": fallback_reason,
                "layout_auto_fix_applied": bool(fallback_reason),
                "layout_auto_fix_reason": None,
                "layout_safety_status": "safe",
                "layout_safety_mode": "off",
                "layout_safety_contract_version": 1,
                "scene_class": "single_dynamic" if resolved_layout == "single" else "dual_separated",
                "speaker_count_peak": 1 if resolved_layout == "single" else 2,
                "dominant_speaker_confidence": None,
            }
        else:
            decision_payload = {
                "resolved_layout": str(getattr(layout_decision, "resolved_layout", "single") or "single"),
                "layout_fallback_reason": getattr(layout_decision, "layout_fallback_reason", None),
                "layout_auto_fix_applied": bool(getattr(layout_decision, "layout_auto_fix_applied", False)),
                "layout_auto_fix_reason": getattr(layout_decision, "layout_auto_fix_reason", None),
                "layout_safety_status": str(getattr(layout_decision, "layout_safety_status", "safe") or "safe"),
                "layout_safety_mode": str(getattr(layout_decision, "layout_safety_mode", "off") or "off"),
                "layout_safety_contract_version": int(getattr(layout_decision, "layout_safety_contract_version", 1) or 1),
                "scene_class": str(getattr(layout_decision, "scene_class", "single_dynamic") or "single_dynamic"),
                "speaker_count_peak": int(getattr(layout_decision, "speaker_count_peak", 1) or 1),
                "dominant_speaker_confidence": getattr(layout_decision, "dominant_speaker_confidence", None),
            }
        safe_area_detection = _resolve_safe_area_detection(
            video_processor=video_processor,
            source_video=source_video,
            start_t=start_t,
            end_t=end_t,
            resolved_layout=str(decision_payload["resolved_layout"]),
        )
        return SubtitleRenderPlan(
            canvas_width=LOGICAL_CANVAS_WIDTH,
            canvas_height=LOGICAL_CANVAS_HEIGHT,
            requested_layout=normalized_layout,
            resolved_layout=str(decision_payload["resolved_layout"]),
            layout_fallback_reason=decision_payload["layout_fallback_reason"],
            layout_auto_fix_applied=bool(decision_payload["layout_auto_fix_applied"]),
            layout_auto_fix_reason=decision_payload["layout_auto_fix_reason"],
            layout_safety_status=str(decision_payload["layout_safety_status"]),
            layout_safety_mode=str(decision_payload["layout_safety_mode"]),
            layout_safety_contract_version=int(decision_payload["layout_safety_contract_version"]),
            scene_class=str(decision_payload["scene_class"]),
            speaker_count_peak=int(decision_payload["speaker_count_peak"]),
            dominant_speaker_confidence=float(decision_payload["dominant_speaker_confidence"]) if isinstance(decision_payload["dominant_speaker_confidence"], (int, float)) else None,
            safe_area_profile=str(safe_area_detection["safe_area_profile"]),
            lower_third_collision_detected=bool(safe_area_detection["lower_third_collision_detected"]),
            lower_third_band_height_ratio=float(safe_area_detection["lower_third_band_height_ratio"]),
        )

    canvas_width, canvas_height = probe_video_canvas(source_video)
    resolved_layout = "single" if normalized_layout == "auto" else normalized_layout
    fallback_reason: str | None = None
    if resolved_layout == "split":
        if canvas_width == LOGICAL_CANVAS_WIDTH and canvas_height == LOGICAL_CANVAS_HEIGHT:
            resolved_layout = "split"
        else:
            resolved_layout = "single"
            fallback_reason = "split_requires_short_canvas"

    safe_area_detection = _resolve_safe_area_detection(
        video_processor=video_processor,
        source_video=source_video,
        start_t=start_t,
        end_t=end_t,
        resolved_layout=resolved_layout,
    )

    return SubtitleRenderPlan(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        requested_layout=normalized_layout,
        resolved_layout=resolved_layout,
        layout_fallback_reason=fallback_reason,
        safe_area_profile=str(safe_area_detection["safe_area_profile"]),
        lower_third_collision_detected=bool(safe_area_detection["lower_third_collision_detected"]),
        lower_third_band_height_ratio=float(safe_area_detection["lower_third_band_height_ratio"]),
    )


def probe_video_canvas(video_path: str) -> tuple[int, int]:
    """Probe a video stream's first video width and height using ffprobe."""
    cmd = [
        resolve_ffprobe(),
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


LOWER_THIRD_SAFE_AREA_PROFILE = "lower_third_safe"
LOWER_THIRD_PROBE_SAMPLE_COUNT = 5
LOWER_THIRD_PROBE_WINDOW_SECONDS = 2.5


def _resolve_safe_area_detection(
    *,
    video_processor: VideoProcessor,
    source_video: str,
    start_t: float,
    end_t: float,
    resolved_layout: str,
) -> dict[str, object]:
    if resolved_layout != "single":
        return {
            "safe_area_profile": "default",
            "lower_third_collision_detected": False,
            "lower_third_band_height_ratio": 0.0,
        }

    duration = max(0.3, end_t - start_t)
    window = min(duration, LOWER_THIRD_PROBE_WINDOW_SECONDS)
    frames: list[np.ndarray] = []
    for sample_index in range(LOWER_THIRD_PROBE_SAMPLE_COUNT):
        ratio = 0.0 if LOWER_THIRD_PROBE_SAMPLE_COUNT == 1 else sample_index / (LOWER_THIRD_PROBE_SAMPLE_COUNT - 1)
        sample_time = start_t + (window * ratio)
        frame = video_processor._extract_probe_frame(source_video, sample_time)
        if frame is not None and frame.size > 0:
            frames.append(frame)
    return _detect_lower_third_collision(frames)


def _detect_lower_third_collision(frames: list[np.ndarray]) -> dict[str, object]:
    if len(frames) < 2:
        return {
            "safe_area_profile": "default",
            "lower_third_collision_detected": False,
            "lower_third_band_height_ratio": 0.0,
        }

    base_height, base_width = frames[0].shape[:2]
    if base_height <= 0 or base_width <= 0:
        return {
            "safe_area_profile": "default",
            "lower_third_collision_detected": False,
            "lower_third_band_height_ratio": 0.0,
        }

    normalized_frames = [
        frame if frame.shape[:2] == (base_height, base_width) else cv2.resize(frame, (base_width, base_height))
        for frame in frames
    ]
    gray_frames = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in normalized_frames]
    hsv_frames = [cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) for frame in normalized_frames]

    bottom_start = int(round(base_height * 0.74))
    center_start = int(round(base_height * 0.44))
    center_end = int(round(base_height * 0.68))
    if bottom_start >= base_height or center_start >= center_end:
        return {
            "safe_area_profile": "default",
            "lower_third_collision_detected": False,
            "lower_third_band_height_ratio": 0.0,
        }

    bottom_motion_samples: list[float] = []
    center_motion_samples: list[float] = []
    for previous, current in zip(gray_frames, gray_frames[1:]):
        bottom_motion_samples.append(float(np.mean(cv2.absdiff(previous[bottom_start:], current[bottom_start:]))))
        center_motion_samples.append(float(np.mean(cv2.absdiff(previous[center_start:center_end], current[center_start:center_end]))))

    median_gray = np.median(np.stack(gray_frames, axis=0), axis=0).astype(np.uint8)
    median_hsv = np.median(np.stack(hsv_frames, axis=0), axis=0).astype(np.uint8)
    bottom_roi_gray = median_gray[bottom_start:]
    bottom_roi_hsv = median_hsv[bottom_start:]
    edges = cv2.Canny(bottom_roi_gray, 60, 150)
    edge_density = float(np.mean(edges > 0))
    bottom_saturation = float(np.mean(bottom_roi_hsv[:, :, 1]))
    bottom_brightness = float(np.mean(bottom_roi_gray))
    bottom_motion = float(np.mean(bottom_motion_samples)) if bottom_motion_samples else 0.0
    center_motion = float(np.mean(center_motion_samples)) if center_motion_samples else 0.0

    stable_bottom = bottom_motion <= max(10.0, center_motion * 0.58)
    graphic_signal = edge_density >= 0.055 or bottom_saturation >= 46.0 or bottom_brightness <= 82.0
    detected = stable_bottom and graphic_signal
    if not detected:
        return {
            "safe_area_profile": "default",
            "lower_third_collision_detected": False,
            "lower_third_band_height_ratio": 0.0,
        }

    band_height_ratio = 0.14 if edge_density >= 0.09 or bottom_saturation >= 70.0 else 0.11
    logger.info(
        "Lower-third güvenli alan profili secildi. motion_bottom={:.2f} motion_center={:.2f} edge_density={:.3f} saturation={:.1f}",
        bottom_motion,
        center_motion,
        edge_density,
        bottom_saturation,
    )
    return {
        "safe_area_profile": LOWER_THIRD_SAFE_AREA_PROFILE,
        "lower_third_collision_detected": True,
        "lower_third_band_height_ratio": round(band_height_ratio, 4),
    }
