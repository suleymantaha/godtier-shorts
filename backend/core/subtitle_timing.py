"""Shared subtitle timing, normalization, chunking, and snapping helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Sequence

DEFAULT_MAX_WORDS_PER_SCREEN = 3
DEFAULT_MAX_CHUNK_DURATION = 1.8
DEFAULT_MIN_CHUNK_DURATION = 0.45
DEFAULT_MAX_MERGED_CHUNK_DURATION = 2.2
DEFAULT_WORD_GAP_BREAK = 0.35

STRONG_PUNCTUATION = (".", "!", "?")
WEAK_PUNCTUATION = (",", ";", ":")
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")
WHITESPACE_PATTERN = re.compile(r"\s+")


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalize_subtitle_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text or "")
    normalized = ZERO_WIDTH_PATTERN.sub("", normalized)
    normalized = normalized.replace("…", "...")
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def count_normalized_tokens(text: str) -> int:
    normalized = normalize_subtitle_text(text)
    if not normalized:
        return 0
    scrubbed = re.sub(r"[^\w\s'-]", " ", normalized, flags=re.UNICODE)
    return len([token for token in scrubbed.split(" ") if token])


def tokenize_subtitle_text(text: str) -> list[str]:
    normalized = normalize_subtitle_text(text)
    if not normalized:
        return []
    return [token for token in normalized.split(" ") if token]


def normalize_word_payload(word: dict) -> dict | None:
    raw_text = normalize_subtitle_text(str(word.get("word", "")).strip())
    if not raw_text:
        return None
    if "start" not in word or "end" not in word:
        return None
    start = float(word["start"])
    end = float(word["end"])
    if end <= start:
        return None
    normalized = {
        "word": str(word.get("word", "")).strip(),
        "start": start,
        "end": end,
        "score": float(word.get("score", 1.0)),
    }
    if "segment_end" in word:
        normalized["segment_end"] = float(word["segment_end"])
    return normalized


def build_words_from_segment_text(text: str, start: float, end: float) -> list[dict]:
    tokens = tokenize_subtitle_text(text)
    if not tokens or end <= start:
        return []

    total_duration = max(float(end) - float(start), 0.01)
    word_duration = total_duration / len(tokens)
    words: list[dict] = []
    for index, token in enumerate(tokens):
        word_start = float(start) + (index * word_duration)
        word_end = float(end) if index == len(tokens) - 1 else float(start) + ((index + 1) * word_duration)
        words.append(
            {
                "word": token,
                "start": word_start,
                "end": word_end,
                "score": 1.0,
            }
        )
    return words


def sync_segment_text_and_words(segment: dict) -> dict:
    synced = dict(segment)
    text = normalize_subtitle_text(str(segment.get("text", "")))
    start = float(segment.get("start", 0.0) or 0.0)
    end = float(segment.get("end", start) or start)
    valid_words = resolve_word_overlaps(
        [
            normalized
            for raw_word in segment.get("words", []) or []
            if (normalized := normalize_word_payload(dict(raw_word))) is not None
        ]
    )
    tokens = tokenize_subtitle_text(text)

    synced["text"] = text
    synced["start"] = start
    synced["end"] = end

    if not tokens or end <= start:
        synced["words"] = []
        return synced

    if len(valid_words) == len(tokens):
        synced["words"] = [
            {
                **word,
                "word": tokens[index],
            }
            for index, word in enumerate(valid_words)
        ]
        return synced

    synced["words"] = build_words_from_segment_text(text, start, end)
    return synced


def canonicalize_transcript_segments(segments: Sequence[dict]) -> list[dict]:
    return [sync_segment_text_and_words(segment) for segment in segments]


def collect_valid_words(segments: Sequence[dict]) -> list[dict]:
    words: list[dict] = []
    for segment in segments:
        for raw_word in segment.get("words", []) or []:
            enriched_word = dict(raw_word)
            enriched_word.setdefault("segment_end", float(segment.get("end", raw_word.get("end", 0.0))))
            normalized = normalize_word_payload(enriched_word)
            if normalized is not None:
                words.append(normalized)
    return resolve_word_overlaps(words)


def resolve_word_overlaps(words: Sequence[dict]) -> list[dict]:
    resolved: list[dict] = []
    for word in words:
        normalized = dict(word)
        normalized["start"] = float(normalized["start"])
        normalized["end"] = float(normalized["end"])
        if normalized["end"] <= normalized["start"]:
            normalized["end"] = normalized["start"] + 0.01

        if resolved and normalized["start"] < resolved[-1]["end"]:
            resolved[-1]["end"] = max(resolved[-1]["start"] + 0.01, normalized["start"])
            normalized["start"] = max(normalized["start"], resolved[-1]["end"])
            if normalized["end"] <= normalized["start"]:
                normalized["end"] = normalized["start"] + 0.01

        resolved.append(normalized)
    return resolved


def compute_word_coverage_ratio(segments: Sequence[dict]) -> float:
    valid_word_tokens = len(collect_valid_words(segments))
    normalized_text_tokens = sum(count_normalized_tokens(str(segment.get("text", ""))) for segment in segments)
    return valid_word_tokens / max(normalized_text_tokens, 1)


def resolve_snap_window(word_coverage_ratio: float) -> float | None:
    if word_coverage_ratio >= 0.80:
        return 0.35
    if word_coverage_ratio >= 0.60:
        return 0.20
    return None


def snap_segment_boundaries(
    segments: Sequence[dict],
    start_time: float,
    end_time: float,
) -> tuple[float, float, dict]:
    report = {
        "enabled": False,
        "word_coverage_ratio": 0.0,
        "snap_window": None,
        "start_applied": False,
        "end_applied": False,
        "original_start_time": float(start_time),
        "original_end_time": float(end_time),
        "snapped_start_time": float(start_time),
        "snapped_end_time": float(end_time),
        "boundary_snaps_applied": 0,
    }
    relevant_segments = [
        segment
        for segment in segments
        if float(segment.get("end", 0.0)) > start_time and float(segment.get("start", 0.0)) < end_time
    ]
    coverage_ratio = compute_word_coverage_ratio(relevant_segments)
    report["word_coverage_ratio"] = round(coverage_ratio, 4)
    snap_window = resolve_snap_window(coverage_ratio)
    report["snap_window"] = snap_window
    if snap_window is None:
        return float(start_time), float(end_time), report

    report["enabled"] = True
    boundaries = sorted(
        {
            boundary
            for word in collect_valid_words(relevant_segments)
            for boundary in (float(word["start"]), float(word["end"]))
        }
    )
    if not boundaries:
        return float(start_time), float(end_time), report

    snapped_start = _nearest_boundary(float(start_time), boundaries, snap_window)
    snapped_end = _nearest_boundary(float(end_time), boundaries, snap_window)
    if snapped_start is not None and snapped_start < end_time:
        report["start_applied"] = snapped_start != start_time
        report["snapped_start_time"] = snapped_start
        start_time = snapped_start
    if snapped_end is not None and snapped_end > start_time:
        report["end_applied"] = snapped_end != end_time
        report["snapped_end_time"] = snapped_end
        end_time = snapped_end
    report["boundary_snaps_applied"] = int(bool(report["start_applied"])) + int(bool(report["end_applied"]))
    return float(start_time), float(end_time), report


def _nearest_boundary(target: float, boundaries: Sequence[float], max_delta: float) -> float | None:
    nearest: float | None = None
    nearest_delta = max_delta + 1.0
    for boundary in boundaries:
        delta = abs(boundary - target)
        if delta <= max_delta and delta < nearest_delta:
            nearest = boundary
            nearest_delta = delta
    return nearest


def chunk_words(
    words: Sequence[dict],
    *,
    max_words: int = DEFAULT_MAX_WORDS_PER_SCREEN,
    max_chunk_duration: float = DEFAULT_MAX_CHUNK_DURATION,
    min_chunk_duration: float = DEFAULT_MIN_CHUNK_DURATION,
    max_merged_duration: float = DEFAULT_MAX_MERGED_CHUNK_DURATION,
    gap_break: float = DEFAULT_WORD_GAP_BREAK,
) -> list[list[dict]]:
    seeded_chunks = _seed_chunks(words, max_words=max_words, max_chunk_duration=max_chunk_duration, gap_break=gap_break)
    return _merge_short_chunks(
        seeded_chunks,
        min_chunk_duration=min_chunk_duration,
        max_merged_duration=max_merged_duration,
    )


def _seed_chunks(
    words: Sequence[dict],
    *,
    max_words: int,
    max_chunk_duration: float,
    gap_break: float,
) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current_chunk: list[dict] = []

    valid_words = [word for word in words if normalize_word_payload(word) is not None]
    valid_words = resolve_word_overlaps(valid_words)

    for index, word in enumerate(valid_words):
        current_chunk.append(word)
        next_word = valid_words[index + 1] if index + 1 < len(valid_words) else None
        time_gap = (
            float(next_word["start"]) - float(word["end"])
            if next_word is not None
            else 0.0
        )
        text = normalize_subtitle_text(str(word.get("word", "")))
        chunk_duration = get_chunk_duration(current_chunk)

        should_break = False
        if len(current_chunk) >= max_words:
            should_break = True
        elif chunk_duration >= max_chunk_duration:
            should_break = True
        elif time_gap > gap_break:
            should_break = True
        elif has_strong_punctuation(text):
            should_break = True
        elif has_weak_punctuation(text) and len(current_chunk) >= 2:
            should_break = True

        if should_break:
            chunks.append(current_chunk)
            current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _merge_short_chunks(
    chunks: Sequence[list[dict]],
    *,
    min_chunk_duration: float,
    max_merged_duration: float,
) -> list[list[dict]]:
    merged: list[list[dict]] = []
    pending: list[dict] | None = None

    for chunk in chunks:
        if not chunk:
            continue
        current = list(chunk)
        if pending is not None:
            combined = pending + current
            if (
                not chunk_ends_with_strong_punctuation(pending)
                and get_chunk_duration(combined) <= max_merged_duration
            ):
                current = combined
                pending = None
            else:
                merged.append(pending)
                pending = None

        if get_chunk_duration(current) < min_chunk_duration:
            pending = current
            continue

        merged.append(current)

    if pending is not None:
        if merged:
            candidate = merged[-1] + pending
            if (
                not chunk_ends_with_strong_punctuation(merged[-1])
                and get_chunk_duration(candidate) <= max_merged_duration
            ):
                merged[-1] = candidate
            else:
                merged.append(pending)
        else:
            merged.append(pending)

    return merged


def get_chunk_duration(chunk: Sequence[dict]) -> float:
    if not chunk:
        return 0.0
    return max(0.0, float(chunk[-1]["end"]) - float(chunk[0]["start"]))


def get_chunk_text(chunk: Sequence[dict]) -> str:
    return " ".join(str(word.get("word", "")).strip() for word in chunk if str(word.get("word", "")).strip())


def has_strong_punctuation(text: str) -> bool:
    return any(punct in text for punct in STRONG_PUNCTUATION)


def has_weak_punctuation(text: str) -> bool:
    return any(punct in text for punct in WEAK_PUNCTUATION)


def chunk_ends_with_strong_punctuation(chunk: Sequence[dict]) -> bool:
    if not chunk:
        return False
    return has_strong_punctuation(normalize_subtitle_text(str(chunk[-1].get("word", ""))))


def build_chunk_payload(chunks: Sequence[Sequence[dict]]) -> list[dict]:
    payload: list[dict] = []
    for chunk in chunks:
        if not chunk:
            continue
        payload.append(
            {
                "text": get_chunk_text(chunk),
                "start": float(chunk[0]["start"]),
                "end": float(chunk[-1]["end"]),
                "words": [dict(word) for word in chunk],
                "duration": round(get_chunk_duration(chunk), 4),
            }
        )
    return payload


def average_chunk_words(chunks: Sequence[Sequence[dict]]) -> float:
    populated = [chunk for chunk in chunks if chunk]
    if not populated:
        return 0.0
    return sum(len(chunk) for chunk in populated) / len(populated)


def iter_word_boundaries(segments: Sequence[dict]) -> Iterable[float]:
    for word in collect_valid_words(segments):
        yield float(word["start"])
        yield float(word["end"])
