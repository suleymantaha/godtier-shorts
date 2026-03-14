"""Prefill generation and viral metadata fallback helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.config import get_project_path

from .constants import PLATFORM_MAX_HASHTAGS, PLATFORM_MAX_TEXT, SUPPORTED_SOCIAL_PLATFORMS

_HASHTAG_RE = re.compile(r"#([\w\d_\-ÇĞİÖŞÜçğıöşü]+)")


def extract_hashtags(text: str) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for raw in _HASHTAG_RE.findall(text):
        tag = raw.strip()
        if not tag:
            continue
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tags.append(tag)
    return tags


def strip_hashtags(text: str) -> str:
    stripped = _HASHTAG_RE.sub("", text)
    stripped = re.sub(r"\s{2,}", " ", stripped)
    return stripped.strip()


def _normalize_hashtags(platform: str, tags: list[str]) -> list[str]:
    limit = PLATFORM_MAX_HASHTAGS.get(platform, 10)
    return tags[:limit]


def _clamp_text(platform: str, value: str) -> str:
    max_len = PLATFORM_MAX_TEXT.get(platform)
    if not max_len or len(value) <= max_len:
        return value
    if max_len <= 1:
        return value[:max_len]
    return value[: max_len - 1].rstrip() + "…"


def _platform_text(platform: str, base_text: str, tags: list[str]) -> str:
    tag_str = " ".join(f"#{t}" for t in tags)
    if platform == "x":
        # For X we keep a shorter, denser format.
        body = base_text
        if tag_str:
            body = f"{body}\n\n{tag_str}".strip()
        return _clamp_text(platform, body)

    body = base_text
    if tag_str:
        body = f"{body}\n\n{tag_str}".strip()
    return _clamp_text(platform, body)


def build_platform_prefill(viral_metadata: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    source = viral_metadata or {}
    title = str(source.get("ui_title") or "").strip()
    hook_text = str(source.get("hook_text") or "").strip()
    social_caption = str(source.get("social_caption") or "").strip()
    viral_score = int(source.get("viral_score") or 0)

    tags = extract_hashtags(social_caption)
    base_text = strip_hashtags(social_caption)

    payload: dict[str, dict[str, Any]] = {}
    for platform in SUPPORTED_SOCIAL_PLATFORMS:
        platform_tags = _normalize_hashtags(platform, tags)
        platform_text = _platform_text(platform, base_text, platform_tags)
        payload[platform] = {
            "title": _clamp_text(platform, title),
            "text": platform_text,
            "hashtags": platform_tags,
            "hook_text": hook_text,
            "viral_score": viral_score,
        }

    return payload


def _segment_overlap(seg_start: float, seg_end: float, clip_start: float, clip_end: float) -> float:
    start = max(seg_start, clip_start)
    end = min(seg_end, clip_end)
    return max(0.0, end - start)


def _match_by_render_window(segments: list[dict[str, Any]], clip_meta: dict[str, Any]) -> dict[str, Any] | None:
    render = clip_meta.get("render_metadata")
    if not isinstance(render, dict):
        return None

    start = render.get("start_time")
    end = render.get("end_time")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None

    best: dict[str, Any] | None = None
    best_overlap = 0.0
    for seg in segments:
        seg_start = seg.get("start_time")
        seg_end = seg.get("end_time")
        if not isinstance(seg_start, (int, float)) or not isinstance(seg_end, (int, float)):
            continue
        overlap = _segment_overlap(float(seg_start), float(seg_end), float(start), float(end))
        if overlap > best_overlap:
            best_overlap = overlap
            best = seg

    return best


def _match_by_filename_index(segments: list[dict[str, Any]], clip_name: str) -> dict[str, Any] | None:
    patterns = [r"short_(\d+)_", r"batch_(\d+)_", r"cut_(\d+)_"]
    for pat in patterns:
        found = re.search(pat, clip_name)
        if not found:
            continue
        idx = int(found.group(1)) - 1
        if 0 <= idx < len(segments):
            return segments[idx]
    return None


def resolve_viral_metadata(project_id: str, clip_name: str, clip_meta: dict[str, Any]) -> dict[str, Any] | None:
    viral_meta = clip_meta.get("viral_metadata")
    if isinstance(viral_meta, dict) and any(
        isinstance(viral_meta.get(key), str) and viral_meta.get(key)
        for key in ("ui_title", "social_caption", "hook_text")
    ):
        return viral_meta

    viral_path = get_project_path(project_id, "viral.json")
    if not viral_path.exists():
        return None

    try:
        import json

        with open(viral_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None

    segments = raw.get("segments") if isinstance(raw, dict) else None
    if not isinstance(segments, list) or not segments:
        return None

    matched = _match_by_render_window(segments, clip_meta)
    if matched is None:
        matched = _match_by_filename_index(segments, clip_name)
    if matched is None:
        matched = segments[0] if segments else None

    return matched if isinstance(matched, dict) else None


def resolve_clip_metadata_paths(project_id: str, clip_name: str) -> tuple[Path, Path]:
    clip_path = get_project_path(project_id, "shorts", clip_name)
    meta_path = get_project_path(project_id, "shorts", clip_name.replace(".mp4", ".json"))
    return clip_path, meta_path
