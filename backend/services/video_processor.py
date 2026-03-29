"""
backend/services/video_processor.py
=====================================
YOLO + ffmpeg NVENC tabanli video kirpma ve dikey donusturme servisi.
"""

from __future__ import annotations

import gc
import io
import math
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field

import cv2
import numpy as np
import torch
from loguru import logger
from ultralytics import YOLO

from backend.config import LOGS_DIR, TEMP_DIR, YOLO_MODEL_PATH
from backend.core.render_contracts import ensure_valid_requested_layout
from backend.core.render_quality import extract_media_stream_metrics, probe_media
from backend.services.subtitle_styles import (
    LOGICAL_CANVAS_HEIGHT,
    LOGICAL_CANVAS_WIDTH,
    SPLIT_GUTTER_HEIGHT,
    SPLIT_PANEL_HEIGHT,
)

MIN_DETECTION_CONFIDENCE = 0.35
MIN_TRACK_ACCEPT_SCORE = 0.30
MISSING_TRACK_GRACE_FRAMES = 8
REACQUIRE_CONFIRMATION_FRAMES = 3
CONTROLLED_RETURN_FRAMES = 5
SINGLE_DEADZONE_RATIO = 0.012
SINGLE_MAX_STEP_RATIO = 0.012
SINGLE_EMA_ALPHA = 0.22
SINGLE_LOCK_SAFE_BAND_RATIO = 0.55
SINGLE_REFRAME_SUSTAINED_FRAMES = 3
SPLIT_DEADZONE_RATIO = 0.02
SPLIT_MAX_STEP_RATIO = 0.006
SPLIT_EMA_ALPHA = 0.16
SPLIT_CONTROLLED_RETURN_PAN_RATIO = 0.015
SPLIT_SUSTAINED_MOVEMENT_FRAMES = 3
SPLIT_FALLBACK_DEADZONE_RATIO = 0.06
SPLIT_FALLBACK_SUSTAINED_FRAMES = 4
SAME_ID_REACQUIRE_CENTER_RATIO = 0.08
DIFF_ID_REACQUIRE_CENTER_RATIO = 0.12
SPLIT_SAMPLE_WINDOWS = 16
SPLIT_REQUIRED_POSITIVE_WINDOWS = 12
SPLIT_MIN_SEPARATION_RATIO = 0.18
SPLIT_MIN_VISIBILITY_SCORE = 0.72
SPLIT_EDGE_MARGIN_RATIO = 0.06
SPLIT_UNSAFE_SUSTAINED_FRAMES = 4
LAYOUT_SAFETY_CONTRACT_VERSION = 1
TRACKER_CONFIG = "bytetrack.yaml"
DETECTION_LONG_EDGE = 960
CPU_TRACKING_STRIDE = 3
HARD_CUT_THRESHOLD = 0.75
SOFT_CUT_THRESHOLD = 0.55
OPENING_VISIBILITY_WINDOW_SECONDS = 1.5
OPENING_MAX_SHIFT_SECONDS = 3.0
OPENING_VISIBILITY_OK_SECONDS = 0.5
OPENING_SAMPLE_COUNT = 6
STARTUP_SETTLE_JUMP_THRESHOLD_PX = 4.0
SPLIT_JITTER_DEGRADED_THRESHOLD_PX = 12.0
STARTUP_SETTLE_DEGRADED_MS = 250.0


def _is_nvenc_error(stderr: str) -> bool:
    patterns = (
        "nvenc",
        "cuda",
        "cannot load libnvidia-encode",
        "no nvenc capable devices found",
        "error initializing output stream",
    )
    lowered = stderr.lower()
    return any(pattern in lowered for pattern in patterns)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _read_layout_safety_mode() -> str:
    raw = os.getenv("LAYOUT_SAFETY_MODE", "shadow").strip().lower()
    return raw if raw in {"off", "shadow", "enforce"} else "shadow"


def _box_iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])
    if x_right <= x_left or y_bottom <= y_top:
        return 0.0
    intersection = (x_right - x_left) * (y_bottom - y_top)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


@dataclass
class DetectionCandidate:
    track_id: int | None
    box: tuple[float, float, float, float]
    center_x: float
    area: float
    confidence: float
    aspect_ratio: float
    visibility_score: float = 0.0
    motion_score: float = 0.0
    mouth_motion_score: float = 0.0


@dataclass(frozen=True)
class LayoutDecisionReport:
    requested_layout: str
    resolved_layout: str
    layout_fallback_reason: str | None = None
    layout_auto_fix_applied: bool = False
    layout_auto_fix_reason: str | None = None
    layout_safety_status: str = "safe"
    layout_safety_mode: str = "off"
    layout_safety_contract_version: int = LAYOUT_SAFETY_CONTRACT_VERSION
    scene_class: str = "single_dynamic"
    speaker_count_peak: int = 1
    dominant_speaker_confidence: float | None = None

    def __iter__(self):
        yield self.resolved_layout
        yield self.layout_fallback_reason


@dataclass
class TrackSlotState:
    label: str
    current_cx: float
    confirmed_track_id: int | None = None
    last_confirmed_box: tuple[float, float, float, float] | None = None
    last_confirmed_center: float | None = None
    last_confirmed_area: float | None = None
    last_confirmed_aspect_ratio: float | None = None
    grace_remaining: int = 0
    controlled_return_frames_remaining: int = 0
    reacquire_counts: dict[int, int] = field(default_factory=dict)
    lost_streak: int = 0
    continuity_multiplier: float = 1.0
    last_mode: str = "fallback"
    sustained_movement_frames: int = 0
    unsafe_reframe_streak: int = 0
    last_visibility_score: float | None = None
    last_identity_confidence: float = 1.0


@dataclass
class TrackingDiagnostics:
    mode: str = "tracked"
    fps: float = 30.0
    layout: str = "single"
    total_frames: int = 0
    fallback_frames: int = 0
    confirmed_track_frames: int = 0
    grace_hold_frames: int = 0
    controlled_return_frames: int = 0
    reacquire_attempt_count: int = 0
    reacquire_success_count: int = 0
    active_track_id_switches: int = 0
    shot_cut_resets: int = 0
    max_track_lost_streak: int = 0
    total_center_jump_px: float = 0.0
    jump_samples: list[float] = field(default_factory=list)
    identity_confidence_samples: list[float] = field(default_factory=list)
    predict_fallback_active: bool = False
    timeline: list[dict] = field(default_factory=list)

    def register_mode(self, mode: str) -> None:
        self.total_frames += 1
        if mode == "tracked":
            self.confirmed_track_frames += 1
        elif mode == "grace":
            self.grace_hold_frames += 1
            self.fallback_frames += 1
        elif mode == "controlled_return":
            self.controlled_return_frames += 1
            self.fallback_frames += 1
        elif mode == "fallback":
            self.fallback_frames += 1

    def register_center_jump(self, jump_px: float) -> None:
        jump = max(0.0, float(jump_px))
        self.total_center_jump_px += jump
        self.jump_samples.append(jump)

    def register_identity_confidence(self, value: float) -> None:
        self.identity_confidence_samples.append(_clamp01(value))

    def to_quality(self) -> dict:
        avg_center_jump = self.total_center_jump_px / self.total_frames if self.total_frames > 0 else 0.0
        fallback_ratio = self.fallback_frames / self.total_frames if self.total_frames > 0 else 0.0
        p95_center_jump = self._percentile(self.jump_samples, 95)
        startup_settle_ms = self._compute_startup_settle_ms(self.jump_samples, self.fps)
        status = "good"
        if self.mode == "manual":
            status = "good"
        elif fallback_ratio >= 0.5:
            status = "fallback"
        elif (
            fallback_ratio >= 0.12
            or self.shot_cut_resets > 0
            or self.active_track_id_switches > 1
            or (self.layout == "split" and p95_center_jump > SPLIT_JITTER_DEGRADED_THRESHOLD_PX)
            or (self.layout == "split" and startup_settle_ms > STARTUP_SETTLE_DEGRADED_MS)
        ):
            status = "degraded"
        return {
            "status": status,
            "mode": self.mode,
            "total_frames": self.total_frames,
            "fallback_frames": self.fallback_frames,
            "avg_center_jump_px": round(avg_center_jump, 3),
            "p95_center_jump_px": round(p95_center_jump, 3),
            "startup_settle_ms": round(startup_settle_ms, 3),
            "predict_fallback_active": bool(self.predict_fallback_active),
            "speaker_lock_policy": "hold_until_unsafe" if self.layout == "single" else "stable_split",
            "identity_confidence": round(
                float(np.mean(self.identity_confidence_samples)) if self.identity_confidence_samples else 1.0,
                4,
            ),
            "confirmed_track_frames": self.confirmed_track_frames,
            "grace_hold_frames": self.grace_hold_frames,
            "controlled_return_frames": self.controlled_return_frames,
            "reacquire_attempt_count": self.reacquire_attempt_count,
            "reacquire_success_count": self.reacquire_success_count,
            "active_track_id_switches": self.active_track_id_switches,
            "shot_cut_resets": self.shot_cut_resets,
            "max_track_lost_streak": self.max_track_lost_streak,
        }

    @staticmethod
    def merge(
        diag_a: "TrackingDiagnostics",
        diag_b: "TrackingDiagnostics",
        *,
        panel_swap_count: int = 0,
    ) -> dict:
        quality_a = diag_a.to_quality()
        quality_b = diag_b.to_quality()
        total_frames = int(quality_a.get("total_frames", 0)) + int(quality_b.get("total_frames", 0))
        avg_center_jump = (
            float(quality_a.get("avg_center_jump_px", 0.0) or 0.0)
            + float(quality_b.get("avg_center_jump_px", 0.0) or 0.0)
        ) / 2.0
        status_order = {"good": 0, "degraded": 1, "fallback": 2}
        merged_status = max(
            str(quality_a.get("status", "good")),
            str(quality_b.get("status", "good")),
            key=lambda value: status_order.get(value, 0),
        )
        primary_p95 = float(quality_a.get("p95_center_jump_px", 0.0) or 0.0)
        secondary_p95 = float(quality_b.get("p95_center_jump_px", 0.0) or 0.0)
        startup_settle_ms = max(
            float(quality_a.get("startup_settle_ms", 0.0) or 0.0),
            float(quality_b.get("startup_settle_ms", 0.0) or 0.0),
        )
        if panel_swap_count > 0 or primary_p95 > SPLIT_JITTER_DEGRADED_THRESHOLD_PX or secondary_p95 > SPLIT_JITTER_DEGRADED_THRESHOLD_PX or startup_settle_ms > STARTUP_SETTLE_DEGRADED_MS:
            merged_status = max(merged_status, "degraded", key=lambda value: status_order.get(value, 0))
        return {
            "status": merged_status,
            "mode": "tracked",
            "total_frames": total_frames,
            "fallback_frames": int(quality_a.get("fallback_frames", 0)) + int(quality_b.get("fallback_frames", 0)),
            "avg_center_jump_px": round(avg_center_jump, 3),
            "primary_p95_center_jump_px": round(primary_p95, 3),
            "secondary_p95_center_jump_px": round(secondary_p95, 3),
            "startup_settle_ms": round(startup_settle_ms, 3),
            "panel_swap_count": int(panel_swap_count),
            "predict_fallback_active": bool(quality_a.get("predict_fallback_active")) or bool(quality_b.get("predict_fallback_active")),
            "split_motion_policy": "stable",
            "speaker_lock_policy": "hold_until_unsafe",
            "identity_confidence": round(
                (
                    float(quality_a.get("identity_confidence", 1.0) or 1.0)
                    + float(quality_b.get("identity_confidence", 1.0) or 1.0)
                ) / 2.0,
                4,
            ),
            "confirmed_track_frames": int(quality_a.get("confirmed_track_frames", 0)) + int(quality_b.get("confirmed_track_frames", 0)),
            "grace_hold_frames": int(quality_a.get("grace_hold_frames", 0)) + int(quality_b.get("grace_hold_frames", 0)),
            "controlled_return_frames": int(quality_a.get("controlled_return_frames", 0)) + int(quality_b.get("controlled_return_frames", 0)),
            "reacquire_attempt_count": int(quality_a.get("reacquire_attempt_count", 0)) + int(quality_b.get("reacquire_attempt_count", 0)),
            "reacquire_success_count": int(quality_a.get("reacquire_success_count", 0)) + int(quality_b.get("reacquire_success_count", 0)),
            "active_track_id_switches": int(quality_a.get("active_track_id_switches", 0)) + int(quality_b.get("active_track_id_switches", 0)),
            "shot_cut_resets": max(int(quality_a.get("shot_cut_resets", 0)), int(quality_b.get("shot_cut_resets", 0))),
            "max_track_lost_streak": max(int(quality_a.get("max_track_lost_streak", 0)), int(quality_b.get("max_track_lost_streak", 0))),
        }

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        return float(np.percentile(np.asarray(values, dtype=np.float32), percentile))

    @staticmethod
    def _compute_startup_settle_ms(jump_samples: list[float], fps: float) -> float:
        if not jump_samples or fps <= 0:
            return 0.0
        startup_window_frames = min(len(jump_samples), max(1, int(round(fps * 0.5))))
        significant_frames = [
            frame_index + 1
            for frame_index, jump in enumerate(jump_samples[:startup_window_frames])
            if jump > STARTUP_SETTLE_JUMP_THRESHOLD_PX
        ]
        if not significant_frames:
            return 0.0
        return (max(significant_frames) / fps) * 1000.0


logger.add(
    str(LOGS_DIR / "video_processor_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)


class VideoProcessor:
    @staticmethod
    def _compute_ffmpeg_timeout(
        duration: float,
        *,
        start_time: float = 0.0,
        minimum: int = 300,
        maximum: int = 1800,
    ) -> int:
        safe_duration = max(1.0, float(duration))
        safe_start = max(0.0, float(start_time))
        estimated = int(180 + (safe_duration * 8.0) + (safe_start * 0.15))
        return max(minimum, min(maximum, estimated))

    @staticmethod
    def _run_command_with_cancel(
        cmd: list[str],
        *,
        timeout: float,
        cancel_event: threading.Event | None = None,
        text: bool = True,
    ) -> subprocess.CompletedProcess:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
        start = time.time()
        while True:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.communicate()
                raise RuntimeError("Job cancelled by user")
            rc = proc.poll()
            if rc is not None:
                stdout, stderr = proc.communicate()
                return subprocess.CompletedProcess(cmd, rc, stdout, stderr)
            if time.time() - start > timeout:
                proc.kill()
                proc.communicate()
                raise RuntimeError(f"FFmpeg islemi timeout oldu ({int(timeout)} sn)")
            time.sleep(0.5)

    def __init__(self, model_version: str | None = None, device: str = "cuda"):
        self._model_path = model_version or str(YOLO_MODEL_PATH)
        self._device = device
        self.model: YOLO | None = None
        self._tracker_available = True
        logger.info("🎥 Video Processor hazirlandi (YOLO lazy-load, cihaz: {}).", device.upper())

    def _ensure_model_loaded(self) -> None:
        if self.model is not None:
            return

        logger.info("🔄 YOLO modeli yukleniyor: {}", self._model_path)
        self.model = YOLO(self._model_path)
        if self._device == "cuda" and not torch.cuda.is_available():
            if os.getenv("REQUIRE_CUDA_FOR_APP", "").strip().lower() in {"1", "true", "yes", "on"}:
                raise RuntimeError("CUDA zorunlu ama torch.cuda kullanilabilir degil")
            logger.warning("⚠️ CUDA istendi ama GPU yok. CPU'ya geciliyor.")
            self._device = "cpu"
        self.model.to(self._device)
        logger.success("✅ YOLO modeli {} uzerine yuklendi.", self._device.upper())

    def unload_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if self._device == "cuda":
                torch.cuda.empty_cache()
            logger.info("♻️ YOLO modeli VRAM'den bosaltildi.")

    def cleanup_gpu(self) -> None:
        self.unload_model()
        gc.collect()
        if self._device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("🧹 VideoProcessor GPU cleanup tamamlandi.")

    def _prefer_nvenc(self) -> bool:
        return self._device == "cuda" and torch.cuda.is_available()

    @staticmethod
    def _build_h264_encoder_args(*, prefer_nvenc: bool) -> list[str]:
        if prefer_nvenc:
            return [
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p6",
                "-b:v",
                "8M",
            ]
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
        ]

    def _tracking_stride(self) -> int:
        return CPU_TRACKING_STRIDE if self._device != "cuda" or not self._tracker_available else 1

    def _build_segment_cut_command(
        self,
        *,
        input_video: str,
        start_time: float,
        duration: float,
        source_fps: float,
        output_filename: str,
        has_audio: bool,
        prefer_nvenc: bool,
    ) -> list[str]:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-i",
            input_video,
            "-t",
            str(duration),
            "-vsync",
            "cfr",
            "-r",
            f"{source_fps:.6f}",
            *self._build_h264_encoder_args(prefer_nvenc=prefer_nvenc),
        ]
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.append("-an")
        cmd.append(output_filename)
        return cmd

    def _extract_probe_frame(self, input_video: str, sample_time: float) -> np.ndarray | None:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{sample_time:.3f}",
            "-i",
            input_video,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ]
        completed = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=20,
        )
        if completed.returncode != 0 or not completed.stdout:
            return None
        frame_buffer = np.frombuffer(completed.stdout, dtype=np.uint8)
        if frame_buffer.size == 0:
            return None
        frame = cv2.imdecode(frame_buffer, cv2.IMREAD_COLOR)
        if frame is None or frame.size == 0:
            return None
        return frame

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    @staticmethod
    def _compute_crop_bounds(center_x: float, crop_width: int, frame_width: int) -> tuple[int, int]:
        x1 = int(center_x - crop_width / 2)
        max_x1 = max(0, frame_width - crop_width)
        x1 = min(max(0, x1), max_x1)
        x2 = x1 + crop_width
        return x1, x2

    @staticmethod
    def _resize_for_detection(frame: np.ndarray) -> tuple[np.ndarray, float, float]:
        frame_height, frame_width = frame.shape[:2]
        long_edge = max(frame_width, frame_height)
        if long_edge <= DETECTION_LONG_EDGE:
            return frame, 1.0, 1.0
        scale = DETECTION_LONG_EDGE / long_edge
        resized = cv2.resize(frame, (int(round(frame_width * scale)), int(round(frame_height * scale))))
        return resized, frame_width / resized.shape[1], frame_height / resized.shape[0]

    @staticmethod
    def _compute_visibility_score(
        box: tuple[float, float, float, float],
        *,
        frame_width: int,
        frame_height: int,
    ) -> float:
        x1, y1, x2, y2 = box
        width = max(1.0, x2 - x1)
        height = max(1.0, y2 - y1)
        height_ratio = height / max(frame_height, 1)
        width_ratio = width / max(frame_width, 1)
        clipped_penalty = 0.0
        if x1 <= 2 or x2 >= frame_width - 2:
            clipped_penalty += 0.15
        if y1 <= 2 or y2 >= frame_height - 2:
            clipped_penalty += 0.15
        size_score = _clamp01((height_ratio * 0.8) + (width_ratio * 0.2))
        return _clamp01(size_score - clipped_penalty)

    @staticmethod
    def _candidate_identity_confidence(
        candidate: DetectionCandidate,
        state: TrackSlotState,
    ) -> float:
        track_score = 1.0
        if state.confirmed_track_id is not None and candidate.track_id is not None:
            track_score = 1.0 if candidate.track_id == state.confirmed_track_id else 0.0
        elif state.confirmed_track_id is not None or candidate.track_id is not None:
            track_score = 0.5

        area_score = 1.0
        if state.last_confirmed_area is not None:
            area_score = 1.0 - _clamp01(abs(candidate.area - state.last_confirmed_area) / max(state.last_confirmed_area, 1.0))

        aspect_score = 1.0
        if state.last_confirmed_aspect_ratio is not None:
            aspect_score = 1.0 - _clamp01(
                abs(candidate.aspect_ratio - state.last_confirmed_aspect_ratio) / max(state.last_confirmed_aspect_ratio, 0.01)
            )

        visibility_score = 1.0
        if state.last_visibility_score is not None:
            visibility_score = 1.0 - _clamp01(abs(candidate.visibility_score - state.last_visibility_score))

        return _clamp01(
            (0.40 * track_score)
            + (0.25 * area_score)
            + (0.15 * aspect_score)
            + (0.20 * visibility_score)
        )

    @staticmethod
    def _split_crop_margin_ratio(
        candidate: DetectionCandidate,
        *,
        frame_width: int,
        crop_width: int,
    ) -> float:
        crop_x1, crop_x2 = VideoProcessor._compute_crop_bounds(candidate.center_x, crop_width, frame_width)
        left_margin = max(0.0, candidate.box[0] - crop_x1)
        right_margin = max(0.0, crop_x2 - candidate.box[2])
        return min(left_margin, right_margin) / max(float(crop_width), 1.0)

    @staticmethod
    def _compute_motion_scores(
        current_frame: np.ndarray,
        previous_frame: np.ndarray | None,
        box: tuple[float, float, float, float],
    ) -> tuple[float, float]:
        if previous_frame is None:
            return 0.0, 0.0

        frame_height, frame_width = current_frame.shape[:2]
        x1, y1, x2, y2 = [int(round(value)) for value in box]
        x1 = max(0, min(frame_width - 1, x1))
        x2 = max(x1 + 1, min(frame_width, x2))
        y1 = max(0, min(frame_height - 1, y1))
        y2 = max(y1 + 1, min(frame_height, y2))

        current_crop = current_frame[y1:y2, x1:x2]
        previous_crop = previous_frame[y1:y2, x1:x2]
        if current_crop.size == 0 or previous_crop.size == 0:
            return 0.0, 0.0

        current_gray = cv2.cvtColor(current_crop, cv2.COLOR_BGR2GRAY)
        previous_gray = cv2.cvtColor(previous_crop, cv2.COLOR_BGR2GRAY)
        body_diff = float(np.mean(cv2.absdiff(current_gray, previous_gray)) / 255.0)

        crop_height, crop_width = current_gray.shape[:2]
        mouth_y1 = int(round(crop_height * 0.42))
        mouth_y2 = int(round(crop_height * 0.78))
        mouth_x1 = int(round(crop_width * 0.18))
        mouth_x2 = int(round(crop_width * 0.82))
        current_mouth = current_gray[mouth_y1:mouth_y2, mouth_x1:mouth_x2]
        previous_mouth = previous_gray[mouth_y1:mouth_y2, mouth_x1:mouth_x2]
        if current_mouth.size == 0 or previous_mouth.size == 0:
            mouth_diff = 0.0
        else:
            mouth_diff = float(np.mean(cv2.absdiff(current_mouth, previous_mouth)) / 255.0)

        return _clamp01(body_diff * 6.0), _clamp01(mouth_diff * 10.0)

    def _track_people(self, frame: np.ndarray, previous_frame: np.ndarray | None = None) -> list[DetectionCandidate]:
        if self.model is None:
            return []
        frame_height, frame_width = frame.shape[:2]
        resized, scale_x, scale_y = self._resize_for_detection(frame)
        if not self._tracker_available:
            return self._predict_people(frame)
        try:
            results = self.model.track(
                resized,
                persist=True,
                tracker=TRACKER_CONFIG,
                classes=[0],
                verbose=False,
                conf=MIN_DETECTION_CONFIDENCE,
            )
        except ModuleNotFoundError as exc:
            if exc.name == "lap":
                logger.warning("Ultralytics tracker bagimliligi eksik (lap). predict fallback kullanilacak.")
                self._tracker_available = False
                return self._predict_people(frame)
            raise
        det_boxes = results[0].boxes
        if det_boxes is None or len(det_boxes) == 0:
            return []

        xyxy = det_boxes.xyxy.cpu().numpy()  # type: ignore[reportAttributeAccessIssue]
        confs = det_boxes.conf.cpu().numpy() if det_boxes.conf is not None else np.ones(len(xyxy))  # type: ignore[reportAttributeAccessIssue]
        ids = det_boxes.id.cpu().numpy() if det_boxes.id is not None else np.full(len(xyxy), np.nan)  # type: ignore[reportAttributeAccessIssue]
        candidates: list[DetectionCandidate] = []
        for index, box in enumerate(xyxy):
            confidence = float(confs[index])
            if confidence < MIN_DETECTION_CONFIDENCE:
                continue
            x1 = float(box[0]) * scale_x
            y1 = float(box[1]) * scale_y
            x2 = float(box[2]) * scale_x
            y2 = float(box[3]) * scale_y
            width = max(1.0, x2 - x1)
            height = max(1.0, y2 - y1)
            track_id = None if np.isnan(ids[index]) else int(ids[index])
            visibility_score = self._compute_visibility_score((x1, y1, x2, y2), frame_width=frame_width, frame_height=frame_height)
            motion_score, mouth_motion_score = self._compute_motion_scores(frame, previous_frame, (x1, y1, x2, y2))
            candidates.append(
                DetectionCandidate(
                    track_id=track_id,
                    box=(x1, y1, x2, y2),
                    center_x=(x1 + x2) / 2.0,
                    area=width * height,
                    confidence=confidence,
                    aspect_ratio=width / height,
                    visibility_score=visibility_score,
                    motion_score=motion_score,
                    mouth_motion_score=mouth_motion_score,
                )
            )
        return candidates

    def _predict_people(self, frame: np.ndarray) -> list[DetectionCandidate]:
        if self.model is None:
            return []
        frame_height, frame_width = frame.shape[:2]
        resized, scale_x, scale_y = self._resize_for_detection(frame)
        results = self.model.predict(
            resized,
            classes=[0],
            verbose=False,
            conf=MIN_DETECTION_CONFIDENCE,
        )
        det_boxes = results[0].boxes
        if det_boxes is None or len(det_boxes) == 0:
            return []
        xyxy = det_boxes.xyxy.cpu().numpy()  # type: ignore[reportAttributeAccessIssue]
        confs = det_boxes.conf.cpu().numpy() if det_boxes.conf is not None else np.ones(len(xyxy))  # type: ignore[reportAttributeAccessIssue]
        candidates: list[DetectionCandidate] = []
        for index, box in enumerate(xyxy):
            confidence = float(confs[index])
            if confidence < MIN_DETECTION_CONFIDENCE:
                continue
            x1 = float(box[0]) * scale_x
            y1 = float(box[1]) * scale_y
            x2 = float(box[2]) * scale_x
            y2 = float(box[3]) * scale_y
            width = max(1.0, x2 - x1)
            height = max(1.0, y2 - y1)
            visibility_score = self._compute_visibility_score((x1, y1, x2, y2), frame_width=frame_width, frame_height=frame_height)
            candidates.append(
                DetectionCandidate(
                    track_id=index,
                    box=(x1, y1, x2, y2),
                    center_x=(x1 + x2) / 2.0,
                    area=width * height,
                    confidence=confidence,
                    aspect_ratio=width / height,
                    visibility_score=visibility_score,
                )
            )
        return candidates

    @staticmethod
    def _compute_cut_confidence(previous_frame: np.ndarray | None, current_frame: np.ndarray) -> tuple[float, float, float]:
        if previous_frame is None:
            return 0.0, 1.0, 0.0
        prev_small = cv2.resize(previous_frame, (96, 54))
        curr_small = cv2.resize(current_frame, (96, 54))
        prev_hsv = cv2.cvtColor(prev_small, cv2.COLOR_BGR2HSV)
        curr_hsv = cv2.cvtColor(curr_small, cv2.COLOR_BGR2HSV)
        prev_hist = cv2.calcHist([prev_hsv], [0, 1], None, [12, 12], [0, 180, 0, 256])
        curr_hist = cv2.calcHist([curr_hsv], [0, 1], None, [12, 12], [0, 180, 0, 256])
        cv2.normalize(prev_hist, prev_hist)
        cv2.normalize(curr_hist, curr_hist)
        hist_corr = float(cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL))

        prev_gray = cv2.cvtColor(prev_small, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_small, cv2.COLOR_BGR2GRAY)
        luma_diff = float(np.mean(np.abs(prev_gray.astype(np.float32) - curr_gray.astype(np.float32))) / 255.0)

        hist_cut_confidence = _clamp01((0.70 - hist_corr) / 0.40)
        luminance_cut_confidence = _clamp01((luma_diff - 0.12) / 0.28)
        return max(hist_cut_confidence, luminance_cut_confidence), hist_corr, luma_diff

    def _compute_candidate_score(
        self,
        candidate: DetectionCandidate,
        state: TrackSlotState,
        *,
        frame_width: int,
        frame_height: int,
    ) -> float:
        frame_area = max(1.0, float(frame_width * frame_height))
        normalized_area = _clamp01(candidate.area / (frame_area * 0.35))
        confidence = _clamp01(candidate.confidence)

        if state.last_confirmed_center is None:
            center_distance_penalty = abs(candidate.center_x - (frame_width / 2.0)) / max(frame_width / 2.0, 1.0)
        else:
            center_distance_penalty = abs(candidate.center_x - state.last_confirmed_center) / max(frame_width / 2.0, 1.0)
        center_distance_penalty = _clamp01(center_distance_penalty)

        if state.last_confirmed_aspect_ratio is None:
            aspect_ratio_penalty = 0.0
        else:
            aspect_ratio_penalty = _clamp01(
                abs(candidate.aspect_ratio - state.last_confirmed_aspect_ratio) / max(state.last_confirmed_aspect_ratio, 0.01)
            )

        continuity = 0.0
        if state.last_confirmed_box is not None:
            iou = _box_iou(candidate.box, state.last_confirmed_box)
            center_proximity = 1.0 - center_distance_penalty
            if state.last_confirmed_area is None:
                scale_proximity = 0.5
            else:
                scale_proximity = 1.0 - _clamp01(abs(candidate.area - state.last_confirmed_area) / max(state.last_confirmed_area, 1.0))
            continuity = _clamp01((iou * 0.55) + (center_proximity * 0.30) + (scale_proximity * 0.15))
            continuity *= state.continuity_multiplier

        score = (
            (0.45 * _clamp01(continuity))
            + (0.25 * normalized_area)
            + (0.15 * confidence)
            + (0.08 * _clamp01(candidate.visibility_score))
            + (0.12 * _clamp01((candidate.motion_score * 0.4) + (candidate.mouth_motion_score * 0.6)))
            - (0.10 * center_distance_penalty)
            - (0.05 * aspect_ratio_penalty)
        )
        return _clamp01(score)

    def _confirm_candidate(
        self,
        state: TrackSlotState,
        diagnostics: TrackingDiagnostics,
        candidate: DetectionCandidate,
        *,
        switched: bool,
    ) -> float:
        if switched:
            diagnostics.active_track_id_switches += 1
        identity_confidence = self._candidate_identity_confidence(candidate, state)
        state.confirmed_track_id = candidate.track_id
        state.last_confirmed_box = candidate.box
        state.last_confirmed_center = candidate.center_x
        state.last_confirmed_area = candidate.area
        state.last_confirmed_aspect_ratio = candidate.aspect_ratio
        state.last_visibility_score = candidate.visibility_score
        state.last_identity_confidence = identity_confidence
        state.grace_remaining = 0
        state.controlled_return_frames_remaining = 0
        state.reacquire_counts.clear()
        state.lost_streak = 0
        state.last_mode = "tracked"
        diagnostics.register_identity_confidence(identity_confidence)
        return candidate.center_x

    @staticmethod
    def _move_towards(current: float, target: float, *, max_step_px: float, ema_alpha: float) -> float:
        delta = float(target) - float(current)
        if abs(delta) <= 0.001:
            return float(current)
        proposed_step = delta * float(ema_alpha)
        clamped_step = float(np.clip(proposed_step, -max_step_px, max_step_px))
        return float(current + clamped_step)

    @staticmethod
    def _movement_profile(
        *,
        layout: str,
        mode: str,
        frame_width: int,
        tracker_weak: bool,
    ) -> tuple[float, float, float, int]:
        if layout == "split":
            if mode == "controlled_return":
                return (
                    frame_width * SPLIT_DEADZONE_RATIO,
                    frame_width * SPLIT_CONTROLLED_RETURN_PAN_RATIO,
                    SPLIT_EMA_ALPHA,
                    1,
                )
            deadzone_ratio = SPLIT_FALLBACK_DEADZONE_RATIO if tracker_weak else SPLIT_DEADZONE_RATIO
            sustained_frames = SPLIT_FALLBACK_SUSTAINED_FRAMES if tracker_weak else SPLIT_SUSTAINED_MOVEMENT_FRAMES
            return (
                frame_width * deadzone_ratio,
                frame_width * SPLIT_MAX_STEP_RATIO,
                SPLIT_EMA_ALPHA,
                sustained_frames,
            )
        return (
            frame_width * SINGLE_DEADZONE_RATIO,
            frame_width * SINGLE_MAX_STEP_RATIO,
            SINGLE_EMA_ALPHA,
            1,
        )

    def _stabilize_tracking_center(
        self,
        *,
        state: TrackSlotState,
        target_cx: float,
        frame_width: int,
        layout: str,
        mode: str,
        tracker_weak: bool,
        crop_width: int | None = None,
    ) -> tuple[float, bool, bool, int]:
        deadzone_px, max_step_px, ema_alpha, sustained_required = self._movement_profile(
            layout=layout,
            mode=mode,
            frame_width=frame_width,
            tracker_weak=tracker_weak,
        )
        delta = float(target_cx) - float(state.current_cx)
        if layout == "single" and mode == "tracked":
            effective_crop_width = max(1, int(crop_width or frame_width))
            safe_band_px = max(
                frame_width * SINGLE_DEADZONE_RATIO,
                (effective_crop_width * SINGLE_LOCK_SAFE_BAND_RATIO) / 2.0,
            )
            if abs(delta) <= safe_band_px:
                state.unsafe_reframe_streak = 0
                state.sustained_movement_frames = 0
                return float(state.current_cx), True, True, 0
            state.unsafe_reframe_streak += 1
            if state.unsafe_reframe_streak < SINGLE_REFRAME_SUSTAINED_FRAMES:
                return float(state.current_cx), True, False, state.unsafe_reframe_streak
        else:
            state.unsafe_reframe_streak = 0
        deadzone_hit = abs(delta) <= deadzone_px
        if deadzone_hit:
            state.sustained_movement_frames = 0
            return float(state.current_cx), True, True, 0

        if layout == "split" and mode != "controlled_return":
            state.sustained_movement_frames += 1
            if state.sustained_movement_frames < sustained_required:
                return float(state.current_cx), True, False, state.sustained_movement_frames
        else:
            state.sustained_movement_frames = 0

        next_center = self._move_towards(
            state.current_cx,
            target_cx,
            max_step_px=max_step_px,
            ema_alpha=ema_alpha,
        )
        if abs(next_center - state.current_cx) < 0.25:
            next_center = float(state.current_cx)
        return next_center, False, False, state.sustained_movement_frames

    def _process_tracking_slot(
        self,
        *,
        state: TrackSlotState,
        candidates: list[DetectionCandidate],
        frame_width: int,
        frame_height: int,
        panel_center: float,
        diagnostics: TrackingDiagnostics,
        layout: str,
        frame_index: int,
        cut_confidence: float,
        crop_width: int | None = None,
    ) -> float:
        best_candidate: DetectionCandidate | None = None
        best_score = -1.0
        for candidate in candidates:
            score = self._compute_candidate_score(candidate, state, frame_width=frame_width, frame_height=frame_height)
            if score > best_score:
                best_candidate = candidate
                best_score = score

        same_id_candidate = None
        if state.confirmed_track_id is not None:
            same_id_candidate = next((cand for cand in candidates if cand.track_id == state.confirmed_track_id), None)

        target_cx = state.current_cx
        mode = "fallback"

        if same_id_candidate is not None:
            same_id_score = self._compute_candidate_score(
                same_id_candidate,
                state,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            if same_id_score >= MIN_TRACK_ACCEPT_SCORE:
                target_cx = self._confirm_candidate(state, diagnostics, same_id_candidate, switched=False)
                mode = "tracked"

        if mode != "tracked" and state.last_confirmed_box is not None:
            state.lost_streak += 1
            diagnostics.max_track_lost_streak = max(diagnostics.max_track_lost_streak, state.lost_streak)
            if state.grace_remaining == 0 and state.controlled_return_frames_remaining == 0:
                state.grace_remaining = MISSING_TRACK_GRACE_FRAMES

            reacquired = False
            if same_id_candidate is not None:
                center_delta = abs(same_id_candidate.center_x - (state.last_confirmed_center or same_id_candidate.center_x))
                iou = _box_iou(same_id_candidate.box, state.last_confirmed_box)
                diagnostics.reacquire_attempt_count += 1
                if iou >= 0.25 or center_delta <= frame_width * SAME_ID_REACQUIRE_CENTER_RATIO:
                    diagnostics.reacquire_success_count += 1
                    target_cx = self._confirm_candidate(state, diagnostics, same_id_candidate, switched=False)
                    reacquired = True
                    mode = "tracked"

            if not reacquired:
                for candidate in candidates:
                    if candidate.track_id is None or candidate.track_id == state.confirmed_track_id:
                        continue
                    center_delta = abs(candidate.center_x - (state.last_confirmed_center or candidate.center_x))
                    if center_delta > frame_width * DIFF_ID_REACQUIRE_CENTER_RATIO:
                        continue
                    if state.last_confirmed_area is None:
                        continue
                    area_ratio = candidate.area / max(state.last_confirmed_area, 1.0)
                    if not (0.7 <= area_ratio <= 1.4):
                        continue
                    diagnostics.reacquire_attempt_count += 1
                    state.reacquire_counts[candidate.track_id] = state.reacquire_counts.get(candidate.track_id, 0) + 1
                    if state.reacquire_counts[candidate.track_id] >= REACQUIRE_CONFIRMATION_FRAMES:
                        candidate_score = self._compute_candidate_score(
                            candidate,
                            state,
                            frame_width=frame_width,
                            frame_height=frame_height,
                        )
                        if candidate_score >= MIN_TRACK_ACCEPT_SCORE:
                            diagnostics.reacquire_success_count += 1
                            target_cx = self._confirm_candidate(state, diagnostics, candidate, switched=True)
                            reacquired = True
                            mode = "tracked"
                            break

            if not reacquired:
                if state.grace_remaining > 0:
                    state.grace_remaining -= 1
                    target_cx = state.last_confirmed_center if state.last_confirmed_center is not None else state.current_cx
                    mode = "grace"
                else:
                    state.confirmed_track_id = None
                    state.controlled_return_frames_remaining = max(state.controlled_return_frames_remaining, CONTROLLED_RETURN_FRAMES)
                    target_cx = panel_center
                    state.controlled_return_frames_remaining = max(0, state.controlled_return_frames_remaining - 1)
                    mode = "controlled_return"

        if mode == "fallback" and best_candidate is not None and best_score >= MIN_TRACK_ACCEPT_SCORE:
            target_cx = self._confirm_candidate(
                state,
                diagnostics,
                best_candidate,
                switched=state.last_confirmed_center is not None and best_candidate.track_id != state.confirmed_track_id,
            )
            mode = "tracked"

        previous_cx = state.current_cx
        tracker_weak = self._device != "cuda" or not self._tracker_available
        state.current_cx, movement_suppressed, deadzone_hit, sustained_frames = self._stabilize_tracking_center(
            state=state,
            target_cx=target_cx,
            frame_width=frame_width,
            crop_width=crop_width,
            layout=layout,
            mode=mode,
            tracker_weak=tracker_weak,
        )
        diagnostics.register_center_jump(abs(state.current_cx - previous_cx))
        diagnostics.register_mode(mode)
        state.last_mode = mode
        if os.getenv("DEBUG_RENDER_ARTIFACTS") == "1":
            diagnostics.timeline.append(
                {
                    "frame": frame_index,
                    "slot": state.label,
                    "mode": mode,
                    "track_id": state.confirmed_track_id,
                    "center_x": round(state.current_cx, 3),
                    "target_center_x": round(float(target_cx), 3),
                    "cut_confidence": round(cut_confidence, 4),
                    "candidate_count": len(candidates),
                    "movement_suppressed": bool(movement_suppressed),
                    "deadzone_hit": bool(deadzone_hit),
                    "sustained_frames": int(sustained_frames),
                }
            )
        return state.current_cx

    @staticmethod
    def _build_tracking_debug(diagnostics: TrackingDiagnostics) -> dict | None:
        if os.getenv("DEBUG_RENDER_ARTIFACTS") != "1":
            return None
        quality_summary = diagnostics.to_quality()
        return {
            "timeline": diagnostics.timeline,
            "summary": {
                "avg_center_jump_px": quality_summary.get("avg_center_jump_px", 0.0),
                "p95_center_jump_px": quality_summary.get("p95_center_jump_px", 0.0),
                "startup_settle_ms": quality_summary.get("startup_settle_ms", 0.0),
                "predict_fallback_active": quality_summary.get("predict_fallback_active", False),
            },
        }

    @staticmethod
    def _debug_artifacts_enabled() -> bool:
        return os.getenv("DEBUG_RENDER_ARTIFACTS") == "1"

    @staticmethod
    def _create_overlay_writer(path: str, fps: float, size: tuple[int, int]) -> cv2.VideoWriter | None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, max(1.0, float(fps or 1.0)), size)
        if not writer.isOpened():
            writer.release()
            return None
        return writer

    @staticmethod
    def _scale_debug_frame(frame: np.ndarray) -> np.ndarray:
        frame_height, frame_width = frame.shape[:2]
        long_edge = max(frame_width, frame_height)
        if long_edge <= DETECTION_LONG_EDGE:
            return frame
        scale = DETECTION_LONG_EDGE / long_edge
        return cv2.resize(frame, (int(round(frame_width * scale)), int(round(frame_height * scale))))

    def _draw_debug_overlay(
        self,
        *,
        frame: np.ndarray,
        candidates: list[DetectionCandidate],
        crop_bounds: list[tuple[str, tuple[int, int], tuple[int, int, int]]],
        primary_slot: TrackSlotState,
        secondary_slot: TrackSlotState | None,
        frame_index: int,
        cut_confidence: float,
        layout: str,
    ) -> np.ndarray:
        annotated = frame.copy()
        track_colors: dict[int | None, tuple[int, int, int]] = {
            primary_slot.confirmed_track_id: (80, 220, 120),
        }
        if secondary_slot is not None:
            track_colors[secondary_slot.confirmed_track_id] = (255, 200, 80)

        for candidate in candidates:
            x1, y1, x2, y2 = [int(round(value)) for value in candidate.box]
            color = track_colors.get(candidate.track_id, (180, 180, 180))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"id={candidate.track_id if candidate.track_id is not None else 'na'} conf={candidate.confidence:.2f}"
            cv2.putText(
                annotated,
                f"{label} act={candidate.mouth_motion_score:.2f}",
                (x1, max(18, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

        for slot_label, (x1, x2), color in crop_bounds:
            cv2.rectangle(annotated, (x1, 0), (x2, annotated.shape[0] - 1), color, 2)
            cv2.putText(
                annotated,
                slot_label.upper(),
                (x1 + 8, 26 if slot_label == "primary" else 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )

        cv2.putText(
            annotated,
            f"frame={frame_index} layout={layout} cut={cut_confidence:.2f} mode={primary_slot.last_mode}",
            (18, annotated.shape[0] - 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return self._scale_debug_frame(annotated)

    @staticmethod
    def _build_debug_timing(
        *,
        source_metrics: dict,
        normalized_metrics: dict,
        rendered_metrics: dict,
        merged_metrics: dict,
    ) -> dict:
        normalized_fps = normalized_metrics.get("fps") or rendered_metrics.get("fps") or source_metrics.get("fps") or 30.0
        expected_frames = (rendered_metrics.get("duration") or 0.0) * normalized_fps
        actual_frames = rendered_metrics.get("nb_frames") or merged_metrics.get("nb_frames") or 0
        dropped_or_duplicated = abs(float(actual_frames or 0) - float(expected_frames)) if actual_frames else 0.0

        merged_video_duration = float(merged_metrics.get("video_duration") or merged_metrics.get("duration") or 0.0)
        merged_audio_duration = float(merged_metrics.get("audio_duration") or 0.0)
        drift_ms = abs(merged_video_duration - merged_audio_duration) * 1000 if merged_metrics.get("has_audio") else 0.0

        return {
            "source_fps": round(float(source_metrics.get("fps") or 0.0), 4),
            "normalized_fps": round(float(normalized_fps or 0.0), 4),
            "source_duration": round(float(source_metrics.get("duration") or 0.0), 4),
            "normalized_video_duration": round(float(rendered_metrics.get("duration") or 0.0), 4),
            "normalized_audio_duration": round(float(normalized_metrics.get("audio_duration") or 0.0), 4),
            "merged_output_duration": round(float(merged_metrics.get("duration") or 0.0), 4),
            "merged_output_drift_ms": round(drift_ms, 3),
            "dropped_or_duplicated_frame_estimate": round(dropped_or_duplicated, 3),
            "has_audio": bool(merged_metrics.get("has_audio")),
            "audio_sample_rate": merged_metrics.get("audio_sample_rate"),
            "audio_channels": merged_metrics.get("audio_channels"),
        }

    def create_viral_short(
        self,
        input_video: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        smoothness: float = 0.1,
        manual_center_x: float | None = None,
        layout: str = "single",
        initial_slot_centers: tuple[float, float] | None = None,
        cancel_event: threading.Event | None = None,
        require_audio: bool = False,
    ) -> dict:
        logger.info("✂️ Klip: {} - {} sn (Layout: {}) → {}", start_time, end_time, layout, output_filename)
        if manual_center_x is None:
            self._ensure_model_loaded()

        duration = end_time - start_time
        source_probe = probe_media(input_video)
        source_metrics = extract_media_stream_metrics(source_probe)
        if require_audio and not source_metrics["has_audio"]:
            raise RuntimeError("Audio stream required for this render but source video has no audio")

        source_fps = float(source_metrics.get("fps") or 30.0)
        if source_fps <= 0:
            source_fps = 30.0
        prefer_nvenc = self._prefer_nvenc()

        job_uuid = uuid.uuid4().hex[:8]
        temp_cut = str(TEMP_DIR / f"cut_{job_uuid}.mp4")
        temp_video_only = str(TEMP_DIR / f"vonly_{job_uuid}.mp4")
        debug_overlay_temp = str(TEMP_DIR / f"overlay_{job_uuid}.mp4")
        debug_overlay_ready = False

        cut_timeout = self._compute_ffmpeg_timeout(duration, start_time=start_time, minimum=300)
        try:
            cut_cmd = self._build_segment_cut_command(
                input_video=input_video,
                start_time=start_time,
                duration=duration,
                source_fps=source_fps,
                output_filename=temp_cut,
                has_audio=bool(source_metrics["has_audio"]),
                prefer_nvenc=prefer_nvenc,
            )
            result = self._run_command_with_cancel(
                cut_cmd,
                timeout=cut_timeout,
                cancel_event=cancel_event,
            )
            if result.returncode != 0 and prefer_nvenc and _is_nvenc_error(result.stderr or ""):
                prefer_nvenc = False
                cut_cmd = self._build_segment_cut_command(
                    input_video=input_video,
                    start_time=start_time,
                    duration=duration,
                    source_fps=source_fps,
                    output_filename=temp_cut,
                    has_audio=bool(source_metrics["has_audio"]),
                    prefer_nvenc=False,
                )
                result = self._run_command_with_cancel(
                    cut_cmd,
                    timeout=cut_timeout,
                    cancel_event=cancel_event,
                )
            if result.returncode != 0:
                raise RuntimeError(f"Video kesilemedi: {(result.stderr or '')[-300:]}")

            cap = cv2.VideoCapture(temp_cut)
            orig_fps = cap.get(cv2.CAP_PROP_FPS) or source_fps or 30.0
            if orig_fps <= 0:
                orig_fps = source_fps or 30.0
            orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            target_w, target_h = LOGICAL_CANVAS_WIDTH, LOGICAL_CANVAS_HEIGHT
            split_panel_h = SPLIT_PANEL_HEIGHT
            split_gutter_h = SPLIT_GUTTER_HEIGHT

            initial_primary_cx = orig_w / 2.0
            initial_secondary_cx = orig_w / 2.0
            if layout == "split" and initial_slot_centers is not None:
                initial_primary_cx = float(initial_slot_centers[0])
                initial_secondary_cx = float(initial_slot_centers[1])
            elif layout == "split":
                initial_primary_cx = orig_w * 0.33
                initial_secondary_cx = orig_w * 0.67

            primary_diagnostics = TrackingDiagnostics(mode="tracked", fps=float(orig_fps), layout=layout)
            secondary_diagnostics = TrackingDiagnostics(mode="tracked", fps=float(orig_fps), layout=layout)
            primary_diagnostics.predict_fallback_active = not self._tracker_available
            secondary_diagnostics.predict_fallback_active = not self._tracker_available
            primary_slot = TrackSlotState("primary", initial_primary_cx)
            secondary_slot = TrackSlotState("secondary", initial_secondary_cx)
            ffmpeg_proc: subprocess.Popen[bytes] | None = None
            debug_writer: cv2.VideoWriter | None = None
            frame_count = 0
            previous_frame: np.ndarray | None = None
            cached_candidates: list[DetectionCandidate] = []
            debug_status = "complete" if self._debug_artifacts_enabled() else None
            split_panel_swap_count = 0
            split_unsafe_frames = 0
            face_edge_violation_frames = 0
            primary_edge_violation_streak = 0
            secondary_edge_violation_streak = 0
            last_confirmed_pair: tuple[int | None, int | None] | None = None

            try:
                ffmpeg_proc = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-y",
                        "-loglevel",
                        "error",
                        "-f",
                        "rawvideo",
                        "-vcodec",
                        "rawvideo",
                        "-s",
                        f"{target_w}x{target_h}",
                        "-pix_fmt",
                        "bgr24",
                        "-r",
                        str(orig_fps),
                        "-i",
                        "-",
                        "-vsync",
                        "cfr",
                        "-r",
                        str(orig_fps),
                        *self._build_h264_encoder_args(prefer_nvenc=prefer_nvenc),
                        "-pix_fmt",
                        "yuv420p",
                        temp_video_only,
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                if ffmpeg_proc.stdin is None:
                    raise RuntimeError("FFmpeg stdin acilamadi!")
                stdin: io.RawIOBase = ffmpeg_proc.stdin  # type: ignore[assignment]

                if layout == "split":
                    src_crop_w = min(orig_w, max(1, int(orig_h * (target_w / split_panel_h))))
                else:
                    src_crop_w = min(orig_w, max(1, int(orig_h * (target_w / target_h))))

                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        ffmpeg_proc.kill()
                        cap.release()
                        raise RuntimeError("Job cancelled by user")
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_count += 1
                    cut_confidence, _hist_corr, _luma_diff = self._compute_cut_confidence(previous_frame, frame)
                    motion_reference = previous_frame
                    previous_frame = frame

                    if cut_confidence >= HARD_CUT_THRESHOLD:
                        for state in (primary_slot, secondary_slot):
                            state.confirmed_track_id = None
                            state.last_confirmed_box = None
                            state.last_confirmed_center = None
                            state.last_confirmed_area = None
                            state.last_confirmed_aspect_ratio = None
                            state.grace_remaining = 0
                            state.reacquire_counts.clear()
                            state.continuity_multiplier = 1.0
                        primary_diagnostics.shot_cut_resets += 1
                        secondary_diagnostics.shot_cut_resets += 1
                    elif cut_confidence >= SOFT_CUT_THRESHOLD:
                        primary_slot.continuity_multiplier = 0.5
                        secondary_slot.continuity_multiplier = 0.5
                    else:
                        primary_slot.continuity_multiplier = 1.0
                        secondary_slot.continuity_multiplier = 1.0

                    if manual_center_x is not None:
                        primary_slot.current_cx = manual_center_x * orig_w
                        secondary_slot.current_cx = primary_slot.current_cx
                        primary_diagnostics.register_mode("tracked")
                        candidates = []
                    else:
                        stride = self._tracking_stride()
                        should_refresh_candidates = (
                            frame_count == 1
                            or not cached_candidates
                            or (frame_count - 1) % stride == 0
                            or cut_confidence >= SOFT_CUT_THRESHOLD
                        )
                        if should_refresh_candidates:
                            cached_candidates = self._track_people(frame, motion_reference)
                        primary_diagnostics.predict_fallback_active = primary_diagnostics.predict_fallback_active or (not self._tracker_available)
                        secondary_diagnostics.predict_fallback_active = secondary_diagnostics.predict_fallback_active or (not self._tracker_available)
                        candidates = list(cached_candidates)
                        candidates = sorted(candidates, key=lambda candidate: candidate.center_x)
                        if layout == "split":
                            if (
                                manual_center_x is None
                                and primary_slot.confirmed_track_id is None
                                and secondary_slot.confirmed_track_id is None
                                and len(candidates) >= 2
                            ):
                                bootstrap_candidates = sorted(candidates[:2], key=lambda candidate: candidate.center_x)
                                self._confirm_candidate(primary_slot, primary_diagnostics, bootstrap_candidates[0], switched=False)
                                self._confirm_candidate(secondary_slot, secondary_diagnostics, bootstrap_candidates[1], switched=False)

                            first_center = self._process_tracking_slot(
                                state=primary_slot,
                                candidates=candidates,
                                frame_width=orig_w,
                                frame_height=orig_h,
                                crop_width=src_crop_w,
                                panel_center=orig_w * 0.33,
                                diagnostics=primary_diagnostics,
                                layout=layout,
                                frame_index=frame_count,
                                cut_confidence=cut_confidence,
                            )
                            remaining_candidates = [
                                candidate
                                for candidate in candidates
                                if primary_slot.confirmed_track_id is None or candidate.track_id != primary_slot.confirmed_track_id
                            ]
                            second_center = self._process_tracking_slot(
                                state=secondary_slot,
                                candidates=remaining_candidates,
                                frame_width=orig_w,
                                frame_height=orig_h,
                                crop_width=src_crop_w,
                                panel_center=orig_w * 0.67,
                                diagnostics=secondary_diagnostics,
                                layout=layout,
                                frame_index=frame_count,
                                cut_confidence=cut_confidence,
                            )
                            current_cx1, current_cx2 = first_center, second_center
                            current_pair = (primary_slot.confirmed_track_id, secondary_slot.confirmed_track_id)
                            if (
                                last_confirmed_pair is not None
                                and all(track_id is not None for track_id in last_confirmed_pair)
                                and all(track_id is not None for track_id in current_pair)
                                and current_pair == (last_confirmed_pair[1], last_confirmed_pair[0])
                            ):
                                split_panel_swap_count += 1
                            if any(track_id is not None for track_id in current_pair):
                                last_confirmed_pair = current_pair
                        else:
                            current_cx1 = self._process_tracking_slot(
                                state=primary_slot,
                                candidates=candidates,
                                frame_width=orig_w,
                                frame_height=orig_h,
                                crop_width=src_crop_w,
                                panel_center=orig_w / 2.0,
                                diagnostics=primary_diagnostics,
                                layout=layout,
                                frame_index=frame_count,
                                cut_confidence=cut_confidence,
                            )
                            current_cx2 = current_cx1

                    if manual_center_x is not None:
                        current_cx1 = manual_center_x * orig_w
                        current_cx2 = current_cx1

                    def get_crop(center_x: float) -> np.ndarray:
                        x1, x2 = self._compute_crop_bounds(center_x, src_crop_w, orig_w)
                        return frame[0:orig_h, x1:x2]

                    primary_bounds = self._compute_crop_bounds(current_cx1, src_crop_w, orig_w)
                    secondary_bounds = self._compute_crop_bounds(current_cx2, src_crop_w, orig_w)

                    if layout == "split" and manual_center_x is None:
                        primary_margin_ok = False
                        secondary_margin_ok = False
                        if primary_slot.last_confirmed_box is not None:
                            left_margin = max(0.0, primary_slot.last_confirmed_box[0] - primary_bounds[0])
                            right_margin = max(0.0, primary_bounds[1] - primary_slot.last_confirmed_box[2])
                            primary_margin_ok = min(left_margin, right_margin) / max(float(src_crop_w), 1.0) >= SPLIT_EDGE_MARGIN_RATIO
                        if secondary_slot.last_confirmed_box is not None:
                            left_margin = max(0.0, secondary_slot.last_confirmed_box[0] - secondary_bounds[0])
                            right_margin = max(0.0, secondary_bounds[1] - secondary_slot.last_confirmed_box[2])
                            secondary_margin_ok = min(left_margin, right_margin) / max(float(src_crop_w), 1.0) >= SPLIT_EDGE_MARGIN_RATIO
                        primary_edge_violation_streak = 0 if primary_margin_ok else primary_edge_violation_streak + 1
                        secondary_edge_violation_streak = 0 if secondary_margin_ok else secondary_edge_violation_streak + 1
                        if not primary_margin_ok:
                            face_edge_violation_frames += 1
                        if not secondary_margin_ok:
                            face_edge_violation_frames += 1
                        if split_panel_swap_count > 0 or primary_edge_violation_streak >= SPLIT_UNSAFE_SUSTAINED_FRAMES or secondary_edge_violation_streak >= SPLIT_UNSAFE_SUSTAINED_FRAMES:
                            split_unsafe_frames += 1

                    if layout == "split" and manual_center_x is None:
                        crop1 = get_crop(current_cx1)
                        crop2 = get_crop(current_cx2)
                        res1 = cv2.resize(crop1, (target_w, split_panel_h))
                        res2 = cv2.resize(crop2, (target_w, split_panel_h))
                        gutter = np.zeros((split_gutter_h, target_w, 3), dtype=np.uint8)
                        final_frame = np.vstack((res1, gutter, res2))
                    else:
                        crop = get_crop(current_cx1)
                        final_frame = cv2.resize(crop, (target_w, target_h))

                    try:
                        stdin.write(final_frame.tobytes())
                    except (BrokenPipeError, OSError) as exc:
                        stderr_tail = ""
                        if ffmpeg_proc.stderr is not None:
                            stderr_tail = ffmpeg_proc.stderr.read().decode("utf-8", errors="replace")[-500:]
                        raise RuntimeError(f"FFmpeg encode pipe kirildi: {stderr_tail or str(exc)}") from exc

                    if self._debug_artifacts_enabled():
                        try:
                            debug_frame = self._draw_debug_overlay(
                                frame=frame,
                                candidates=candidates,
                                crop_bounds=[
                                    ("primary", primary_bounds, (80, 220, 120)),
                                    *([("secondary", secondary_bounds, (255, 200, 80))] if layout == "split" and manual_center_x is None else []),
                                ],
                                primary_slot=primary_slot,
                                secondary_slot=secondary_slot if layout == "split" and manual_center_x is None else None,
                                frame_index=frame_count,
                                cut_confidence=cut_confidence,
                                layout=layout,
                            )
                            if debug_writer is None:
                                debug_writer = self._create_overlay_writer(
                                    debug_overlay_temp,
                                    orig_fps,
                                    (debug_frame.shape[1], debug_frame.shape[0]),
                                )
                                if debug_writer is None:
                                    debug_status = "partial"
                            if debug_writer is not None:
                                debug_writer.write(debug_frame)
                                debug_overlay_ready = True
                        except Exception as exc:
                            logger.warning("Debug overlay yazilamadi: {}", exc)
                            debug_status = "partial"

                cap.release()
                stdin.close()
                ffmpeg_proc.stdin = None
                _, ffmpeg_stderr = ffmpeg_proc.communicate()
                if ffmpeg_proc.returncode != 0:
                    stderr_tail = (ffmpeg_stderr or b"").decode("utf-8", errors="replace")[-500:]
                    raise RuntimeError(f"FFmpeg encode hatasi: {stderr_tail}")
            finally:
                if debug_writer is not None:
                    debug_writer.release()
                if self._device == "cuda":
                    gc.collect()
                    torch.cuda.empty_cache()

            normalized_metrics = extract_media_stream_metrics(probe_media(temp_cut))
            rendered_metrics = extract_media_stream_metrics(probe_media(temp_video_only))
            merge_timeout = self._compute_ffmpeg_timeout(duration, minimum=300)

            logger.info("🎵 Ses birlestiriliyor...")
            if normalized_metrics["has_audio"]:
                cmd_merge = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    temp_video_only,
                    "-i",
                    temp_cut,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-shortest",
                    output_filename,
                ]
            else:
                cmd_merge = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    temp_video_only,
                    "-c:v",
                    "copy",
                    "-an",
                    output_filename,
                ]

            merge_result = self._run_command_with_cancel(
                cmd_merge,
                timeout=merge_timeout,
                cancel_event=cancel_event,
            )
            if merge_result.returncode != 0:
                merge_stderr = merge_result.stderr or ""
                logger.error("FFmpeg ses birlestirme hatasi: {}", merge_stderr[-500:])
                if normalized_metrics["has_audio"] and _is_nvenc_error(merge_stderr):
                    cmd_cpu_fallback = [
                        "ffmpeg",
                        "-y",
                        "-i",
                        temp_video_only,
                    ]
                    if normalized_metrics["has_audio"]:
                        cmd_cpu_fallback.extend(["-i", temp_cut])
                    cmd_cpu_fallback.extend(
                        [
                            "-c:v",
                            "libx264",
                            "-preset",
                            "medium",
                            "-crf",
                            "23",
                        ]
                    )
                    if normalized_metrics["has_audio"]:
                        cmd_cpu_fallback.extend(["-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest"])
                    else:
                        cmd_cpu_fallback.append("-an")
                    cmd_cpu_fallback.append(output_filename)
                    fallback_result = self._run_command_with_cancel(
                        cmd_cpu_fallback,
                        timeout=merge_timeout,
                        cancel_event=cancel_event,
                    )
                    if fallback_result.returncode != 0:
                        raise RuntimeError(f"Ses birlestirilemedi: {(fallback_result.stderr or '')[-300:]}")
                else:
                    raise RuntimeError(f"Ses birlestirilemedi: {merge_stderr[-300:]}")

            merged_metrics = extract_media_stream_metrics(probe_media(output_filename))
            debug_timing = self._build_debug_timing(
                source_metrics=source_metrics,
                normalized_metrics=normalized_metrics,
                rendered_metrics=rendered_metrics,
                merged_metrics=merged_metrics,
            )
            if debug_timing["merged_output_drift_ms"] > 150:
                raise RuntimeError(f"Merged output drift too high: {debug_timing['merged_output_drift_ms']}ms")

            if layout == "split" and manual_center_x is None:
                tracking_quality = TrackingDiagnostics.merge(
                    primary_diagnostics,
                    secondary_diagnostics,
                    panel_swap_count=split_panel_swap_count,
                )
                tracking_quality.update(
                    {
                        "face_edge_violation_frames": int(face_edge_violation_frames),
                        "unsafe_split_frames": int(split_unsafe_frames),
                        "layout_safety_status": (
                            "unsafe"
                            if split_unsafe_frames > 0 or split_panel_swap_count > 0
                            else ("degraded" if tracking_quality.get("status") in {"degraded", "fallback"} else "safe")
                        ),
                    }
                )
                debug_tracking = {
                    "primary": self._build_tracking_debug(primary_diagnostics),
                    "secondary": self._build_tracking_debug(secondary_diagnostics),
                } if os.getenv("DEBUG_RENDER_ARTIFACTS") == "1" else None
            else:
                tracking_quality = primary_diagnostics.to_quality()
                tracking_quality.update(
                    {
                        "face_edge_violation_frames": int(face_edge_violation_frames),
                        "unsafe_split_frames": 0,
                        "layout_safety_status": "degraded" if tracking_quality.get("status") in {"degraded", "fallback"} else "safe",
                    }
                )
                debug_tracking = self._build_tracking_debug(primary_diagnostics)
            if manual_center_x is not None:
                tracking_quality.update(
                    {
                        "status": "good",
                        "mode": "manual",
                        "fallback_frames": 0,
                        "avg_center_jump_px": 0.0,
                        "layout_safety_status": "safe",
                    }
                )

            audio_validation = {
                "has_audio": bool(merged_metrics.get("has_audio")),
                "audio_sample_rate": merged_metrics.get("audio_sample_rate"),
                "audio_channels": merged_metrics.get("audio_channels"),
                "audio_duration": round(float(merged_metrics.get("audio_duration") or 0.0), 4),
                "audio_validation_status": merged_metrics.get("audio_validation_status"),
            }

            if not os.path.exists(output_filename):
                raise RuntimeError(f"Cikti dosyasi olusturulamadi: {output_filename}")
            if os.path.getsize(output_filename) <= 0:
                raise RuntimeError(f"Cikti dosyasi bos: {output_filename}")

            return {
                "tracking_quality": tracking_quality,
                "debug_timing": debug_timing,
                "audio_validation": audio_validation,
                "debug_tracking": debug_tracking,
                "debug_overlay_temp_path": debug_overlay_temp if debug_overlay_ready else None,
                "debug_artifacts_status": debug_status if debug_status is not None else None,
            }
        finally:
            try:
                cap.release()  # type: ignore[name-defined]
            except Exception:
                pass
            try:
                if ffmpeg_proc is not None:  # type: ignore[name-defined]
                    if ffmpeg_proc.stdin is not None and not ffmpeg_proc.stdin.closed:
                        ffmpeg_proc.stdin.close()
                    if ffmpeg_proc.poll() is None:
                        ffmpeg_proc.kill()
                        ffmpeg_proc.wait()
            except Exception:
                pass
            for artifact in (temp_cut, temp_video_only):
                try:
                    os.remove(artifact)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    logger.warning("Dosya silinemedi: {} - {}", artifact, exc)
            if not debug_overlay_ready:
                try:
                    os.remove(debug_overlay_temp)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    logger.warning("Debug overlay silinemedi: {} - {}", debug_overlay_temp, exc)

    def resolve_layout_for_segment(
        self,
        *,
        input_video: str,
        start_time: float,
        end_time: float,
        requested_layout: str,
        manual_center_x: float | None = None,
    ) -> LayoutDecisionReport:
        normalized_layout = ensure_valid_requested_layout(requested_layout)
        if normalized_layout == "single":
            return LayoutDecisionReport(
                requested_layout=normalized_layout,
                resolved_layout="single",
                layout_safety_status="safe",
                layout_safety_mode=_read_layout_safety_mode(),
                scene_class="single_dynamic",
            )
        if manual_center_x is not None:
            return LayoutDecisionReport(
                requested_layout=normalized_layout,
                resolved_layout="single",
                layout_fallback_reason="split_not_stable",
                layout_auto_fix_applied=True,
                layout_auto_fix_reason="split_face_safety",
                layout_safety_status="safe",
                layout_safety_mode=_read_layout_safety_mode(),
                scene_class="single_dynamic",
            )

        self._ensure_model_loaded()

        duration = max(0.2, end_time - start_time)
        frame_results: list[dict[str, object]] = []
        speaker_count_peak = 0
        for index in range(SPLIT_SAMPLE_WINDOWS):
            ratio = 0.0 if SPLIT_SAMPLE_WINDOWS == 1 else index / (SPLIT_SAMPLE_WINDOWS - 1)
            sample_time = start_time + (duration * ratio)
            frame = self._extract_probe_frame(input_video, sample_time)
            if frame is None:
                continue
            frame_height = int(frame.shape[0]) if frame.ndim >= 2 else 0
            frame_width = int(frame.shape[1]) if frame.ndim >= 2 else 0
            centers = self._detect_person_centers(frame)
            candidates = sorted(
                self._predict_people(frame),
                key=lambda candidate: (candidate.visibility_score, candidate.area),
                reverse=True,
            )
            speaker_count_peak = max(speaker_count_peak, len(candidates), len(centers))
            crop_width = min(frame_width, max(1, int(frame_height * (LOGICAL_CANVAS_WIDTH / SPLIT_PANEL_HEIGHT)))) if frame_width > 0 and frame_height > 0 else 0
            pair = sorted(candidates[:2], key=lambda candidate: candidate.center_x)
            edge_margin_ratios = [
                self._split_crop_margin_ratio(candidate, frame_width=frame_width, crop_width=crop_width)
                for candidate in pair
            ] if crop_width > 0 else []
            visibility_scores = [candidate.visibility_score for candidate in pair]
            if not pair and len(centers) >= 2:
                visibility_scores = [1.0, 1.0]
                edge_margin_ratios = [1.0, 1.0]
            frame_results.append(
                {
                    "frame_width": frame_width,
                    "sample_index": index,
                    "sample_total": SPLIT_SAMPLE_WINDOWS,
                    "speaker_count": max(len(candidates), len(centers)),
                    "candidates": pair,
                    "centers": [candidate.center_x for candidate in pair] if pair else centers[:2],
                    "visibility_scores": visibility_scores,
                    "edge_margin_ratios": edge_margin_ratios,
                }
            )

        split_report = self._evaluate_split_layout(frame_results)
        scene_class = "dual_separated" if split_report["stable"] else "dual_overlap_risky"
        if speaker_count_peak <= 1:
            scene_class = "single_dynamic"
        if speaker_count_peak >= 3:
            split_report = {"stable": False, "reason": "split_face_safety", "identity_confidence": 0.0}
            scene_class = "dual_overlap_risky"

        if split_report["stable"]:
            return LayoutDecisionReport(
                requested_layout=normalized_layout,
                resolved_layout="split",
                layout_safety_status="safe",
                layout_safety_mode=_read_layout_safety_mode(),
                scene_class=scene_class,
                speaker_count_peak=max(2, speaker_count_peak),
                dominant_speaker_confidence=None,
            )

        auto_fix_reason = str(split_report["reason"] or "split_face_safety")
        return LayoutDecisionReport(
            requested_layout=normalized_layout,
            resolved_layout="single",
            layout_fallback_reason="split_not_stable",
            layout_auto_fix_applied=normalized_layout in {"auto", "split"},
            layout_auto_fix_reason=auto_fix_reason,
            layout_safety_status="safe",
            layout_safety_mode=_read_layout_safety_mode(),
            scene_class=scene_class,
            speaker_count_peak=max(1, speaker_count_peak),
            dominant_speaker_confidence=None,
        )

    def _detect_person_centers(self, frame: np.ndarray) -> list[float]:
        candidates = self._predict_people(frame)
        if not candidates:
            return []
        ranked = sorted(candidates, key=lambda candidate: (candidate.visibility_score, candidate.area), reverse=True)[:2]
        return sorted(candidate.center_x for candidate in ranked)

    def analyze_opening_shot(
        self,
        *,
        input_video: str,
        start_time: float,
        end_time: float,
        resolved_layout: str,
        manual_center_x: float | None = None,
    ) -> dict[str, object]:
        if manual_center_x is not None:
            return {
                "layout_validation_status": "manual",
                "opening_visibility_delay_ms": 0.0,
                "suggested_start_time": float(start_time),
            }

        self._ensure_model_loaded()
        duration = max(0.2, end_time - start_time)
        window = min(OPENING_VISIBILITY_WINDOW_SECONDS, duration)
        earliest_visible_offset: float | None = None
        split_initial_centers: tuple[float, float] | None = None
        sampled_any_frame = False
        for sample_index in range(OPENING_SAMPLE_COUNT):
            ratio = 0.0 if OPENING_SAMPLE_COUNT == 1 else sample_index / (OPENING_SAMPLE_COUNT - 1)
            sample_time = start_time + (window * ratio)
            frame = self._extract_probe_frame(input_video, sample_time)
            if frame is None:
                continue
            sampled_any_frame = True
            candidates = sorted(
                self._predict_people(frame),
                key=lambda candidate: (candidate.visibility_score, candidate.area),
                reverse=True,
            )
            visible = False
            if resolved_layout == "split":
                centers = sorted(candidate.center_x for candidate in candidates[:2])
                if len(centers) >= 2:
                    visible = abs(centers[1] - centers[0]) >= frame.shape[1] * SPLIT_MIN_SEPARATION_RATIO
                    if visible:
                        split_initial_centers = (float(centers[0]), float(centers[1]))
            else:
                visible = len(candidates) > 0
            if visible:
                earliest_visible_offset = max(0.0, sample_time - start_time)
                break

        if not sampled_any_frame:
            return {
                "layout_validation_status": "probe_failed",
                "opening_visibility_delay_ms": 0.0,
                "suggested_start_time": float(start_time),
            }

        if earliest_visible_offset is None:
            return {
                "layout_validation_status": "opening_subject_missing",
                "opening_visibility_delay_ms": round(window * 1000, 3),
                "suggested_start_time": float(min(end_time, start_time + min(window, OPENING_MAX_SHIFT_SECONDS))),
            }

        suggested_start = float(start_time)
        status = "ok"
        if earliest_visible_offset > OPENING_VISIBILITY_OK_SECONDS:
            status = "opening_subject_delayed"
            suggested_start = float(min(end_time, start_time + min(earliest_visible_offset, OPENING_MAX_SHIFT_SECONDS)))
        return {
            "layout_validation_status": status,
            "opening_visibility_delay_ms": round(earliest_visible_offset * 1000, 3),
            "suggested_start_time": suggested_start,
            **({"initial_slot_centers": [round(split_initial_centers[0], 3), round(split_initial_centers[1], 3)]} if split_initial_centers is not None else {}),
        }

    @staticmethod
    def _normalize_split_frame_result(frame_result: object, index: int) -> dict[str, object]:
        if isinstance(frame_result, dict):
            centers = [float(value) for value in frame_result.get("centers", []) if isinstance(value, (int, float))]
            return {
                "frame_width": int(frame_result.get("frame_width", 0) or 0),
                "sample_index": int(frame_result.get("sample_index", index) or index),
                "sample_total": int(frame_result.get("sample_total", SPLIT_SAMPLE_WINDOWS) or SPLIT_SAMPLE_WINDOWS),
                "speaker_count": int(frame_result.get("speaker_count", len(centers)) or len(centers)),
                "centers": centers,
                "visibility_scores": [float(value) for value in frame_result.get("visibility_scores", []) if isinstance(value, (int, float))],
                "edge_margin_ratios": [float(value) for value in frame_result.get("edge_margin_ratios", []) if isinstance(value, (int, float))],
                "candidates": frame_result.get("candidates") if isinstance(frame_result.get("candidates"), list) else [],
            }
        if isinstance(frame_result, tuple):
            if len(frame_result) >= 4:
                frame_width, centers, sample_index, sample_total = frame_result[:4]
            else:
                frame_width, centers = frame_result[:2]
                sample_index = index
                sample_total = len(frame_result)
            center_values = [float(value) for value in centers if isinstance(value, (int, float))]
            return {
                "frame_width": int(frame_width or 0),
                "sample_index": int(sample_index),
                "sample_total": int(sample_total or SPLIT_SAMPLE_WINDOWS),
                "speaker_count": len(center_values),
                "centers": center_values,
                "visibility_scores": [1.0 for _ in center_values],
                "edge_margin_ratios": [1.0 for _ in center_values],
                "candidates": [],
            }
        return {
            "frame_width": 0,
            "sample_index": index,
            "sample_total": SPLIT_SAMPLE_WINDOWS,
            "speaker_count": 0,
            "centers": [],
            "visibility_scores": [],
            "edge_margin_ratios": [],
            "candidates": [],
        }

    @classmethod
    def _evaluate_split_layout(cls, frame_results: list[object]) -> dict[str, object]:
        if not frame_results:
            return {"stable": False, "reason": "split_face_safety", "identity_confidence": 0.0}

        normalized_results = [
            cls._normalize_split_frame_result(frame_result, index)
            for index, frame_result in enumerate(frame_results)
        ]
        stable_positions: list[int] = []
        sampled_frames = 0
        total_windows = int(normalized_results[0]["sample_total"] or SPLIT_SAMPLE_WINDOWS)
        previous_pair: list[DetectionCandidate] | None = None
        identity_scores: list[float] = []

        for frame_result in normalized_results:
            frame_width = int(frame_result["frame_width"])
            centers = list(frame_result["centers"])
            visibility_scores = list(frame_result["visibility_scores"])
            edge_margin_ratios = list(frame_result["edge_margin_ratios"])
            sample_index = int(frame_result["sample_index"])
            sampled_frames += 1 if frame_width > 0 else 0
            if frame_width <= 0 or len(centers) < 2 or int(frame_result["speaker_count"]) < 2:
                previous_pair = None
                continue
            separation = abs(float(centers[1]) - float(centers[0]))
            visibility_ok = len(visibility_scores) >= 2 and all(score >= SPLIT_MIN_VISIBILITY_SCORE for score in visibility_scores[:2])
            edge_margin_ok = len(edge_margin_ratios) >= 2 and all(margin >= SPLIT_EDGE_MARGIN_RATIO for margin in edge_margin_ratios[:2])
            if visibility_ok and edge_margin_ok and separation >= frame_width * SPLIT_MIN_SEPARATION_RATIO:
                stable_positions.append(sample_index)

            candidates = frame_result["candidates"] if isinstance(frame_result["candidates"], list) else []
            if len(candidates) >= 2 and previous_pair is not None and len(previous_pair) >= 2:
                slot_scores = []
                for previous_candidate, candidate in zip(previous_pair[:2], candidates[:2], strict=False):
                    temp_state = TrackSlotState(
                        "probe",
                        candidate.center_x,
                        confirmed_track_id=previous_candidate.track_id,
                        last_confirmed_box=previous_candidate.box,
                        last_confirmed_center=previous_candidate.center_x,
                        last_confirmed_area=previous_candidate.area,
                        last_confirmed_aspect_ratio=previous_candidate.aspect_ratio,
                        last_visibility_score=previous_candidate.visibility_score,
                    )
                    slot_scores.append(cls._candidate_identity_confidence(candidate, temp_state))
                if slot_scores:
                    identity_scores.append(float(np.mean(slot_scores)))
            previous_pair = candidates[:2] if len(candidates) >= 2 else None

        identity_confidence = float(np.mean(identity_scores)) if identity_scores else 1.0
        if sampled_frames == 0:
            return {"stable": False, "reason": "split_face_safety", "identity_confidence": identity_confidence}
        if total_windows >= SPLIT_SAMPLE_WINDOWS:
            if len(stable_positions) < SPLIT_REQUIRED_POSITIVE_WINDOWS:
                return {"stable": False, "reason": "split_face_safety", "identity_confidence": identity_confidence}
            region_hits = {
                "early": any(position <= (total_windows // 3) for position in stable_positions),
                "mid": any((total_windows // 3) < position < (2 * total_windows // 3) for position in stable_positions),
                "late": any(position >= (2 * total_windows // 3) for position in stable_positions),
            }
            if not all(region_hits.values()):
                return {"stable": False, "reason": "split_face_safety", "identity_confidence": identity_confidence}
        elif len(stable_positions) < math.ceil(sampled_frames * 0.5):
            return {"stable": False, "reason": "split_face_safety", "identity_confidence": identity_confidence}

        if identity_confidence < 0.58:
            return {"stable": False, "reason": "split_identity_unstable", "identity_confidence": identity_confidence}

        return {"stable": True, "reason": None, "identity_confidence": identity_confidence}

    @classmethod
    def _is_split_layout_stable(cls, frame_results: list[tuple]) -> bool:
        return bool(cls._evaluate_split_layout(frame_results)["stable"])

    def cut_segment_only(
        self,
        input_video: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        cancel_event: threading.Event | None = None,
        require_audio: bool = False,
    ) -> dict:
        duration = end_time - start_time
        logger.info("✂️ Zaman kesimi: {} - {} sn (orijinal boyut) → {}", start_time, end_time, output_filename)
        source_metrics = extract_media_stream_metrics(probe_media(input_video))
        if require_audio and not source_metrics["has_audio"]:
            raise RuntimeError("Audio stream required for this render but source video has no audio")

        source_fps = float(source_metrics.get("fps") or 30.0)
        cmd_nvenc = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-i",
            input_video,
            "-t",
            str(duration),
            "-vsync",
            "cfr",
            "-r",
            f"{source_fps:.6f}",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p6",
            "-b:v",
            "8M",
        ]
        if source_metrics["has_audio"]:
            cmd_nvenc.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd_nvenc.append("-an")
        cmd_nvenc.append(output_filename)

        cmd_cpu = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-i",
            input_video,
            "-t",
            str(duration),
            "-vsync",
            "cfr",
            "-r",
            f"{source_fps:.6f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
        ]
        if source_metrics["has_audio"]:
            cmd_cpu.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd_cpu.append("-an")
        cmd_cpu.append(output_filename)

        cut_timeout = self._compute_ffmpeg_timeout(duration, start_time=start_time, minimum=300)
        result = self._run_command_with_cancel(cmd_nvenc, timeout=cut_timeout, cancel_event=cancel_event)
        if result.returncode != 0:
            stderr = result.stderr or ""
            if _is_nvenc_error(stderr):
                cpu_result = self._run_command_with_cancel(cmd_cpu, timeout=cut_timeout, cancel_event=cancel_event)
                if cpu_result.returncode != 0:
                    raise RuntimeError("CPU fallback ile video kesilemedi")
            else:
                raise RuntimeError(f"Video kesilemedi: {stderr[-300:]}")

        merged_metrics = extract_media_stream_metrics(probe_media(output_filename))
        debug_timing = {
            "source_fps": round(float(source_metrics.get("fps") or 0.0), 4),
            "normalized_fps": round(float(merged_metrics.get("fps") or 0.0), 4),
            "source_duration": round(float(source_metrics.get("duration") or 0.0), 4),
            "normalized_video_duration": round(float(merged_metrics.get("video_duration") or merged_metrics.get("duration") or 0.0), 4),
            "normalized_audio_duration": round(float(merged_metrics.get("audio_duration") or 0.0), 4),
            "merged_output_duration": round(float(merged_metrics.get("duration") or 0.0), 4),
            "merged_output_drift_ms": round(
                abs(float(merged_metrics.get("video_duration") or 0.0) - float(merged_metrics.get("audio_duration") or 0.0)) * 1000
                if merged_metrics.get("has_audio")
                else 0.0,
                3,
            ),
            "dropped_or_duplicated_frame_estimate": 0.0,
            "has_audio": bool(merged_metrics.get("has_audio")),
            "audio_sample_rate": merged_metrics.get("audio_sample_rate"),
            "audio_channels": merged_metrics.get("audio_channels"),
        }
        if debug_timing["merged_output_drift_ms"] > 150:
            raise RuntimeError(f"Merged output drift too high: {debug_timing['merged_output_drift_ms']}ms")

        debug_overlay_temp = None
        debug_status = None
        if self._debug_artifacts_enabled():
            debug_overlay_temp = str(TEMP_DIR / f"overlay_cut_{uuid.uuid4().hex[:8]}.mp4")
            try:
                shutil.copy2(output_filename, debug_overlay_temp)
                debug_status = "partial"
            except OSError as exc:
                logger.warning("Cut-only debug overlay olusturulamadi: {}", exc)
                debug_overlay_temp = None
                debug_status = "partial"

        return {
            "tracking_quality": {
                "status": "good",
                "mode": "manual",
                "total_frames": 0,
                "fallback_frames": 0,
                "avg_center_jump_px": 0.0,
                "speaker_lock_policy": "hold_until_unsafe",
                "identity_confidence": 1.0,
                "face_edge_violation_frames": 0,
                "unsafe_split_frames": 0,
                "layout_safety_status": "safe",
                "confirmed_track_frames": 0,
                "grace_hold_frames": 0,
                "controlled_return_frames": 0,
                "reacquire_attempt_count": 0,
                "reacquire_success_count": 0,
                "active_track_id_switches": 0,
                "shot_cut_resets": 0,
                "max_track_lost_streak": 0,
            },
            "debug_timing": debug_timing,
            "audio_validation": {
                "has_audio": bool(merged_metrics.get("has_audio")),
                "audio_sample_rate": merged_metrics.get("audio_sample_rate"),
                "audio_channels": merged_metrics.get("audio_channels"),
                "audio_duration": round(float(merged_metrics.get("audio_duration") or 0.0), 4),
                "audio_validation_status": merged_metrics.get("audio_validation_status"),
            },
            "debug_tracking": None,
            "debug_overlay_temp_path": debug_overlay_temp,
            "debug_artifacts_status": debug_status,
        }
