#!/usr/bin/env python3
"""Run subtitle style smoke/full render matrix and emit a single JSON report."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.core.orchestrator import GodTierShortsCreator
from backend.core.workflow_runtime import create_subtitle_renderer
from backend.services.subtitle_styles import StyleManager


DEFAULT_PROJECT_ID = "yt_-hL25diakQc"
DEFAULT_CLIP_JSON = (
    "workspace/projects/yt_-hL25diakQc/shorts/manual_manual_1773514300.json"
)
DEFAULT_SMOKE_SECONDS = 20.0
DEFAULT_FULL_START = 1054.9
DEFAULT_FULL_DURATION = 120.0
DEFAULT_ANIMATIONS = ("default", "pop", "slide_up", "typewriter")
DEFAULT_SMOKE_COMBOS = (
    ("single", "default"),
    ("single", "lower_third_safe"),
    ("split", "default"),
)


@dataclass
class SmokeResult:
    style_name: str
    layout: str
    safe_area_profile: str
    output_video: str
    status: str
    error: str | None = None
    subtitle_overflow_detected: bool | None = None
    max_rendered_line_width_ratio: float | None = None
    safe_area_violation_count: int | None = None
    simultaneous_event_overlap_count: int | None = None
    max_simultaneous_events: int | None = None
    overflow_strategy: str | None = None
    font_clamp_count: int | None = None
    burn_encoder: str | None = None
    nvenc_fallback_used: bool | None = None


@dataclass
class FullRenderResult:
    animation_type: str
    output_video: str
    output_json: str
    status: str
    error: str | None = None
    resolved_layout: str | None = None
    render_quality_score: int | None = None
    transcript_status: str | None = None
    subtitle_overflow_detected: bool | None = None
    max_rendered_line_width_ratio: float | None = None
    safe_area_violation_count: int | None = None
    overflow_strategy: str | None = None
    burn_encoder: str | None = None
    nvenc_fallback_used: bool | None = None
    duration_seconds: float | None = None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _probe_duration(video_path: Path) -> float | None:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(video_path),
    ]
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return round(float(completed.stdout.strip()), 3)
    except Exception:
        return None


def _slice_transcript(segments: list[dict[str, Any]], max_seconds: float) -> list[dict[str, Any]]:
    sliced: list[dict[str, Any]] = []
    for segment in segments:
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", 0.0))
        if end <= 0.0 or start >= max_seconds:
            continue
        if end <= start:
            continue
        words = []
        for word in segment.get("words", []):
            word_start = float(word.get("start", 0.0))
            word_end = float(word.get("end", 0.0))
            if word_end <= 0.0 or word_start >= max_seconds:
                continue
            clipped_start = max(0.0, word_start)
            clipped_end = min(max_seconds, word_end)
            if clipped_end <= clipped_start:
                continue
            words.append(
                {
                    **word,
                    "start": clipped_start,
                    "end": clipped_end,
                }
            )
        if not words:
            continue
        clipped_start = max(0.0, start)
        clipped_end = min(max_seconds, end)
        text = " ".join(str(word.get("word", "")).strip() for word in words).strip()
        sliced.append(
            {
                "text": text,
                "start": clipped_start,
                "end": clipped_end,
                "words": words,
            }
        )
    return sliced


def _resolve_paths(repo_root: Path, clip_json_rel: str) -> tuple[Path, Path, Path]:
    clip_json_path = (repo_root / clip_json_rel).resolve()
    if not clip_json_path.exists():
        raise FileNotFoundError(f"Clip JSON not found: {clip_json_path}")
    clip_stem = clip_json_path.stem
    raw_video_path = clip_json_path.with_name(f"{clip_stem}_raw.mp4")
    if not raw_video_path.exists():
        raise FileNotFoundError(f"Raw clip video not found: {raw_video_path}")
    transcript_smoke_path = clip_json_path.with_name(f"{clip_stem}_smoke_transcript.json")
    return clip_json_path, raw_video_path, transcript_smoke_path


def _resolve_project_output_dir(repo_root: Path, project_id: str) -> Path:
    direct = repo_root / "workspace" / "projects" / project_id / "shorts"
    if direct.exists():
        return direct

    nested_matches = list((repo_root / "workspace" / "projects").glob(f"*/{project_id}/shorts"))
    if nested_matches:
        return nested_matches[0]

    raise FileNotFoundError(
        f"Could not resolve project shorts directory for project_id={project_id}. "
        "Expected workspace/projects/<project_id>/shorts or workspace/projects/<subject>/<project_id>/shorts."
    )


def _build_smoke_source(raw_video_path: Path, smoke_source_path: Path, smoke_seconds: float) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0",
            "-t",
            f"{smoke_seconds:.3f}",
            "-i",
            str(raw_video_path),
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p6",
            "-b:v",
            "8M",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(smoke_source_path),
        ]
    )


def run_smoke_matrix(
    *,
    smoke_source_path: Path,
    transcript_smoke_path: Path,
    output_dir: Path,
    max_words_per_screen: int = 3,
) -> tuple[list[SmokeResult], list[dict[str, Any]]]:
    styles = StyleManager.list_presets()
    results: list[SmokeResult] = []

    for style_name in styles:
        for layout, safe_area_profile in DEFAULT_SMOKE_COMBOS:
            output_path = output_dir / f"smoke_{style_name}_{layout}_{safe_area_profile}.mp4"
            ass_path = output_dir / f"smoke_{style_name}_{layout}_{safe_area_profile}.ass"
            renderer = create_subtitle_renderer(
                style_name,
                animation_type="default",
                canvas_width=1080,
                canvas_height=1920,
                layout=layout,
                safe_area_profile=safe_area_profile,
                lower_third_detection={
                    "lower_third_collision_detected": safe_area_profile == "lower_third_safe",
                    "lower_third_band_height_ratio": 0.14 if safe_area_profile == "lower_third_safe" else 0.0,
                },
            )
            try:
                renderer.generate_ass_file(
                    str(transcript_smoke_path),
                    str(ass_path),
                    max_words_per_screen=max_words_per_screen,
                )
                renderer.burn_subtitles_to_video(
                    str(smoke_source_path),
                    str(ass_path),
                    str(output_path),
                )
                report = renderer.last_render_report
                results.append(
                    SmokeResult(
                        style_name=style_name,
                        layout=layout,
                        safe_area_profile=safe_area_profile,
                        output_video=str(output_path),
                        status="ok",
                        subtitle_overflow_detected=report.get("subtitle_overflow_detected"),
                        max_rendered_line_width_ratio=report.get("max_rendered_line_width_ratio"),
                        safe_area_violation_count=report.get("safe_area_violation_count"),
                        simultaneous_event_overlap_count=report.get("simultaneous_event_overlap_count"),
                        max_simultaneous_events=report.get("max_simultaneous_events"),
                        overflow_strategy=report.get("overflow_strategy"),
                        font_clamp_count=report.get("font_clamp_count"),
                        burn_encoder=report.get("burn_encoder"),
                        nvenc_fallback_used=report.get("nvenc_fallback_used"),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    SmokeResult(
                        style_name=style_name,
                        layout=layout,
                        safe_area_profile=safe_area_profile,
                        output_video=str(output_path),
                        status="failed",
                        error=str(exc),
                    )
                )

    problems: list[dict[str, Any]] = []
    for result in results:
        if result.status != "ok":
            problems.append(asdict(result))
            continue
        if bool(result.subtitle_overflow_detected):
            problems.append(asdict(result))
            continue
        if (result.safe_area_violation_count or 0) > 0:
            problems.append(asdict(result))
            continue
        if (result.simultaneous_event_overlap_count or 0) > 0:
            problems.append(asdict(result))
            continue
    return results, problems


def run_full_animation_matrix(
    *,
    subject_id: str,
    project_id: str,
    start_t: float,
    duration: float,
    style_name: str,
    output_dir: Path,
) -> tuple[list[FullRenderResult], list[dict[str, Any]]]:
    creator = GodTierShortsCreator(subject=subject_id)
    end_t = start_t + duration
    results: list[FullRenderResult] = []

    for animation_type in DEFAULT_ANIMATIONS:
        output_name = f"matrix_single_{animation_type}_{int(duration)}s.mp4"
        output_video_path = output_dir / output_name
        output_json_path = output_video_path.with_suffix(".json")
        try:
            rendered_path = creator.run_manual_clip(
                start_t=start_t,
                end_t=end_t,
                transcript_data=None,
                project_id=project_id,
                style_name=style_name,
                animation_type=animation_type,
                layout="single",
                output_name=output_name,
                skip_subtitles=False,
                cut_as_short=True,
            )
            metadata = json.loads(output_json_path.read_text(encoding="utf-8"))["render_metadata"]
            transcript_quality = metadata.get("transcript_quality") or {}
            subtitle_layout_quality = metadata.get("subtitle_layout_quality") or {}
            results.append(
                FullRenderResult(
                    animation_type=animation_type,
                    output_video=rendered_path,
                    output_json=str(output_json_path),
                    status="ok",
                    resolved_layout=metadata.get("resolved_layout"),
                    render_quality_score=metadata.get("render_quality_score"),
                    transcript_status=transcript_quality.get("status"),
                    subtitle_overflow_detected=transcript_quality.get("subtitle_overflow_detected"),
                    max_rendered_line_width_ratio=transcript_quality.get("max_rendered_line_width_ratio"),
                    safe_area_violation_count=transcript_quality.get("safe_area_violation_count"),
                    overflow_strategy=subtitle_layout_quality.get("overflow_strategy"),
                    burn_encoder=subtitle_layout_quality.get("burn_encoder"),
                    nvenc_fallback_used=subtitle_layout_quality.get("nvenc_fallback_used"),
                    duration_seconds=_probe_duration(Path(rendered_path)),
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                FullRenderResult(
                    animation_type=animation_type,
                    output_video=str(output_video_path),
                    output_json=str(output_json_path),
                    status="failed",
                    error=str(exc),
                )
            )

    problems: list[dict[str, Any]] = []
    for result in results:
        if result.status != "ok":
            problems.append(asdict(result))
            continue
        if result.resolved_layout != "single":
            problems.append(asdict(result))
            continue
        if bool(result.subtitle_overflow_detected):
            problems.append(asdict(result))
            continue
        if (result.safe_area_violation_count or 0) > 0:
            problems.append(asdict(result))
            continue
        if bool(result.nvenc_fallback_used):
            problems.append(asdict(result))
            continue
    return results, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Run subtitle style/animation render matrix.")
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--full-project-id", default=None)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--style-name", default="HORMOZI")
    parser.add_argument("--clip-json", default=DEFAULT_CLIP_JSON)
    parser.add_argument("--smoke-seconds", type=float, default=DEFAULT_SMOKE_SECONDS)
    parser.add_argument("--full-start", type=float, default=DEFAULT_FULL_START)
    parser.add_argument("--full-duration", type=float, default=DEFAULT_FULL_DURATION)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = repo_root / "workspace" / "logs" / "render_matrix"
    temp_dir = repo_root / "workspace" / "temp"
    log_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    full_project_id = args.full_project_id or args.project_id

    clip_json_path, raw_video_path, transcript_smoke_path = _resolve_paths(repo_root, args.clip_json)
    smoke_output_dir = clip_json_path.parent
    full_output_dir = _resolve_project_output_dir(repo_root, full_project_id)
    clip_payload = json.loads(clip_json_path.read_text(encoding="utf-8"))
    segments = clip_payload.get("transcript") or []
    smoke_segments = _slice_transcript(segments, args.smoke_seconds)
    transcript_smoke_path.write_text(
        json.dumps(smoke_segments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    smoke_source_path = temp_dir / f"matrix_source_{timestamp}.mp4"
    _build_smoke_source(raw_video_path, smoke_source_path, args.smoke_seconds)

    smoke_results, smoke_problems = run_smoke_matrix(
        smoke_source_path=smoke_source_path,
        transcript_smoke_path=transcript_smoke_path,
        output_dir=smoke_output_dir,
    )
    full_results, full_problems = run_full_animation_matrix(
        subject_id=args.subject_id,
        project_id=full_project_id,
        start_t=args.full_start,
        duration=args.full_duration,
        style_name=args.style_name,
        output_dir=full_output_dir,
    )

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "project_id": args.project_id,
        "full_project_id": full_project_id,
        "subject_id": args.subject_id,
        "style_name": args.style_name,
        "clip_json": str(clip_json_path),
        "smoke_output_dir": str(smoke_output_dir),
        "full_output_dir": str(full_output_dir),
        "smoke_seconds": args.smoke_seconds,
        "full_start": args.full_start,
        "full_duration": args.full_duration,
        "style_matrix": {
            "combos": [f"{layout}/{profile}" for layout, profile in DEFAULT_SMOKE_COMBOS],
            "styles": StyleManager.list_presets(),
            "results": [asdict(result) for result in smoke_results],
            "problematic": smoke_problems,
        },
        "animation_matrix": {
            "animations": list(DEFAULT_ANIMATIONS),
            "results": [asdict(result) for result in full_results],
            "problematic": full_problems,
        },
        "problematic_total": len(smoke_problems) + len(full_problems),
    }

    report_path = log_dir / f"subtitle_render_matrix_{args.project_id}_{timestamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(report_path))
    print(f"style_matrix_total={len(smoke_results)} style_matrix_problematic={len(smoke_problems)}")
    print(f"animation_matrix_total={len(full_results)} animation_matrix_problematic={len(full_problems)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
