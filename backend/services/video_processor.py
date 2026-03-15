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
CONFIRMED_PAN_RATIO = 0.02
CONTROLLED_RETURN_PAN_RATIO = 0.03
SAME_ID_REACQUIRE_CENTER_RATIO = 0.08
DIFF_ID_REACQUIRE_CENTER_RATIO = 0.12
SPLIT_SAMPLE_WINDOWS = 16
SPLIT_REQUIRED_POSITIVE_WINDOWS = 10
SPLIT_MIN_SEPARATION_RATIO = 0.18
TRACKER_CONFIG = "bytetrack.yaml"
DETECTION_LONG_EDGE = 960
HARD_CUT_THRESHOLD = 0.75
SOFT_CUT_THRESHOLD = 0.55


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


@dataclass
class TrackingDiagnostics:
    mode: str = "tracked"
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

    def to_quality(self) -> dict:
        avg_center_jump = self.total_center_jump_px / self.total_frames if self.total_frames > 0 else 0.0
        fallback_ratio = self.fallback_frames / self.total_frames if self.total_frames > 0 else 0.0
        status = "good"
        if self.mode == "manual":
            status = "good"
        elif fallback_ratio >= 0.5:
            status = "fallback"
        elif fallback_ratio >= 0.12 or self.shot_cut_resets > 0 or self.active_track_id_switches > 1:
            status = "degraded"
        return {
            "status": status,
            "mode": self.mode,
            "total_frames": self.total_frames,
            "fallback_frames": self.fallback_frames,
            "avg_center_jump_px": round(avg_center_jump, 3),
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
    def merge(diag_a: "TrackingDiagnostics", diag_b: "TrackingDiagnostics") -> dict:
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
        return {
            "status": merged_status,
            "mode": "tracked",
            "total_frames": total_frames,
            "fallback_frames": int(quality_a.get("fallback_frames", 0)) + int(quality_b.get("fallback_frames", 0)),
            "avg_center_jump_px": round(avg_center_jump, 3),
            "confirmed_track_frames": int(quality_a.get("confirmed_track_frames", 0)) + int(quality_b.get("confirmed_track_frames", 0)),
            "grace_hold_frames": int(quality_a.get("grace_hold_frames", 0)) + int(quality_b.get("grace_hold_frames", 0)),
            "controlled_return_frames": int(quality_a.get("controlled_return_frames", 0)) + int(quality_b.get("controlled_return_frames", 0)),
            "reacquire_attempt_count": int(quality_a.get("reacquire_attempt_count", 0)) + int(quality_b.get("reacquire_attempt_count", 0)),
            "reacquire_success_count": int(quality_a.get("reacquire_success_count", 0)) + int(quality_b.get("reacquire_success_count", 0)),
            "active_track_id_switches": int(quality_a.get("active_track_id_switches", 0)) + int(quality_b.get("active_track_id_switches", 0)),
            "shot_cut_resets": max(int(quality_a.get("shot_cut_resets", 0)), int(quality_b.get("shot_cut_resets", 0))),
            "max_track_lost_streak": max(int(quality_a.get("max_track_lost_streak", 0)), int(quality_b.get("max_track_lost_streak", 0))),
        }


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
        logger.info("🎥 Video Processor hazirlandi (YOLO lazy-load, cihaz: {}).", device.upper())

    def _ensure_model_loaded(self) -> None:
        if self.model is not None:
            return

        logger.info("🔄 YOLO modeli yukleniyor: {}", self._model_path)
        self.model = YOLO(self._model_path)
        if self._device == "cuda" and not torch.cuda.is_available():
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

    def _track_people(self, frame: np.ndarray) -> list[DetectionCandidate]:
        if self.model is None:
            return []
        resized, scale_x, scale_y = self._resize_for_detection(frame)
        results = self.model.track(
            resized,
            persist=True,
            tracker=TRACKER_CONFIG,
            classes=[0],
            verbose=False,
            conf=MIN_DETECTION_CONFIDENCE,
        )
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
            candidates.append(
                DetectionCandidate(
                    track_id=track_id,
                    box=(x1, y1, x2, y2),
                    center_x=(x1 + x2) / 2.0,
                    area=width * height,
                    confidence=confidence,
                    aspect_ratio=width / height,
                )
            )
        return candidates

    def _predict_people(self, frame: np.ndarray) -> list[DetectionCandidate]:
        if self.model is None:
            return []
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
            candidates.append(
                DetectionCandidate(
                    track_id=index,
                    box=(x1, y1, x2, y2),
                    center_x=(x1 + x2) / 2.0,
                    area=width * height,
                    confidence=confidence,
                    aspect_ratio=width / height,
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
        state.confirmed_track_id = candidate.track_id
        state.last_confirmed_box = candidate.box
        state.last_confirmed_center = candidate.center_x
        state.last_confirmed_area = candidate.area
        state.last_confirmed_aspect_ratio = candidate.aspect_ratio
        state.grace_remaining = 0
        state.controlled_return_frames_remaining = 0
        state.reacquire_counts.clear()
        state.lost_streak = 0
        state.last_mode = "tracked"
        return candidate.center_x

    @staticmethod
    def _move_towards(current: float, target: float, *, max_step_px: float, smoothness: float) -> float:
        if abs(target - current) <= max_step_px:
            return target
        stepped = current + np.sign(target - current) * max_step_px
        return float((current * (1.0 - smoothness)) + (stepped * smoothness))

    def _process_tracking_slot(
        self,
        *,
        state: TrackSlotState,
        candidates: list[DetectionCandidate],
        frame_width: int,
        frame_height: int,
        panel_center: float,
        diagnostics: TrackingDiagnostics,
        smoothness: float,
        frame_index: int,
        cut_confidence: float,
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

        pan_ratio = CONTROLLED_RETURN_PAN_RATIO if mode == "controlled_return" else CONFIRMED_PAN_RATIO
        previous_cx = state.current_cx
        state.current_cx = self._move_towards(
            state.current_cx,
            target_cx,
            max_step_px=frame_width * pan_ratio,
            smoothness=max(0.55, smoothness),
        )
        diagnostics.total_center_jump_px += abs(state.current_cx - previous_cx)
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
                    "cut_confidence": round(cut_confidence, 4),
                    "candidate_count": len(candidates),
                }
            )
        return state.current_cx

    @staticmethod
    def _build_tracking_debug(diagnostics: TrackingDiagnostics) -> dict | None:
        if os.getenv("DEBUG_RENDER_ARTIFACTS") != "1":
            return None
        return {
            "timeline": diagnostics.timeline,
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
                label,
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

        job_uuid = uuid.uuid4().hex[:8]
        temp_cut = str(TEMP_DIR / f"cut_{job_uuid}.mp4")
        temp_video_only = str(TEMP_DIR / f"vonly_{job_uuid}.mp4")
        debug_overlay_temp = str(TEMP_DIR / f"overlay_{job_uuid}.mp4")
        debug_overlay_ready = False

        cut_timeout = self._compute_ffmpeg_timeout(duration, start_time=start_time, minimum=300)
        cut_cmd = [
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
            cut_cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cut_cmd.append("-an")
        cut_cmd.append(temp_cut)

        try:
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

            primary_diagnostics = TrackingDiagnostics(mode="tracked")
            secondary_diagnostics = TrackingDiagnostics(mode="tracked")
            primary_slot = TrackSlotState("primary", orig_w / 2)
            secondary_slot = TrackSlotState("secondary", orig_w / 2)
            ffmpeg_proc: subprocess.Popen[bytes] | None = None
            debug_writer: cv2.VideoWriter | None = None
            frame_count = 0
            previous_frame: np.ndarray | None = None
            debug_status = "complete" if self._debug_artifacts_enabled() else None

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
                        "-c:v",
                        "h264_nvenc",
                        "-preset",
                        "p6",
                        "-b:v",
                        "8M",
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
                        candidates = self._track_people(frame)
                        candidates = sorted(candidates, key=lambda candidate: candidate.center_x)
                        if layout == "split":
                            first_center = self._process_tracking_slot(
                                state=primary_slot,
                                candidates=candidates,
                                frame_width=orig_w,
                                frame_height=orig_h,
                                panel_center=orig_w * 0.33,
                                diagnostics=primary_diagnostics,
                                smoothness=smoothness,
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
                                panel_center=orig_w * 0.67,
                                diagnostics=secondary_diagnostics,
                                smoothness=smoothness,
                                frame_index=frame_count,
                                cut_confidence=cut_confidence,
                            )
                            current_cx1, current_cx2 = sorted([first_center, second_center])
                        else:
                            current_cx1 = self._process_tracking_slot(
                                state=primary_slot,
                                candidates=candidates,
                                frame_width=orig_w,
                                frame_height=orig_h,
                                panel_center=orig_w / 2.0,
                                diagnostics=primary_diagnostics,
                                smoothness=smoothness,
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
                tracking_quality = TrackingDiagnostics.merge(primary_diagnostics, secondary_diagnostics)
                debug_tracking = {
                    "primary": self._build_tracking_debug(primary_diagnostics),
                    "secondary": self._build_tracking_debug(secondary_diagnostics),
                } if os.getenv("DEBUG_RENDER_ARTIFACTS") == "1" else None
            else:
                tracking_quality = primary_diagnostics.to_quality()
                debug_tracking = self._build_tracking_debug(primary_diagnostics)
            if manual_center_x is not None:
                tracking_quality.update(
                    {
                        "status": "good",
                        "mode": "manual",
                        "fallback_frames": 0,
                        "avg_center_jump_px": 0.0,
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
    ) -> tuple[str, str | None]:
        if requested_layout != "split":
            return "single" if requested_layout == "single" else requested_layout, None
        if manual_center_x is not None:
            return "single", "split_not_stable"

        self._ensure_model_loaded()
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            return "single", "split_not_stable"

        duration = max(0.2, end_time - start_time)
        frame_results: list[tuple[int, list[float], int, int]] = []
        try:
            for index in range(SPLIT_SAMPLE_WINDOWS):
                ratio = 0.0 if SPLIT_SAMPLE_WINDOWS == 1 else index / (SPLIT_SAMPLE_WINDOWS - 1)
                sample_time = start_time + (duration * ratio)
                cap.set(cv2.CAP_PROP_POS_MSEC, sample_time * 1000)
                ok, frame = cap.read()
                if not ok:
                    continue
                frame_width = int(frame.shape[1]) if frame.ndim >= 2 else 0
                centers = self._detect_person_centers(frame)
                frame_results.append((frame_width, centers, index, SPLIT_SAMPLE_WINDOWS))
        finally:
            cap.release()

        if self._is_split_layout_stable(frame_results):
            return "split", None
        return "single", "split_not_stable"

    def _detect_person_centers(self, frame: np.ndarray) -> list[float]:
        candidates = self._predict_people(frame)
        if not candidates:
            return []
        ranked = sorted(candidates, key=lambda candidate: candidate.area, reverse=True)[:2]
        return sorted(candidate.center_x for candidate in ranked)

    @staticmethod
    def _is_split_layout_stable(frame_results: list[tuple]) -> bool:
        if not frame_results:
            return False

        stable_positions: list[int] = []
        sampled_frames = 0
        total_windows = frame_results[0][3] if len(frame_results[0]) >= 4 else len(frame_results)
        for index, frame_result in enumerate(frame_results):
            if len(frame_result) >= 4:
                frame_width, centers, sample_index, _sample_total = frame_result
            else:
                frame_width, centers = frame_result[:2]
                sample_index = index
            if frame_width <= 0:
                continue
            sampled_frames += 1
            if len(centers) < 2:
                continue
            separation = abs(centers[1] - centers[0])
            if separation >= frame_width * SPLIT_MIN_SEPARATION_RATIO:
                stable_positions.append(sample_index)

        if sampled_frames == 0:
            return False
        if total_windows >= SPLIT_SAMPLE_WINDOWS:
            if len(stable_positions) < SPLIT_REQUIRED_POSITIVE_WINDOWS:
                return False
            region_hits = {
                "early": any(position <= (total_windows // 3) for position in stable_positions),
                "mid": any((total_windows // 3) < position < (2 * total_windows // 3) for position in stable_positions),
                "late": any(position >= (2 * total_windows // 3) for position in stable_positions),
            }
            return all(region_hits.values())
        return len(stable_positions) >= math.ceil(sampled_frames * 0.5)

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
