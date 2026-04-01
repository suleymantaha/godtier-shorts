"""Media-level helper operations used by orchestration workflows."""

from __future__ import annotations

import json
import locale
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from backend.config import MASTER_AUDIO, MASTER_VIDEO, ProjectPaths
from backend.core.command_runner import CommandRunner
from backend.core.subtitle_timing import (
    canonicalize_transcript_segments,
    collect_valid_words,
    compute_word_coverage_ratio,
    count_normalized_tokens,
    normalize_subtitle_text,
    normalize_word_payload,
    resolve_word_overlaps,
)
from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.video_processor import VideoProcessor

StatusUpdater = Callable[[str, int], None]
YTDLP_PROGRESS_PREFIX = "GTS_DL|"
DOWNLOAD_TOTAL_TIMEOUT_SECONDS = 6 * 60 * 60
DOWNLOAD_ACTIVITY_TIMEOUT_SECONDS = 30 * 60
DOWNLOAD_PROGRESS_MIN_EMIT_INTERVAL_MS = 2000
DOWNLOAD_PROGRESS_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)")
JSON_FALLBACK_ENCODINGS = ("utf-8", "utf-8-sig", "cp1254", "latin-1")


def _read_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _load_json_file(path: str) -> Any:
    raw = Path(path).read_bytes()
    encodings: list[str] = ["utf-8", "utf-8-sig"]
    preferred = locale.getpreferredencoding(False)
    if preferred and preferred.lower() not in {encoding.lower() for encoding in encodings}:
        encodings.append(preferred)
    for fallback in JSON_FALLBACK_ENCODINGS:
        if fallback.lower() not in {encoding.lower() for encoding in encodings}:
            encodings.append(fallback)

    last_error: UnicodeDecodeError | json.JSONDecodeError | None = None
    for encoding in encodings:
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


def _format_bytes_human(num_bytes: int | None) -> str:
    if num_bytes is None or num_bytes < 0:
        return "?"
    value = float(num_bytes)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    precision = 0 if unit_index == 0 else 1
    return f"{value:.{precision}f} {units[unit_index]}"


def _parse_int_token(raw: str) -> int | None:
    stripped = raw.strip()
    if not stripped or stripped == "NA":
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _parse_percent_token(raw: str) -> float | None:
    match = DOWNLOAD_PROGRESS_RE.search(raw)
    if not match:
        return None
    try:
        return float(match.group("value"))
    except ValueError:
        return None


def parse_ytdlp_progress_line(line: str) -> tuple[str, int, dict[str, Any]] | None:
    if not line.startswith(YTDLP_PROGRESS_PREFIX):
        return None

    parts = line.split("|")
    if len(parts) < 8:
        return None

    downloaded_bytes = _parse_int_token(parts[1])
    total_bytes = _parse_int_token(parts[2])
    total_estimate = _parse_int_token(parts[3])
    speed = parts[5].strip()
    eta = parts[6].strip()
    status = parts[7].strip().lower()
    resolved_total = total_bytes or total_estimate

    percent = None
    if downloaded_bytes is not None and resolved_total not in (None, 0):
        percent = max(0.0, min(100.0, downloaded_bytes * 100.0 / resolved_total))
    if percent is None:
        percent = _parse_percent_token(parts[4])
    if percent is None:
        return None

    rounded_percent = round(percent, 1)
    stage_progress = 10 + min(9, max(0, int(percent // 10)))
    detail = f"{_format_bytes_human(downloaded_bytes)} / {_format_bytes_human(resolved_total)}"
    suffix: list[str] = [f"{percent:.1f}%"]
    if speed and speed != "NA":
        suffix.append(speed)
    if eta and eta != "NA":
        suffix.append(f"ETA {eta}")
    if status and status not in {"NA", "finished"}:
        suffix.append(status)

    return (
        f"YouTube indiriliyor: {detail} ({', '.join(suffix)})",
        stage_progress,
        {
            "phase": "download",
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "total_bytes_estimate": total_estimate,
            "percent": rounded_percent,
            "speed_text": speed if speed and speed != "NA" else None,
            "eta_text": eta if eta and eta != "NA" else None,
            "status": status if status and status != "NA" else None,
        },
    )


def build_ytdlp_progress_callback(update_status: StatusUpdater) -> Callable[[str, str], None]:
    last_emitted_percent = -1
    last_emitted_at = 0.0
    min_emit_interval_seconds = _read_positive_int_env(
        "YTDLP_PROGRESS_MIN_EMIT_INTERVAL_MS",
        DOWNLOAD_PROGRESS_MIN_EMIT_INTERVAL_MS,
    ) / 1000.0

    def _handle_output(stream_name: str, line: str) -> None:
        nonlocal last_emitted_at, last_emitted_percent
        if stream_name != "stderr":
            return

        parsed = parse_ytdlp_progress_line(line)
        if parsed is None:
            return

        message, stage_progress, download_progress = parsed
        byte_progress = int(download_progress.get("percent") or 0)
        now = time.monotonic()
        should_emit = (
            byte_progress >= 100
            or byte_progress != last_emitted_percent
            or now - last_emitted_at >= min_emit_interval_seconds
        )
        if not should_emit:
            return

        last_emitted_percent = byte_progress
        last_emitted_at = now
        update_status(message, stage_progress, {
            "download_progress": download_progress,
            "status": "processing",
        })

    return _handle_output


async def download_full_video_async(
    *,
    url: str,
    project_paths: Optional[ProjectPaths],
    resolution: str,
    validate_url: Callable[[str], None],
    update_status: StatusUpdater,
    command_runner: CommandRunner,
) -> tuple[str, str]:
    """Downloads source video/audio into project assets."""
    validate_url(url)
    update_status("YouTube'dan orijinal video indiriliyor...", 10)

    video_file = str(project_paths.master_video if project_paths else MASTER_VIDEO)
    audio_file = str(project_paths.master_audio if project_paths else MASTER_AUDIO)

    if resolution != "best":
        height = "".join(filter(str.isdigit, resolution))
        format_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/mp4"
    else:
        format_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

    progress_callback = build_ytdlp_progress_callback(update_status)
    rc, _stdout, stderr = await command_runner.run_async(
        [
            "yt-dlp",
            "--newline",
            "--progress-template",
            "download:GTS_DL|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(progress.status)s",
            "-f",
            format_str,
            "-o",
            video_file,
            url,
        ],
        timeout=_read_positive_int_env(
            "YTDLP_DOWNLOAD_TOTAL_TIMEOUT_SECONDS",
            DOWNLOAD_TOTAL_TIMEOUT_SECONDS,
        ),
        activity_timeout=_read_positive_int_env(
            "YTDLP_DOWNLOAD_IDLE_TIMEOUT_SECONDS",
            DOWNLOAD_ACTIVITY_TIMEOUT_SECONDS,
        ),
        error_message="Video indirme işlemi uzun süre ilerleme vermediği için durduruldu.",
        on_output=progress_callback,
    )
    if rc != 0 or not os.path.exists(video_file):
        raise RuntimeError(f"Video indirilemedi: {url}\n{stderr}")

    await extract_audio_async(
        video_file=video_file,
        audio_file=audio_file,
        update_status=update_status,
        command_runner=command_runner,
    )
    return video_file, audio_file


async def extract_audio_async(
    *,
    video_file: str,
    audio_file: str,
    update_status: StatusUpdater,
    command_runner: CommandRunner,
) -> str:
    update_status("Video içinden ses ayrıştırılıyor...", 20)
    arc, _astout, astderr = await command_runner.run_async(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_file,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            audio_file,
        ],
        timeout=900,
        error_message="Ses ayrıştırma işlemi timeout oldu (15 dakika)",
    )
    if arc != 0:
        stderr_tail = (astderr or "")[-300:]
        logger.error("Ses ayrıştırma hatası (stderr son 300 karakter): %s", stderr_tail)
        raise RuntimeError(f"Ses ayrıştırılamadı. ffmpeg stderr özeti: {stderr_tail}")
    return audio_file


def shift_timestamps(
    original_json: str,
    start_time: float,
    end_time: float,
    output_json: str,
) -> str:
    """Aligns subtitle timestamps to clip-local timeline."""
    data = _load_json_file(original_json)

    shifted, _report = build_shifted_transcript_segments_with_report(data, start_time, end_time)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(shifted, f, ensure_ascii=False, indent=4)

    return output_json


def shift_timestamps_with_report(
    original_json: str,
    start_time: float,
    end_time: float,
    output_json: str,
) -> dict:
    """Aligns subtitle timestamps and returns transcript quality metrics."""
    data = _load_json_file(original_json)

    shifted, report = build_shifted_transcript_segments_with_report(data, start_time, end_time)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(shifted, f, ensure_ascii=False, indent=4)
    return {
        "path": output_json,
        "segments": shifted,
        "transcript_quality": report,
    }


def build_shifted_transcript_segments(
    data: list[dict],
    start_time: float,
    end_time: float,
) -> list[dict]:
    """Slice transcript data into a clip-local timeline."""
    shifted, _report = build_shifted_transcript_segments_with_report(data, start_time, end_time)
    return shifted


def build_shifted_transcript_segments_with_report(
    data: list[dict],
    start_time: float,
    end_time: float,
) -> tuple[list[dict], dict]:
    """Slice transcript data into a clip-local timeline and collect quality metrics."""
    shifted: list[dict] = []
    duration = end_time - start_time
    clamped_words_count = 0
    reconstructed_segments_count = 0
    text_word_mismatches = 0
    normalized_segments = canonicalize_transcript_segments(data)
    for raw_segment, normalized_segment in zip(data, normalized_segments):
        seg = dict(normalized_segment)
        valid_words = resolve_word_overlaps(
            [
                normalized
                for raw_word in raw_segment.get("words", []) or []
                if (normalized := normalize_word_payload(dict(raw_word))) is not None
            ]
        )
        if valid_words and len(valid_words) > count_normalized_tokens(seg["text"]):
            seg["words"] = valid_words
        if seg["end"] > start_time and seg["start"] < end_time:
            new_start = max(0, seg["start"] - start_time)
            new_end = min(seg["end"] - start_time, duration)

            shifted_words = []
            for word in seg.get("words", []):
                if "start" in word and "end" in word:
                    raw_start = float(word["start"]) - start_time
                    raw_end = float(word["end"]) - start_time
                    ws = max(0.0, raw_start)
                    we = min(raw_end, duration)
                    if raw_start != ws or raw_end != we:
                        clamped_words_count += 1
                    if we > 0 and ws < duration:
                        shifted_words.append(
                            {
                                "word": word["word"],
                                "start": ws,
                                "end": we,
                                "score": word.get("score", 1.0),
                            }
                        )

            if new_end <= new_start:
                continue

            rebuilt_text = " ".join(
                str(word.get("word", "")).strip()
                for word in shifted_words
                if str(word.get("word", "")).strip()
            )
            original_text = str(seg.get("text", "")).strip()
            if shifted_words:
                if normalize_subtitle_text(original_text) and normalize_subtitle_text(original_text) != normalize_subtitle_text(rebuilt_text):
                    text_word_mismatches += 1
                if rebuilt_text and rebuilt_text != original_text:
                    reconstructed_segments_count += 1

            shifted.append(
                {
                    "text": rebuilt_text or seg["text"],
                    "start": new_start,
                    "end": new_end,
                    "speaker": seg.get("speaker", "Bilinmeyen"),
                    "words": shifted_words,
                }
            )

    report = analyze_transcript_segments(
        shifted,
        clamped_words_count=clamped_words_count,
        reconstructed_segments_count=reconstructed_segments_count,
        text_word_mismatches=text_word_mismatches,
    )
    return shifted, report


def analyze_transcript_segments(
    segments: list[dict],
    *,
    clamped_words_count: int = 0,
    reconstructed_segments_count: int = 0,
    text_word_mismatches: int = 0,
) -> dict:
    valid_words = collect_valid_words(segments)
    segments_without_words = 0
    empty_text_segments_after_rebuild = 0
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        segment_words = [
            word for word in segment.get("words", []) or []
            if str(word.get("word", "")).strip()
        ]
        if not segment_words:
            segments_without_words += 1
        if not normalize_subtitle_text(text):
            empty_text_segments_after_rebuild += 1

    return {
        "status": _resolve_transcript_quality_status(
            word_coverage_ratio=compute_word_coverage_ratio(segments),
            segments_without_words=segments_without_words,
            empty_text_segments_after_rebuild=empty_text_segments_after_rebuild,
        ),
        "segments_without_words": segments_without_words,
        "text_word_mismatches": text_word_mismatches,
        "clamped_words_count": clamped_words_count,
        "reconstructed_segments_count": reconstructed_segments_count,
        "empty_text_segments_after_rebuild": empty_text_segments_after_rebuild,
        "word_coverage_ratio": round(compute_word_coverage_ratio(segments), 4),
        "valid_word_tokens": len(valid_words),
        "normalized_text_tokens": sum(count_normalized_tokens(str(segment.get("text", ""))) for segment in segments),
    }


def _resolve_transcript_quality_status(
    *,
    word_coverage_ratio: float,
    segments_without_words: int,
    empty_text_segments_after_rebuild: int,
) -> str:
    if word_coverage_ratio >= 0.80 and segments_without_words == 0 and empty_text_segments_after_rebuild == 0:
        return "good"
    if word_coverage_ratio >= 0.60:
        return "partial"
    return "degraded"


def cut_and_burn_clip(
    *,
    video_processor: VideoProcessor,
    cancel_event: threading.Event,
    master_video: str,
    start_t: float,
    end_t: float,
    temp_cropped: str,
    final_output: str,
    ass_file: str,
    subtitle_engine: Optional[SubtitleRenderer],
    layout: str,
    center_x: Optional[float],
    initial_slot_centers: tuple[float, float] | None = None,
    cut_as_short: bool,
    require_audio: bool = False,
) -> dict:
    """Cuts clip and optionally burns subtitles."""
    render_report: dict = {}
    if cut_as_short:
        try:
            render_report = video_processor.create_viral_short(
                input_video=master_video,
                start_time=start_t,
                end_time=end_t,
                output_filename=temp_cropped,
                smoothness=0.1,
                manual_center_x=center_x,
                layout=layout,
                initial_slot_centers=initial_slot_centers,
                cancel_event=cancel_event,
                require_audio=require_audio,
            )
        finally:
            video_processor.cleanup_gpu()
    else:
        render_report = video_processor.cut_segment_only(
            input_video=master_video,
            start_time=start_t,
            end_time=end_t,
            output_filename=temp_cropped,
            cancel_event=cancel_event,
            require_audio=require_audio,
        )
    if not isinstance(render_report, dict):
        render_report = {}

    if subtitle_engine is not None and Path(ass_file).exists():
        raw_path = final_output.replace(".mp4", "_raw.mp4")
        shutil.copy2(temp_cropped, raw_path)
        subtitle_engine.burn_subtitles_to_video(
            temp_cropped,
            ass_file,
            final_output,
            cancel_event=cancel_event,
        )
    else:
        shutil.move(temp_cropped, final_output)

    if subtitle_engine is not None:
        render_report["subtitle_layout_quality"] = dict(getattr(subtitle_engine, "last_render_report", {}) or {})
    return render_report
