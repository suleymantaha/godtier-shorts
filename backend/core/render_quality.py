"""Render quality scoring, media probes, and environment fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path


def probe_media(path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "")[-300:] or f"ffprobe failed for {path}")
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe JSON parse failed for {path}") from exc


def extract_media_stream_metrics(probe_data: dict) -> dict:
    format_data = probe_data.get("format") if isinstance(probe_data, dict) else {}
    streams = probe_data.get("streams") if isinstance(probe_data, dict) else []
    if not isinstance(format_data, dict):
        format_data = {}
    if not isinstance(streams, list):
        streams = []

    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    raw_fps = str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1")
    fps = _parse_fraction(raw_fps)
    duration = _safe_float(format_data.get("duration"))
    audio_duration = _safe_float(audio_stream.get("duration"), default=duration)
    video_duration = _safe_float(video_stream.get("duration"), default=duration)
    nb_frames = _safe_float(video_stream.get("nb_frames"), default=0.0)

    return {
        "fps": fps,
        "duration": duration,
        "video_duration": video_duration,
        "audio_duration": audio_duration,
        "has_audio": bool(audio_stream),
        "audio_sample_rate": _safe_int(audio_stream.get("sample_rate")),
        "audio_channels": _safe_int(audio_stream.get("channels")),
        "audio_validation_status": _resolve_audio_validation_status(audio_stream, audio_duration),
        "nb_frames": int(nb_frames) if nb_frames > 0 else None,
    }


def build_debug_environment(*, model_identifier: str, model_path: str) -> dict:
    import torch
    import ultralytics

    return {
        "ffmpeg_version": _probe_tool_version(["ffmpeg", "-version"]),
        "ultralytics_version": getattr(ultralytics, "__version__", "unknown"),
        "torch_version": getattr(torch, "__version__", "unknown"),
        "cuda_runtime": torch.version.cuda if torch.cuda.is_available() else None,
        "model_identifier": model_identifier,
        "model_sha256": _sha256_file(model_path),
    }


def compute_render_quality_score(
    *,
    tracking_quality: dict | None,
    transcript_quality: dict | None,
    debug_timing: dict | None,
    subtitle_layout_quality: dict | None,
) -> int:
    tracking_component = _tracking_score_component(tracking_quality)
    transcript_component = _transcript_score_component(transcript_quality)
    timing_component = _timing_score_component(debug_timing)
    subtitle_component = _subtitle_score_component(subtitle_layout_quality or transcript_quality)

    score = (
        (tracking_component * 0.35)
        + (transcript_component * 0.30)
        + (timing_component * 0.20)
        + (subtitle_component * 0.15)
    )

    tracking_status = (tracking_quality or {}).get("status")
    if tracking_status == "fallback":
        score = min(score, 69.0)

    return int(round(max(0.0, min(100.0, score))))


def merge_transcript_quality(
    *,
    base_quality: dict | None,
    subtitle_layout_quality: dict | None,
    snapping_report: dict | None,
) -> dict:
    merged = dict(base_quality or {})
    layout_metrics = subtitle_layout_quality or {}
    merged.update(
        {
            "avg_words_per_chunk": layout_metrics.get("avg_words_per_chunk", merged.get("avg_words_per_chunk", 0.0)),
            "max_chunk_duration": layout_metrics.get("max_chunk_duration", merged.get("max_chunk_duration", 0.0)),
            "subtitle_overflow_detected": bool(layout_metrics.get("subtitle_overflow_detected", merged.get("subtitle_overflow_detected", False))),
            "max_rendered_line_width_ratio": layout_metrics.get("max_rendered_line_width_ratio", merged.get("max_rendered_line_width_ratio", 0.0)),
            "safe_area_violation_count": layout_metrics.get("safe_area_violation_count", merged.get("safe_area_violation_count", 0)),
        }
    )
    if snapping_report:
        merged["boundary_snaps_applied"] = int(snapping_report.get("boundary_snaps_applied", 0) or 0)
        merged["word_coverage_ratio"] = snapping_report.get("word_coverage_ratio", merged.get("word_coverage_ratio", 0.0))

    coverage_ratio = float(merged.get("word_coverage_ratio", 0.0) or 0.0)
    overflow = bool(merged.get("subtitle_overflow_detected"))
    empty_segments = int(merged.get("empty_text_segments_after_rebuild", 0) or 0)
    if overflow or empty_segments > 0 or coverage_ratio < 0.60:
        merged["status"] = "degraded"
    elif coverage_ratio < 0.80 or int(merged.get("segments_without_words", 0) or 0) > 0:
        merged["status"] = "partial"
    else:
        merged["status"] = "good"
    return merged


def _tracking_score_component(tracking_quality: dict | None) -> float:
    if not tracking_quality:
        return 50.0
    status = tracking_quality.get("status")
    base = 92.0 if status == "good" else 72.0 if status == "degraded" else 56.0
    fallback_frames = float(tracking_quality.get("fallback_frames", 0.0) or 0.0)
    total_frames = float(tracking_quality.get("total_frames", 0.0) or 0.0)
    fallback_ratio = fallback_frames / total_frames if total_frames > 0 else 0.0
    avg_center_jump = float(tracking_quality.get("avg_center_jump_px", 0.0) or 0.0)
    penalty = min(26.0, fallback_ratio * 45.0) + min(18.0, avg_center_jump / 18.0)
    return max(0.0, min(100.0, base - penalty))


def _transcript_score_component(transcript_quality: dict | None) -> float:
    if not transcript_quality:
        return 50.0
    status = transcript_quality.get("status")
    base = 94.0 if status == "good" else 76.0 if status == "partial" else 54.0
    coverage = float(transcript_quality.get("word_coverage_ratio", 0.0) or 0.0)
    clamp_count = float(transcript_quality.get("clamped_words_count", 0.0) or 0.0)
    empty_segments = float(transcript_quality.get("empty_text_segments_after_rebuild", 0.0) or 0.0)
    penalty = max(0.0, (0.80 - coverage) * 35.0) + min(15.0, clamp_count * 0.8) + min(18.0, empty_segments * 4.0)
    return max(0.0, min(100.0, base - penalty))


def _timing_score_component(debug_timing: dict | None) -> float:
    if not debug_timing:
        return 50.0
    drift_ms = abs(float(debug_timing.get("merged_output_drift_ms", 0.0) or 0.0))
    drop_estimate = abs(float(debug_timing.get("dropped_or_duplicated_frame_estimate", 0.0) or 0.0))
    base = 96.0
    penalty = min(70.0, drift_ms / 2.5) + min(18.0, drop_estimate * 0.75)
    return max(0.0, min(100.0, base - penalty))


def _subtitle_score_component(subtitle_quality: dict | None) -> float:
    if not subtitle_quality:
        return 50.0
    overflow = bool(subtitle_quality.get("subtitle_overflow_detected"))
    safe_area_violations = float(subtitle_quality.get("safe_area_violation_count", 0.0) or 0.0)
    width_ratio = float(subtitle_quality.get("max_rendered_line_width_ratio", 0.0) or 0.0)
    base = 96.0 if not overflow else 72.0
    penalty = min(24.0, safe_area_violations * 8.0) + max(0.0, (width_ratio - 0.92) * 22.0)
    return max(0.0, min(100.0, base - penalty))


def _resolve_audio_validation_status(audio_stream: dict, audio_duration: float) -> str:
    if not audio_stream:
        return "missing"
    if audio_duration <= 0:
        return "invalid"
    if _safe_int(audio_stream.get("channels")) <= 0 or _safe_int(audio_stream.get("sample_rate")) <= 0:
        return "invalid"
    return "ok"


def _probe_tool_version(cmd: list[str]) -> str | None:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    except Exception:
        return None
    first_line = (completed.stdout or completed.stderr or "").splitlines()
    return first_line[0].strip() if first_line else None


@lru_cache(maxsize=8)
def _sha256_file(path: str) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_fraction(raw_value: str) -> float:
    if "/" not in raw_value:
        return _safe_float(raw_value)
    numerator_raw, denominator_raw = raw_value.split("/", 1)
    denominator = _safe_float(denominator_raw, default=1.0)
    if denominator == 0:
        return 0.0
    return _safe_float(numerator_raw) / denominator


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
