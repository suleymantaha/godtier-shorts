"""Cache identity and cache persistence helpers for workflow modules."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from backend.config import ProjectPaths
from backend.core.clip_events import ClipEventPort, NullClipEventPort
from backend.core.workflow_artifacts import (
    LAYOUT_SAFETY_CONTRACT_VERSION,
    resolve_layout_safety_mode,
)
from backend.core.workflow_common import (
    build_stable_cache_key,
    hash_file_contents,
    load_json_dict,
    write_json_atomic,
)

PIPELINE_CACHE_SCHEMA_VERSION = 1
PIPELINE_ANALYSIS_CACHE_VERSION = 1
PIPELINE_RENDER_CACHE_VERSION = 2
PIPELINE_ANALYZER_CONTRACT_VERSION = 1
PIPELINE_SUBTITLE_STYLE_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class PipelineCacheIdentity:
    video_id: str
    transcript_hash: str
    analysis_key: str
    render_key: str
    analysis_params: dict[str, object]
    render_params: dict[str, object]


@dataclass(frozen=True)
class PipelineRenderCacheHit:
    project_id: str
    clip_count: int
    expected_outputs: tuple[str, ...]


def resolve_project_video_id(project: ProjectPaths) -> str:
    project_id = project.root.name
    parts = project_id.split("_", 2)
    if len(parts) == 3:
        return parts[2]
    return parts[-1]


def resolve_video_model_identifier(model_path: str | Path | None) -> str:
    return Path(str(model_path or "")).name or "unknown-model"


def build_pipeline_analysis_key(
    *,
    video_id: str,
    transcript_hash: str,
    ai_engine: str,
    num_clips: int,
    duration_min: float,
    duration_max: float,
) -> tuple[str, dict[str, object]]:
    payload: dict[str, object] = {
        "video_id": video_id,
        "transcript_hash": transcript_hash,
        "ai_engine": ai_engine,
        "num_clips": int(num_clips),
        "duration_min": float(duration_min),
        "duration_max": float(duration_max),
        "analysis_cache_version": PIPELINE_ANALYSIS_CACHE_VERSION,
        "analyzer_contract_version": PIPELINE_ANALYZER_CONTRACT_VERSION,
    }
    return build_stable_cache_key(payload), payload


def build_pipeline_render_key(
    *,
    analysis_key: str,
    style_name: str,
    animation_type: str,
    layout: str,
    skip_subtitles: bool,
    video_model_identifier: str,
) -> tuple[str, dict[str, object]]:
    layout_safety_mode = resolve_layout_safety_mode()
    payload: dict[str, object] = {
        "analysis_key": analysis_key,
        "style_name": style_name,
        "animation_type": animation_type,
        "layout": layout,
        "skip_subtitles": bool(skip_subtitles),
        "render_cache_version": PIPELINE_RENDER_CACHE_VERSION,
        "video_processor_model_version": video_model_identifier,
        "subtitle_style_contract_version": PIPELINE_SUBTITLE_STYLE_CONTRACT_VERSION,
        "layout_safety_mode": layout_safety_mode,
        "layout_safety_contract_version": LAYOUT_SAFETY_CONTRACT_VERSION,
        "pipeline_mode": "pipeline_auto",
        "cut_as_short": True,
    }
    return build_stable_cache_key(payload), payload


def build_pipeline_cache_identity(
    *,
    project: ProjectPaths,
    ai_engine: str,
    num_clips: int,
    duration_min: float,
    duration_max: float,
    style_name: str,
    animation_type: str,
    layout: str,
    skip_subtitles: bool,
    video_model_identifier: str,
) -> PipelineCacheIdentity:
    video_id = resolve_project_video_id(project)
    transcript_hash = hash_file_contents(project.transcript)
    analysis_key, analysis_params = build_pipeline_analysis_key(
        video_id=video_id,
        transcript_hash=transcript_hash,
        ai_engine=ai_engine,
        num_clips=num_clips,
        duration_min=duration_min,
        duration_max=duration_max,
    )
    render_key, render_params = build_pipeline_render_key(
        analysis_key=analysis_key,
        style_name=style_name,
        animation_type=animation_type,
        layout=layout,
        skip_subtitles=skip_subtitles,
        video_model_identifier=video_model_identifier,
    )
    return PipelineCacheIdentity(
        video_id=video_id,
        transcript_hash=transcript_hash,
        analysis_key=analysis_key,
        render_key=render_key,
        analysis_params=analysis_params,
        render_params=render_params,
    )


def load_pipeline_cache_manifest(project: ProjectPaths) -> dict[str, object]:
    payload = load_json_dict(project.cache_index) or {}
    if not payload:
        return {"schema_version": PIPELINE_CACHE_SCHEMA_VERSION}
    if int(payload.get("schema_version") or 0) != PIPELINE_CACHE_SCHEMA_VERSION:
        return {"schema_version": PIPELINE_CACHE_SCHEMA_VERSION}
    return payload


def write_pipeline_cache_manifest(
    project: ProjectPaths,
    manifest: dict[str, object],
) -> None:
    payload = {
        **manifest,
        "schema_version": PIPELINE_CACHE_SCHEMA_VERSION,
        "project_id": project.root.name,
        "updated_at": time.time(),
    }
    write_json_atomic(project.cache_index, payload, indent=2)


def build_segments_signature(segments: list[dict]) -> str:
    normalized_segments = [
        {
            "start_time": float(segment.get("start_time", 0.0) or 0.0),
            "end_time": float(segment.get("end_time", 0.0) or 0.0),
            "hook_text": str(segment.get("hook_text", "") or ""),
            "ui_title": str(segment.get("ui_title", "") or ""),
            "viral_score": float(segment.get("viral_score", 0.0) or 0.0),
        }
        for segment in segments
    ]
    return build_stable_cache_key({"segments": normalized_segments})


def extract_pipeline_segments(
    viral_results: dict[str, object],
    *,
    clip_limit: int,
) -> list[dict[str, object]] | None:
    raw_segments = viral_results.get("segments")
    if not isinstance(raw_segments, list):
        return None

    segments: list[dict[str, object]] = []
    for raw_segment in raw_segments[:clip_limit]:
        if isinstance(raw_segment, dict):
            segments.append(raw_segment)
    return segments


def load_cached_pipeline_analysis(
    project: ProjectPaths,
    *,
    analysis_key: str,
) -> dict[str, object] | None:
    if not project.viral_meta.exists():
        return None
    manifest = load_pipeline_cache_manifest(project)
    analysis_section = manifest.get("analysis")
    if not isinstance(analysis_section, dict):
        return None
    if str(analysis_section.get("analysis_key") or "") != analysis_key:
        return None
    viral_results = load_json_dict(project.viral_meta)
    if not viral_results or "segments" not in viral_results:
        return None
    return viral_results


def record_pipeline_analysis_cache(
    project: ProjectPaths,
    *,
    identity: PipelineCacheIdentity,
    viral_results: dict[str, object],
) -> None:
    manifest = load_pipeline_cache_manifest(project)
    manifest["analysis"] = {
        "video_id": identity.video_id,
        "transcript_hash": identity.transcript_hash,
        "analysis_key": identity.analysis_key,
        "analysis_params": identity.analysis_params,
        "viral_results_hash": build_stable_cache_key(viral_results),
        "updated_at": time.time(),
    }
    write_pipeline_cache_manifest(project, manifest)


def load_pipeline_render_cache_hit(
    project: ProjectPaths,
    *,
    render_key: str,
    segments_signature: str,
) -> PipelineRenderCacheHit | None:
    manifest = load_pipeline_cache_manifest(project)
    render_section = manifest.get("render")
    if not isinstance(render_section, dict):
        return None
    if str(render_section.get("render_key") or "") != render_key:
        return None
    if str(render_section.get("segments_signature") or "") != segments_signature:
        return None
    expected_outputs = render_section.get("expected_outputs")
    if not isinstance(expected_outputs, list) or not expected_outputs:
        return None
    if not project.viral_meta.exists():
        return None

    for relative_path in expected_outputs:
        if not _is_valid_cached_output_path(project, relative_path):
            return None
        asset_path = (project.root / relative_path).resolve()
        if not asset_path.exists():
            return None

    clip_metadata_files = [
        item
        for item in expected_outputs
        if isinstance(item, str) and item.endswith(".json")
    ]
    for relative_meta in clip_metadata_files:
        metadata = load_json_dict(project.root / relative_meta)
        if not _has_matching_render_metadata(
            metadata=metadata,
            render_key=render_key,
            analysis_key=str(render_section.get("analysis_key") or ""),
        ):
            return None

    return PipelineRenderCacheHit(
        project_id=project.root.name,
        clip_count=int(render_section.get("clip_count") or 0),
        expected_outputs=tuple(expected_outputs),
    )


def cleanup_stale_render_outputs(
    project: ProjectPaths,
    *,
    previous_outputs: list[str],
    current_outputs: list[str],
    clip_event_port: ClipEventPort | None = None,
) -> int:
    current_set = {item for item in current_outputs if isinstance(item, str)}
    deleted = 0
    for relative_path in previous_outputs:
        if not isinstance(relative_path, str) or relative_path in current_set:
            continue
        if not _is_safe_project_relative_path(project, relative_path):
            raise RuntimeError(f"Geçersiz cleanup hedefi: {relative_path}")
        target = (project.root / relative_path).resolve()
        try:
            os.remove(target)
            deleted += 1
        except FileNotFoundError:
            continue

    if deleted:
        port = clip_event_port or NullClipEventPort()
        port.invalidate_clips_cache(
            reason=f"pipeline_render_cleanup:{project.root.name}"
        )
    return deleted


def record_pipeline_render_cache(
    project: ProjectPaths,
    *,
    identity: PipelineCacheIdentity,
    segments_signature: str,
    clip_names: list[str],
    skip_subtitles: bool,
    clip_event_port: ClipEventPort | None = None,
) -> int:
    expected_outputs: list[str] = []
    for clip_name in clip_names:
        expected_outputs.extend(
            _managed_render_asset_paths(
                project,
                clip_name,
                include_raw=not skip_subtitles,
            )
        )

    manifest = load_pipeline_cache_manifest(project)
    previous_render = manifest.get("render")
    previous_outputs: list[str] = []
    if isinstance(previous_render, dict):
        previous_outputs = [
            item
            for item in previous_render.get("expected_outputs", [])
            if isinstance(item, str)
        ]

    manifest["render"] = {
        "analysis_key": identity.analysis_key,
        "render_key": identity.render_key,
        "render_params": identity.render_params,
        "segments_signature": segments_signature,
        "clip_count": len(clip_names),
        "expected_outputs": expected_outputs,
        "updated_at": time.time(),
    }
    write_pipeline_cache_manifest(project, manifest)
    return cleanup_stale_render_outputs(
        project,
        previous_outputs=previous_outputs,
        current_outputs=expected_outputs,
        clip_event_port=clip_event_port,
    )


def _is_valid_cached_output_path(
    project: ProjectPaths,
    relative_path: object,
) -> bool:
    if not isinstance(relative_path, str):
        return False
    return _is_safe_project_relative_path(project, relative_path)


def _has_matching_render_metadata(
    *,
    metadata: dict | None,
    render_key: str,
    analysis_key: str,
) -> bool:
    render_metadata = metadata.get("render_metadata") if isinstance(metadata, dict) else None
    if not isinstance(render_metadata, dict):
        return False
    if str(render_metadata.get("analysis_key") or "") != analysis_key:
        return False
    if str(render_metadata.get("render_key") or "") != render_key:
        return False
    return True


def _is_safe_project_relative_path(
    project: ProjectPaths,
    relative_path: str,
) -> bool:
    if not relative_path or relative_path.startswith("../"):
        return False
    path = (project.root / relative_path).resolve()
    return project.root.resolve() in path.parents


def _managed_render_asset_paths(
    project: ProjectPaths,
    clip_name: str,
    *,
    include_raw: bool,
) -> list[str]:
    safe_clip_name = Path(clip_name).name
    stem = Path(safe_clip_name).stem
    managed = [
        (project.outputs / safe_clip_name).relative_to(project.root).as_posix(),
        (project.outputs / f"{stem}.json").relative_to(project.root).as_posix(),
    ]
    if include_raw:
        managed.append(
            (project.outputs / f"{stem}_raw.mp4")
            .relative_to(project.root)
            .as_posix()
        )
    return managed


__all__ = [
    "PIPELINE_CACHE_SCHEMA_VERSION",
    "PIPELINE_ANALYSIS_CACHE_VERSION",
    "PIPELINE_RENDER_CACHE_VERSION",
    "PIPELINE_ANALYZER_CONTRACT_VERSION",
    "PIPELINE_SUBTITLE_STYLE_CONTRACT_VERSION",
    "PipelineCacheIdentity",
    "PipelineRenderCacheHit",
    "resolve_project_video_id",
    "resolve_video_model_identifier",
    "build_pipeline_analysis_key",
    "build_pipeline_render_key",
    "build_pipeline_cache_identity",
    "load_pipeline_cache_manifest",
    "write_pipeline_cache_manifest",
    "build_segments_signature",
    "extract_pipeline_segments",
    "load_cached_pipeline_analysis",
    "record_pipeline_analysis_cache",
    "load_pipeline_render_cache_hit",
    "cleanup_stale_render_outputs",
    "record_pipeline_render_cache",
]
