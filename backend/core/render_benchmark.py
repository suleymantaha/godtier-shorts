"""Determinism and performance benchmarking helpers for clip renders."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import cv2

from backend.config import LOGS_DIR, TEMP_DIR, ProjectPaths
from backend.core.media_ops import analyze_transcript_segments, cut_and_burn_clip
from backend.core.render_quality import (
    build_debug_environment,
    compute_render_quality_score,
    merge_transcript_quality,
)
from backend.core.workflow_helpers import TempArtifactManager, write_json_atomic
from backend.core.workflow_runtime import create_subtitle_renderer, resolve_subtitle_render_plan
from backend.services.subtitle_styles import StyleManager
from backend.services.video_processor import VideoProcessor

DEFAULT_BENCHMARK_RUNS = 3
DEFAULT_BENCHMARK_SAMPLES = 5


def select_sample_times(duration: float, *, sample_count: int = DEFAULT_BENCHMARK_SAMPLES) -> list[float]:
    safe_duration = max(0.01, float(duration or 0.0))
    safe_count = max(1, int(sample_count))
    if safe_count == 1:
        return [round(min(0.01, safe_duration), 3)]

    ratios = [(index + 1) / (safe_count + 1) for index in range(safe_count)]
    sample_times: list[float] = []
    for ratio in ratios:
        sample = round(min(max(ratio * safe_duration, 0.0), max(0.0, safe_duration - 0.01)), 3)
        if not sample_times or sample != sample_times[-1]:
            sample_times.append(sample)
    return sample_times or [0.0]


def normalize_render_metadata_for_comparison(render_metadata: dict | None) -> dict:
    normalized = deepcopy(render_metadata or {})
    normalized.pop("debug_artifacts", None)
    return normalized


def compute_video_frame_hashes(video_path: str, sample_times: list[float]) -> dict[str, str | None]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Benchmark frame hash için video açılamadı: {video_path}")

    try:
        frame_hashes: dict[str, str | None] = {}
        for sample_time in sample_times:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(sample_time) * 1000.0)
            ok, frame = cap.read()
            key = f"{float(sample_time):.3f}"
            frame_hashes[key] = hashlib.sha256(frame.tobytes()).hexdigest() if ok else None
        return frame_hashes
    finally:
        cap.release()


def compare_benchmark_runs(runs: list[dict[str, Any]]) -> dict[str, bool]:
    if not runs:
        return {
            "deterministic": False,
            "frame_hash_matches": False,
            "metadata_matches": False,
        }

    baseline_hashes = runs[0].get("frame_hashes", {})
    baseline_metadata = runs[0].get("normalized_metadata", {})
    frame_hash_matches = all(run.get("frame_hashes", {}) == baseline_hashes for run in runs[1:])
    metadata_matches = all(run.get("normalized_metadata", {}) == baseline_metadata for run in runs[1:])
    return {
        "deterministic": frame_hash_matches and metadata_matches,
        "frame_hash_matches": frame_hash_matches,
        "metadata_matches": metadata_matches,
    }


def render_existing_clip_to_temp_output(
    *,
    project_id: str,
    clip_name: str,
    output_path: str,
    video_processor: VideoProcessor,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    project = ProjectPaths(project_id)
    metadata_path = project.outputs / clip_name.replace(".mp4", ".json")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Clip metadata bulunamadı: {metadata_path}")

    payload = _load_clip_payload(metadata_path)
    transcript = payload.get("transcript", [])
    render_metadata = payload.get("render_metadata", {})
    if not isinstance(transcript, list):
        transcript = []
    if not isinstance(render_metadata, dict):
        render_metadata = {}

    start_t = float(render_metadata.get("start_time", 0.0) or 0.0)
    end_t = float(render_metadata.get("end_time", start_t) or start_t)
    if end_t <= start_t:
        raise ValueError(f"Benchmark için geçersiz clip aralığı: {clip_name}")

    style_name = str(render_metadata.get("style_name") or "HORMOZI")
    animation_type = str(render_metadata.get("animation_type") or "default")
    cut_as_short = bool(render_metadata.get("cut_as_short", True))
    requested_layout = str(render_metadata.get("resolved_layout") or render_metadata.get("layout") or "single")
    center_x_raw = render_metadata.get("center_x")
    center_x = float(center_x_raw) if isinstance(center_x_raw, (int, float)) else None
    skip_subtitles = bool(render_metadata.get("skip_subtitles", False))
    require_audio = bool(render_metadata.get("audio_validation", {}).get("has_audio")) if isinstance(render_metadata.get("audio_validation"), dict) else False

    source_video = str(project.master_video if project.master_video.exists() else project.outputs / clip_name)
    render_plan = resolve_subtitle_render_plan(
        video_processor=video_processor,
        source_video=source_video,
        start_t=start_t,
        end_t=end_t,
        requested_layout=requested_layout,
        cut_as_short=cut_as_short,
        manual_center_x=center_x,
    )
    resolved_style = StyleManager.resolve_style(style_name, animation_type)
    subtitle_engine = None
    temp_json = str(TEMP_DIR / f"bench_{uuid.uuid4().hex[:8]}.json")
    ass_file = str(TEMP_DIR / f"bench_{uuid.uuid4().hex[:8]}.ass")
    temp_cropped = str(TEMP_DIR / f"bench_{uuid.uuid4().hex[:8]}.mp4")
    temp_raw = output_path.replace(".mp4", "_raw.mp4")
    base_transcript_quality = analyze_transcript_segments(transcript)

    if not skip_subtitles:
        subtitle_engine = create_subtitle_renderer(
            style_name,
            animation_type=animation_type,
            canvas_width=render_plan.canvas_width,
            canvas_height=render_plan.canvas_height,
            layout=render_plan.resolved_layout,
            safe_area_profile=render_plan.safe_area_profile,
            lower_third_detection={
                "lower_third_collision_detected": render_plan.lower_third_collision_detected,
                "lower_third_band_height_ratio": render_plan.lower_third_band_height_ratio,
            },
        )

    with TempArtifactManager(temp_json, ass_file, temp_cropped, temp_raw) as artifacts:
        if not skip_subtitles and subtitle_engine is not None:
            artifacts.add(ass_file)

        write_json_atomic(Path(temp_json), transcript)
        if subtitle_engine is not None:
            subtitle_engine.generate_ass_file(temp_json, ass_file, max_words_per_screen=3)

        render_report = cut_and_burn_clip(
            video_processor=video_processor,
            cancel_event=cancel_event or threading.Event(),
            master_video=source_video,
            start_t=start_t,
            end_t=end_t,
            temp_cropped=temp_cropped,
            final_output=output_path,
            ass_file=ass_file,
            subtitle_engine=subtitle_engine,
            layout=render_plan.resolved_layout,
            center_x=center_x,
            cut_as_short=cut_as_short,
            require_audio=require_audio,
        )
        if isinstance(render_report, dict):
            artifacts.add(render_report.get("debug_overlay_temp_path"))

    subtitle_layout_quality = render_report.get("subtitle_layout_quality") if isinstance(render_report, dict) else None
    transcript_quality = merge_transcript_quality(
        base_quality=base_transcript_quality,
        subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
        snapping_report=None,
    )
    tracking_quality = render_report.get("tracking_quality") if isinstance(render_report, dict) else None
    debug_timing = render_report.get("debug_timing") if isinstance(render_report, dict) else None
    debug_environment = build_debug_environment(
        model_identifier=os.path.basename(str(video_processor._model_path)),
        model_path=str(video_processor._model_path),
    )
    computed_score = compute_render_quality_score(
        tracking_quality=tracking_quality if isinstance(tracking_quality, dict) else None,
        transcript_quality=transcript_quality,
        debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
        subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
    )
    normalized_metadata = {
        **render_metadata,
        "project_id": project.root.name,
        "clip_name": clip_name,
        "resolved_layout": render_plan.resolved_layout,
        "layout_fallback_reason": render_plan.layout_fallback_reason,
        "style_name": style_name,
        "animation_type": animation_type,
        "resolved_animation_type": resolved_style.animation_type,
        "tracking_quality": tracking_quality,
        "transcript_quality": transcript_quality,
        "debug_timing": debug_timing,
        "debug_tracking": render_report.get("debug_tracking") if isinstance(render_report, dict) else None,
        "debug_environment": debug_environment,
        "render_quality_score": computed_score,
        "audio_validation": render_report.get("audio_validation") if isinstance(render_report, dict) else None,
        "subtitle_layout_quality": subtitle_layout_quality,
    }

    return {
        "output_path": output_path,
        "render_metadata": normalized_metadata,
        "debug_environment": debug_environment,
    }


def run_benchmark(
    *,
    project_id: str,
    clip_name: str,
    run_count: int = DEFAULT_BENCHMARK_RUNS,
    sample_count: int = DEFAULT_BENCHMARK_SAMPLES,
    keep_outputs: bool = False,
) -> dict[str, Any]:
    benchmark_runs: list[dict[str, Any]] = []
    report_dir = LOGS_DIR / "render_benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)

    total_wall_ms = 0.0
    total_expected_frames = 0.0
    output_paths: list[str] = []

    try:
        for run_index in range(max(1, int(run_count))):
            output_path = str(TEMP_DIR / f"bench_{Path(clip_name).stem}_{run_index}_{uuid.uuid4().hex[:8]}.mp4")
            output_paths.append(output_path)
            video_processor = VideoProcessor()
            started_at = time.perf_counter()
            try:
                result = render_existing_clip_to_temp_output(
                    project_id=project_id,
                    clip_name=clip_name,
                    output_path=output_path,
                    video_processor=video_processor,
                )
            finally:
                video_processor.cleanup_gpu()
            wall_ms = (time.perf_counter() - started_at) * 1000.0
            total_wall_ms += wall_ms
            render_metadata = result.get("render_metadata", {})
            debug_timing = render_metadata.get("debug_timing", {}) if isinstance(render_metadata, dict) else {}
            output_duration = float(render_metadata.get("end_time", 0.0) or 0.0) - float(render_metadata.get("start_time", 0.0) or 0.0)
            normalized_fps = float(debug_timing.get("normalized_fps", 0.0) or 0.0)
            total_expected_frames += max(0.0, output_duration * normalized_fps)

            sample_times = select_sample_times(output_duration or float(debug_timing.get("merged_output_duration", 0.0) or 0.0), sample_count=sample_count)
            frame_hashes = compute_video_frame_hashes(output_path, sample_times)
            benchmark_runs.append(
                {
                    "frame_hashes": frame_hashes,
                    "normalized_metadata": normalize_render_metadata_for_comparison(render_metadata if isinstance(render_metadata, dict) else {}),
                    "render_wall_ms": round(wall_ms, 3),
                }
            )

        comparison = compare_benchmark_runs(benchmark_runs)
        report_path = report_dir / f"{project_id}_{Path(clip_name).stem}_{int(time.time())}.json"
        throughput_fps = (total_expected_frames / (total_wall_ms / 1000.0)) if total_wall_ms > 0 else 0.0
        report = {
            "project_id": project_id,
            "clip_name": clip_name,
            "deterministic": comparison["deterministic"],
            "run_count": len(benchmark_runs),
            "render_wall_ms": round(total_wall_ms, 3),
            "throughput_fps": round(throughput_fps, 3),
            "frame_hash_matches": comparison["frame_hash_matches"],
            "metadata_matches": comparison["metadata_matches"],
            "rss_mb_peak": round(read_peak_rss_mb(), 3),
            "debug_environment": render_existing_debug_environment(benchmark_runs),
            "runs": benchmark_runs,
        }
        write_json_atomic(report_path, report)
        report["report_path"] = str(report_path)
        return report
    finally:
        if not keep_outputs:
            for output_path in output_paths:
                try:
                    os.remove(output_path)
                except FileNotFoundError:
                    continue
                except OSError:
                    continue


def read_peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return float(usage.ru_maxrss) / 1024.0


def render_existing_debug_environment(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not runs:
        return None
    first_metadata = runs[0].get("normalized_metadata", {})
    return first_metadata.get("debug_environment") if isinstance(first_metadata, dict) else None


def _load_clip_payload(metadata_path: Path) -> dict[str, Any]:
    with metadata_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return {
            "transcript": payload,
            "render_metadata": {},
        }
    if isinstance(payload, dict):
        return {
            "transcript": payload.get("transcript", []),
            "render_metadata": payload.get("render_metadata", {}),
        }
    return {
        "transcript": [],
        "render_metadata": {},
    }
