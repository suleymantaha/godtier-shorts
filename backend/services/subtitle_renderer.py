"""
backend/services/subtitle_renderer.py
=======================================
Kinetik altyazi olusturma ve videoya yazma servisi.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from backend.config import LOGS_DIR
from backend.core.external_tools import ffmpeg as resolve_ffmpeg
from backend.core.render_quality import extract_media_stream_metrics, probe_media
from backend.core.subtitle_timing import (
    DEFAULT_MAX_CHUNK_DURATION,
    DEFAULT_MAX_WORDS_PER_SCREEN,
    average_chunk_words,
    build_chunk_payload,
    canonicalize_transcript_segments,
    chunk_words,
    collect_valid_words,
    get_chunk_duration,
    normalize_subtitle_text,
)
from backend.services.subtitle_styles import (
    LOGICAL_CANVAS_HEIGHT,
    LOGICAL_CANVAS_WIDTH,
    ResolvedSubtitleRenderSpec,
    StyleManager,
    SubtitleStyle,
)

logger.add(
    str(LOGS_DIR / "renderer_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)

SPLIT_MAX_WORDS_PER_SCREEN = 2
SPLIT_SOFT_WRAP_RATIO = 0.92
SPLIT_HARD_OVERFLOW_RATIO = 1.0
SINGLE_MIN_FONT_SCALE = 0.72
SPLIT_MIN_FONT_SCALE = 0.82
SPLIT_FONT_CLAMP_MARGIN = 0.995
SMALL_GAP_BRIDGE_THRESHOLD = 0.18
NARROW_CHARACTERS = set("ilı!:;'|")
WIDE_LOWER_CHARACTERS = set("mw")
PUNCTUATION_CHARACTERS = set(".,?")


class SubtitleRenderer:
    @staticmethod
    def _count_simultaneous_event_overlaps(intervals: list[tuple[float, float]]) -> tuple[int, int]:
        events: list[tuple[float, int]] = []
        for start, end in intervals:
            if end <= start:
                continue
            events.append((start, 1))
            events.append((end, -1))
        events.sort(key=lambda item: (item[0], item[1]))

        active = 0
        max_active = 0
        overlap_samples = 0
        previous_time: float | None = None
        for timestamp, delta in events:
            if previous_time is not None and timestamp > previous_time and active > 1:
                overlap_samples += 1
            active += delta
            max_active = max(max_active, active)
            previous_time = timestamp
        simultaneous_overlap_count = max(0, max_active - 1)
        return simultaneous_overlap_count, max_active

    @staticmethod
    def _run_command_with_cancel(
        cmd: list[str],
        *,
        timeout: float,
        cancel_event: threading.Event | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
                raise RuntimeError("Altyazi burn işlemi timeout oldu (10 dakika)")
            time.sleep(0.5)

    def __init__(
        self,
        style: SubtitleStyle,
        *,
        canvas_width: int = LOGICAL_CANVAS_WIDTH,
        canvas_height: int = LOGICAL_CANVAS_HEIGHT,
        layout: str = "single",
        safe_area_profile: str = "default",
        lower_third_detection: dict[str, object] | None = None,
    ):
        self.style = style
        self.lower_third_detection = {
            "lower_third_collision_detected": bool((lower_third_detection or {}).get("lower_third_collision_detected", False)),
            "lower_third_band_height_ratio": round(float((lower_third_detection or {}).get("lower_third_band_height_ratio", 0.0) or 0.0), 4),
        }
        self.spec: ResolvedSubtitleRenderSpec = StyleManager.resolve_render_spec(
            style,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            layout=layout,
            safe_area_profile=safe_area_profile,
        )
        logger.info(
            "Kinetik Altyazi Motoru baslatildi. Stil={} layout={} canvas={}x{} safe_area_profile={}",
            style.name,
            self.spec.canvas.layout,
            self.spec.canvas.width,
            self.spec.canvas.height,
            self.spec.safe_area.profile,
        )
        self.last_render_report: dict[str, object] = self._build_base_render_report()

    def _build_base_render_report(self) -> dict[str, object]:
        return {
            "resolved_safe_area_profile": self.spec.safe_area.profile,
            "lower_third_collision_detected": self.lower_third_detection["lower_third_collision_detected"],
            "lower_third_band_height_ratio": self.lower_third_detection["lower_third_band_height_ratio"],
        }

    @staticmethod
    def _tail_text(text: str, limit: int = 1000) -> str:
        return text[-limit:] if len(text) > limit else text

    @staticmethod
    def _looks_like_nvenc_failure(stderr: str) -> bool:
        lowered = stderr.lower()
        return "cuda" in lowered or "nvenc" in lowered or "hwaccel" in lowered

    @staticmethod
    def _summarize_nvenc_failure(stderr: str) -> str:
        lowered = stderr.lower()
        if "cannot load libcuda" in lowered or "libcuda.so" in lowered:
            return "cuda_runtime_unavailable"
        if "no capable devices found" in lowered or "no nvenc capable devices found" in lowered:
            return "nvenc_device_unavailable"
        if "driver does not support" in lowered or "minimum required driver" in lowered:
            return "driver_incompatible"
        if "out of memory" in lowered:
            return "nvenc_oom"
        if "cuda" in lowered:
            return "cuda_error"
        if "nvenc" in lowered:
            return "nvenc_error"
        return "unknown"

    @staticmethod
    def _probe_video_forensics(video_path: str) -> dict[str, Any]:
        try:
            probe = probe_media(video_path)
            metrics = extract_media_stream_metrics(probe)
        except Exception:
            return {}

        streams = probe.get("streams") if isinstance(probe, dict) else []
        if not isinstance(streams, list):
            streams = []
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})

        return {
            "burn_input_codec": video_stream.get("codec_name"),
            "burn_input_width": int(video_stream.get("width", 0) or 0) or None,
            "burn_input_height": int(video_stream.get("height", 0) or 0) or None,
            "burn_input_fps": round(float(metrics.get("fps", 0.0) or 0.0), 4),
        }

    def _format_time_ass(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int(round((seconds - int(seconds)) * 100))
        if centiseconds >= 100:
            secs += 1
            centiseconds = 0
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _generate_ass_header(self) -> str:
        style = self.spec.style
        safe_area = self.spec.safe_area
        is_opaque_box = style.background_color.upper() != "&H00000000"
        border_style = 3 if is_opaque_box else 1
        back_color = style.background_color if is_opaque_box else style.shadow_color
        bold_val = "-1" if style.font_weight >= 600 else "0"
        italic_val = "-1" if style.italic else "0"
        underline_val = "-1" if style.underline else "0"

        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.spec.canvas.width}
PlayResY: {self.spec.canvas.height}
WrapStyle: 1
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{style.font_name},{self.spec.font_size},{style.primary_color},&H000000FF,{style.outline_color},{back_color},{bold_val},{italic_val},{underline_val},0,100,100,0,0,{border_style},{self.spec.outline_width},{self.spec.shadow_depth},{safe_area.alignment},{safe_area.margin_l},{safe_area.margin_r},{safe_area.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _calculate_chunk_prefix_tags(self) -> str:
        animation = self.spec.animation
        safe_area = self.spec.safe_area
        tags = [fr"\an{safe_area.alignment}"]

        if self.style.animation_type == "slide_up" and animation.slide_offset_px > 0:
            tags.append(
                fr"\move({safe_area.anchor_x},{safe_area.anchor_y + animation.slide_offset_px},{safe_area.anchor_x},{safe_area.anchor_y},0,{animation.entry_ms})"
            )

        if animation.chunk_fade:
            tags.append(fr"\fad({animation.entry_ms},{animation.exit_ms})")

        if self.spec.blur > 0:
            tags.append(fr"\blur{self.spec.blur}")

        return "{" + "".join(tags) + "}"

    def _calculate_word_animation_tags(self, word_start: float, word_end: float, chunk_start: float) -> str:
        animation = self.spec.animation
        relative_start_ms = max(0, int(round((word_start - chunk_start) * 1000)))
        relative_end_ms = max(relative_start_ms + 1, int(round((word_end - chunk_start) * 1000)))
        word_duration_ms = max(1, relative_end_ms - relative_start_ms)
        emphasis_ms = max(20, min(animation.emphasis_ms, word_duration_ms))
        grow_ms = max(1, min(50, emphasis_ms // 2))
        settle_ms = max(1, min(70, max(word_duration_ms - grow_ms, 1)))
        settle_start = max(relative_start_ms + grow_ms, relative_end_ms - settle_ms)
        highlight = self.style.highlight_color
        primary = self.style.primary_color
        scale_hi = animation.emphasis_scale_pct
        scale_base = animation.base_scale_pct

        if self.style.animation_type == "none":
            return ""

        if self.style.animation_type == "typewriter":
            return (
                r"{\alpha&HFF&}"
                + fr"{{\t({relative_start_ms},{relative_start_ms + 1},\alpha&H00&\c{highlight})}}"
                + fr"{{\t({settle_start},{relative_end_ms},\c{primary})}}"
            )

        if self.style.animation_type == "fade":
            return (
                fr"{{\c{primary}}}"
                + fr"{{\t({relative_start_ms},{relative_start_ms + grow_ms},\c{highlight})}}"
                + fr"{{\t({settle_start},{relative_end_ms},\c{primary})}}"
            )

        if self.style.animation_type == "shake":
            shake_end = min(relative_start_ms + 75, relative_end_ms)
            return (
                fr"{{\fscx{scale_base}\fscy{scale_base}}}"
                + fr"{{\t({relative_start_ms},{relative_start_ms + grow_ms},\c{highlight}\fscx{scale_hi}\fscy{scale_hi})}}"
                + fr"{{\t({relative_start_ms},{shake_end},\frz3)\t({shake_end},{relative_end_ms},\frz0\c{primary}\fscx100\fscy100)}}"
            )

        return (
            fr"{{\fscx{scale_base}\fscy{scale_base}}}"
            + fr"{{\t({relative_start_ms},{relative_start_ms + grow_ms},\c{highlight}\fscx{scale_hi}\fscy{scale_hi})}}"
            + fr"{{\t({settle_start},{relative_end_ms},\c{primary}\fscx100\fscy100)}}"
        )

    @staticmethod
    def _canonicalize_text(text: str) -> str:
        normalized = normalize_subtitle_text(text).lower()
        normalized = "".join(ch if ch.isalnum() or ch.isspace() or ch in {"'", "-"} else " " for ch in normalized)
        return " ".join(normalized.split())

    def _build_words_from_segment_text(self, segment: dict) -> list[dict]:
        text = str(segment.get("text", "")).strip()
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))

        if not text or end <= start:
            return []

        tokens = [token for token in text.split() if token]
        if not tokens:
            return []

        total_duration = max(end - start, 0.01)
        word_duration = total_duration / len(tokens)
        words: list[dict] = []
        for index, token in enumerate(tokens):
            word_start = start + (index * word_duration)
            word_end = end if index == len(tokens) - 1 else start + ((index + 1) * word_duration)
            words.append(
                {
                    "word": token,
                    "start": word_start,
                    "end": word_end,
                    "score": 1.0,
                    "segment_end": end,
                }
            )
        return words

    def _flatten_render_words(self, segments: list[dict]) -> list[dict]:
        all_words: list[dict] = []
        for segment in segments:
            segment_words = [
                word
                for word in segment.get("words", []) or []
                if word.get("word") and "start" in word and "end" in word
            ]
            if segment_words:
                segment_text = self._canonicalize_text(str(segment.get("text", "")))
                words_text = self._canonicalize_text(
                    " ".join(str(word.get("word", "")).strip() for word in segment_words)
                )
                if segment_text and words_text and segment_text != words_text:
                    logger.warning(
                        "Segment text/words mismatch bulundu; mevcut kelime zamanlari korunuyor. segment={}",
                        segment.get("text", ""),
                    )
                all_words.extend(segment_words)
                continue

            all_words.extend(self._build_words_from_segment_text(segment))
        return all_words

    def _estimate_chunk_overflow(
        self,
        chunks: list[list[dict]],
        *,
        line_breaks: dict[int, int] | None = None,
        font_scales: dict[int, float] | None = None,
    ) -> dict[str, object]:
        overflow_detected = False
        max_width_ratio = 0.0
        safe_area_violations = 0
        line_breaks = line_breaks or {}
        font_scales = font_scales or {}

        for index, chunk in enumerate(chunks):
            if not chunk:
                continue
            lines = self._chunk_lines(chunk, line_break_after=line_breaks.get(index))
            if not lines:
                continue
            font_scale = font_scales.get(index, 1.0)
            line_widths = [self._estimate_line_width_ratio(line, font_scale=font_scale) for line in lines]
            widest = max(line_widths)
            max_width_ratio = max(max_width_ratio, widest)
            if widest > 1.0:
                overflow_detected = True
                safe_area_violations += 1

        return {
            "subtitle_overflow_detected": overflow_detected,
            "max_rendered_line_width_ratio": round(max_width_ratio, 4),
            "safe_area_violation_count": safe_area_violations,
        }

    def _estimate_text_units(self, normalized_text: str) -> float:
        units = 0.0
        for char in normalized_text:
            if char.isspace():
                units += 0.28
            elif char in NARROW_CHARACTERS:
                units += 0.34
            elif char in PUNCTUATION_CHARACTERS:
                units += 0.26
            elif char.isdigit():
                units += 0.52
            elif char in WIDE_LOWER_CHARACTERS:
                units += 0.62
            elif char.isalpha():
                units += 0.58 if char.isupper() else 0.49
            else:
                units += 0.49
        return units

    def _estimate_line_width_ratio(self, line_words: list[dict], *, font_scale: float = 1.0) -> float:
        text = " ".join(str(word.get("word", "")).strip() for word in line_words if str(word.get("word", "")).strip())
        normalized = normalize_subtitle_text(text)
        if not normalized:
            return 0.0
        estimated_width = self._estimate_text_units(normalized) * float(self.spec.font_size) * max(font_scale, 0.0)
        if self.style.high_contrast or self.style.large_text or int(self.style.font_weight) >= 800:
            estimated_width *= 1.05
        return estimated_width / max(self.spec.safe_area.max_text_width, 1)

    @staticmethod
    def _chunk_lines(chunk: list[dict], *, line_break_after: int | None) -> list[list[dict]]:
        if line_break_after is None or line_break_after < 0 or line_break_after >= len(chunk) - 1:
            return [chunk]
        return [chunk[: line_break_after + 1], chunk[line_break_after + 1 :]]

    def _resolve_split_line_break_after(self, chunk: list[dict]) -> tuple[int | None, float]:
        if len(chunk) < 2:
            widest = self._estimate_line_width_ratio(chunk)
            return None, widest

        best_index: int | None = None
        best_widest = float("inf")
        for candidate in range(len(chunk) - 1):
            lines = self._chunk_lines(chunk, line_break_after=candidate)
            widest = max((self._estimate_line_width_ratio(line) for line in lines if line), default=0.0)
            if widest < best_widest:
                best_index = candidate
                best_widest = widest

        if best_index is None:
            return None, self._estimate_line_width_ratio(chunk)
        return best_index, best_widest

    @staticmethod
    def _promote_overflow_strategy(current: str, candidate: str) -> str:
        priority = {
            "default": 0,
            "rechunk_2_words": 1,
            "conservative_line_break": 2,
            "single_font_clamp": 3,
            "split_line_break": 4,
            "split_rechunk_1_word": 5,
        }
        return candidate if priority.get(candidate, 0) >= priority.get(current, 0) else current

    def _resolve_chunk_font_scale(
        self,
        chunk: list[dict],
        *,
        line_break_after: int | None = None,
        min_scale: float = SPLIT_MIN_FONT_SCALE,
    ) -> float:
        lines = self._chunk_lines(chunk, line_break_after=line_break_after)
        widest = max((self._estimate_line_width_ratio(line) for line in lines if line), default=0.0)
        if widest <= 1.0:
            return 1.0
        desired_scale = (1.0 / widest) * SPLIT_FONT_CLAMP_MARGIN
        return round(min(1.0, max(min_scale, desired_scale)), 4)

    def _resolve_split_chunk_font_scales(
        self,
        chunks: list[list[dict]],
        *,
        line_breaks: dict[int, int],
    ) -> dict[int, float]:
        font_scales: dict[int, float] = {}
        for index, chunk in enumerate(chunks):
            if not chunk:
                continue
            font_scale = self._resolve_chunk_font_scale(
                chunk,
                line_break_after=line_breaks.get(index),
                min_scale=SPLIT_MIN_FONT_SCALE,
            )
            if font_scale < 0.9999:
                font_scales[index] = font_scale
        return font_scales

    def _resolve_single_chunk_font_scales(
        self,
        chunks: list[list[dict]],
        *,
        line_breaks: dict[int, int],
    ) -> dict[int, float]:
        font_scales: dict[int, float] = {}
        for index, chunk in enumerate(chunks):
            if not chunk:
                continue
            font_scale = self._resolve_chunk_font_scale(
                chunk,
                line_break_after=line_breaks.get(index),
                min_scale=SINGLE_MIN_FONT_SCALE,
            )
            if font_scale < 0.9999:
                font_scales[index] = font_scale
        return font_scales

    def _prepare_split_render_chunks(
        self,
        chunks: list[list[dict]],
    ) -> tuple[list[list[dict]], dict[int, int], str]:
        planned_chunks: list[list[dict]] = []
        line_breaks: dict[int, int] = {}
        overflow_strategy = "default"

        for chunk in chunks:
            if not chunk:
                continue

            widest_single_line = self._estimate_line_width_ratio(chunk)
            if widest_single_line <= SPLIT_SOFT_WRAP_RATIO:
                planned_chunks.append(chunk)
                continue

            break_after, broken_widest = self._resolve_split_line_break_after(chunk)
            if break_after is not None and broken_widest <= SPLIT_HARD_OVERFLOW_RATIO:
                line_breaks[len(planned_chunks)] = break_after
                planned_chunks.append(chunk)
                overflow_strategy = self._promote_overflow_strategy(overflow_strategy, "split_line_break")
                continue

            overflow_strategy = self._promote_overflow_strategy(overflow_strategy, "split_rechunk_1_word")
            planned_chunks.extend([[word] for word in chunk])

        return planned_chunks, line_breaks, overflow_strategy

    def _resolve_conservative_line_breaks(self, chunks: list[list[dict]]) -> dict[int, int]:
        line_breaks: dict[int, int] = {}
        for index, chunk in enumerate(chunks):
            if len(chunk) < 2:
                continue
            line_breaks[index] = max(0, (len(chunk) // 2) - 1)
        return line_breaks

    def _prepare_render_chunks(
        self,
        all_words: list[dict],
        *,
        max_words_per_screen: int,
    ) -> tuple[list[list[dict]], dict[str, object], dict[int, int], dict[int, float]]:
        if self.spec.canvas.layout == "split" and max_words_per_screen == DEFAULT_MAX_WORDS_PER_SCREEN:
            max_words_per_screen = SPLIT_MAX_WORDS_PER_SCREEN

        line_breaks: dict[int, int] = {}
        chunk_font_scales: dict[int, float] = {}
        chunks = chunk_words(
            all_words,
            max_words=max_words_per_screen,
            max_chunk_duration=DEFAULT_MAX_CHUNK_DURATION,
        )
        overflow_strategy = "default"

        if self.spec.canvas.layout == "split":
            chunks, line_breaks, overflow_strategy = self._prepare_split_render_chunks(chunks)
            chunk_font_scales = self._resolve_split_chunk_font_scales(chunks, line_breaks=line_breaks)
            overflow_metrics = self._estimate_chunk_overflow(
                chunks,
                line_breaks=line_breaks,
                font_scales=chunk_font_scales,
            )
            return chunks, {
                **overflow_metrics,
                "overflow_strategy": overflow_strategy,
                "avg_words_per_chunk": round(average_chunk_words(chunks), 4),
                "max_chunk_duration": round(max((get_chunk_duration(chunk) for chunk in chunks), default=0.0), 4),
                "chunk_count": len(chunks),
                "font_clamp_count": len(chunk_font_scales),
            }, line_breaks, chunk_font_scales

        overflow_metrics = self._estimate_chunk_overflow(chunks)

        if overflow_metrics["subtitle_overflow_detected"]:
            retry_chunks = chunk_words(
                all_words,
                max_words=2,
                max_chunk_duration=DEFAULT_MAX_CHUNK_DURATION,
            )
            retry_metrics = self._estimate_chunk_overflow(retry_chunks)
            chunks = retry_chunks
            overflow_metrics = retry_metrics
            overflow_strategy = "rechunk_2_words"

        if overflow_metrics["subtitle_overflow_detected"]:
            line_breaks = self._resolve_conservative_line_breaks(chunks)
            retry_metrics = self._estimate_chunk_overflow(chunks, line_breaks=line_breaks)
            overflow_metrics = retry_metrics
            overflow_strategy = "conservative_line_break"

        if overflow_metrics["subtitle_overflow_detected"]:
            chunk_font_scales = self._resolve_single_chunk_font_scales(chunks, line_breaks=line_breaks)
            if chunk_font_scales:
                retry_metrics = self._estimate_chunk_overflow(
                    chunks,
                    line_breaks=line_breaks,
                    font_scales=chunk_font_scales,
                )
                overflow_metrics = retry_metrics
                overflow_strategy = self._promote_overflow_strategy(overflow_strategy, "single_font_clamp")

        return chunks, {
            **overflow_metrics,
            "overflow_strategy": overflow_strategy,
            "avg_words_per_chunk": round(average_chunk_words(chunks), 4),
            "max_chunk_duration": round(max((get_chunk_duration(chunk) for chunk in chunks), default=0.0), 4),
            "chunk_count": len(chunks),
            "font_clamp_count": len(chunk_font_scales),
        }, line_breaks, chunk_font_scales

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        return (
            text.replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\r\n", r"\N")
            .replace("\n", r"\N")
            .replace("\r", r"\N")
        )

    @staticmethod
    def _escape_filter_path(path: str) -> str:
        return (
            path.replace("\\", r"\\\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
            .replace(",", r"\,")
            .replace("[", r"\[")
            .replace("]", r"\]")
        )

    def generate_ass_file(
        self,
        transcript_json_path: str,
        output_ass_path: str = "dynamic_subs.ass",
        max_words_per_screen: int = DEFAULT_MAX_WORDS_PER_SCREEN,
    ) -> str:
        logger.info(f"Transkript NLP verisi işleniyor: {transcript_json_path}")

        with open(transcript_json_path, "r", encoding="utf-8") as handle:
            segments = json.load(handle)

        if not isinstance(segments, list):
            raise ValueError("Transcript JSON list formatında olmalı")

        segments = canonicalize_transcript_segments(segments)

        ass_lines: list[str] = []
        all_words = collect_valid_words(segments)
        if not all_words:
            all_words = self._flatten_render_words(segments)
            all_words = collect_valid_words([{"words": all_words}]) if all_words else []
        chunks, render_metrics, line_breaks, chunk_font_scales = self._prepare_render_chunks(
            all_words,
            max_words_per_screen=max_words_per_screen,
        )
        chunk_prefix = self._calculate_chunk_prefix_tags()
        dialogue_intervals: list[tuple[float, float]] = []

        for index, chunk in enumerate(chunks):
            if not chunk:
                continue

            chunk_start_sec = float(chunk[0]["start"])
            chunk_end_sec = float(chunk[-1]["end"])
            if index + 1 < len(chunks) and chunks[index + 1]:
                next_chunk_start = float(chunks[index + 1][0]["start"])
                gap = next_chunk_start - chunk_end_sec
                if 0 <= gap < SMALL_GAP_BRIDGE_THRESHOLD:
                    chunk_end_sec = next_chunk_start

            chunk_start_ass = self._format_time_ass(chunk_start_sec)
            chunk_end_ass = self._format_time_ass(chunk_end_sec)
            line_break_after = line_breaks.get(index)
            chunk_font_scale = chunk_font_scales.get(index, 1.0)
            chunk_font_size = None
            if chunk_font_scale < 0.9999:
                chunk_font_size = max(28, round(float(self.spec.font_size) * chunk_font_scale))

            word_fragments: list[str] = [chunk_prefix]
            for word_index, word in enumerate(chunk):
                word_text = self._escape_ass_text(str(word["word"]).strip())
                word_start = float(word["start"])
                word_end = float(word["end"])
                anim_tags = self._calculate_word_animation_tags(word_start, word_end, chunk_start_sec)
                primary_color = self.style.primary_color
                font_tag = fr"\fs{chunk_font_size}" if chunk_font_size is not None else ""
                if self.spec.blur > 0:
                    reset_tag = fr"{{\r{font_tag}\blur{self.spec.blur}\c{primary_color}}}"
                else:
                    reset_tag = fr"{{\r{font_tag}\c{primary_color}}}"
                word_fragments.append(f"{reset_tag}{anim_tags}{word_text}")
                if line_break_after is not None and word_index == line_break_after:
                    word_fragments.append(r"\N")

            dialogue_text = self._join_word_fragments(word_fragments)
            ass_lines.append(
                f"Dialogue: 0,{chunk_start_ass},{chunk_end_ass},Main,,0,0,0,,{dialogue_text}\n"
            )
            dialogue_intervals.append((chunk_start_sec, chunk_end_sec))

        if not ass_lines:
            raise RuntimeError("ASS generation produced no dialogue events")

        simultaneous_overlap_count, max_simultaneous_events = self._count_simultaneous_event_overlaps(dialogue_intervals)
        if simultaneous_overlap_count > 0:
            raise RuntimeError("ASS generation produced overlapping dialogue events")

        ass_content = self._generate_ass_header() + "".join(ass_lines)
        output_path = Path(output_ass_path)
        output_path.write_text(ass_content, encoding="utf-8")
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise RuntimeError(f"ASS output was not created: {output_ass_path}")

        chunk_dump = build_chunk_payload(chunks)
        for index, chunk_payload in enumerate(chunk_dump):
            if index in line_breaks:
                chunk_payload["line_break_after"] = line_breaks[index]
            if index in chunk_font_scales:
                chunk_payload["font_scale"] = chunk_font_scales[index]

        self.last_render_report = {
            **self._build_base_render_report(),
            **render_metrics,
            "simultaneous_event_overlap_count": simultaneous_overlap_count,
            "max_simultaneous_events": max_simultaneous_events,
            "chunk_dump": chunk_dump,
        }
        logger.success(f"NLP Akilli ASS dosyasi olusturuldu: {output_ass_path}")
        return str(output_path)

    @staticmethod
    def _join_word_fragments(word_fragments: list[str]) -> str:
        rendered: list[str] = []
        for fragment in word_fragments:
            if not fragment:
                continue
            if fragment == r"\N":
                rendered.append(fragment)
                continue
            if rendered and rendered[-1] != r"\N":
                rendered.append(" ")
            rendered.append(fragment)
        return "".join(rendered)

    def burn_subtitles_to_video(
        self,
        input_video: str,
        ass_file: str,
        output_video: str,
        cancel_event: threading.Event | None = None,
    ) -> None:
        logger.info(f"Akilli altyazilar isleniyor -> {output_video}")
        require_nvenc = os.getenv("REQUIRE_NVENC_FOR_BURN") == "1"

        ass_abs = os.path.abspath(ass_file).replace("\\", "/")
        escaped_ass_abs = self._escape_filter_path(ass_abs)
        cmd_nvenc = [
            resolve_ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            input_video,
            "-vf",
            f"ass='{escaped_ass_abs}'",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p6",
            "-b:v",
            "8M",
            "-c:a",
            "copy",
            output_video,
        ]
        cmd_cpu = [
            resolve_ffmpeg(),
            "-y",
            "-i",
            input_video,
            "-vf",
            f"ass='{escaped_ass_abs}'",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-c:a",
            "copy",
            output_video,
        ]

        result = self._run_command_with_cancel(
            cmd_nvenc,
            timeout=600,
            cancel_event=cancel_event,
        )
        if result.returncode == 0:
            self.last_render_report.update(
                {
                    "burn_encoder": "h264_nvenc",
                    "nvenc_fallback_used": False,
                    "nvenc_required": require_nvenc,
                }
            )
            logger.success("Altyazi işlendi (NVENC), video hazır.")
            return

        stderr = result.stderr.decode("utf-8", errors="replace")
        stderr_tail = self._tail_text(stderr)
        failure_reason = self._summarize_nvenc_failure(stderr)
        forensic = self._probe_video_forensics(input_video)
        self.last_render_report.update(
            {
                **forensic,
                "burn_encoder": "h264_nvenc",
                "nvenc_fallback_used": False,
                "nvenc_required": require_nvenc,
                "nvenc_failure_reason": failure_reason,
                "nvenc_failure_stderr_tail": stderr_tail,
            }
        )
        logger.warning(
            "NVENC burn basarisiz, encoder fallback karari veriliyor. reason={} input={} codec={} size={}x{} fps={} stderr_tail={}",
            failure_reason,
            input_video,
            forensic.get("burn_input_codec"),
            forensic.get("burn_input_width"),
            forensic.get("burn_input_height"),
            forensic.get("burn_input_fps"),
            stderr_tail,
        )
        if require_nvenc:
            raise RuntimeError(f"NVENC zorunlu ama burn basarisiz: {stderr_tail}")
        if self._looks_like_nvenc_failure(stderr):
            cpu_result = self._run_command_with_cancel(
                cmd_cpu,
                timeout=600,
                cancel_event=cancel_event,
            )
            if cpu_result.returncode != 0:
                cpu_stderr = cpu_result.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"CPU fallback ile altyazi burn basarisiz: {cpu_stderr[-300:]}")
            self.last_render_report.update(
                {
                    "burn_encoder": "libx264",
                    "nvenc_fallback_used": True,
                }
            )
            logger.success("Altyazi işlendi (CPU), video hazır.")
            return

        logger.error(f"FFmpeg error: {stderr_tail}")
        raise subprocess.CalledProcessError(result.returncode, cmd_nvenc, result.stdout, result.stderr)
