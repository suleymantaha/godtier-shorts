"""Artifact, layout-safety, and clip publication helpers for workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from backend.config import ProjectPaths
from backend.core.clip_events import ClipEventPort, NullClipEventPort
from backend.core.workflow_common import move_file_atomic, write_json_atomic

LAYOUT_SAFETY_CONTRACT_VERSION = 1
VALID_LAYOUT_SAFETY_MODES = {"off", "shadow", "enforce"}
SAFE_PUBLIC_LAYOUT_STATUSES = {"safe", "degraded"}
PUBLICATION_STATUS_PUBLISH_READY = "publish_ready"
PUBLICATION_STATUS_AUTO_REPAIR = "auto_repair"
PUBLICATION_STATUS_REVIEW_REQUIRED = "review_required"
AUTO_REPAIR_STARTUP_SETTLE_MS = 400.0
LOW_SPEAKER_ACTIVITY_CONFIDENCE = 0.35
REVIEW_SUGGESTED_ACTIONS = ["force_single", "force_split", "manual_center"]


@dataclass(frozen=True)
class ProgressStepMapper:
    """Maps iterative steps into a bounded progress range."""

    start: int
    end: int
    total_steps: int

    def map(self, step_index: int) -> int:
        if self.total_steps <= 0:
            return self.end
        bounded = min(max(step_index, 0), self.total_steps)
        delta = self.end - self.start
        return self.start + int((bounded / self.total_steps) * delta)


def resolve_layout_safety_mode() -> str:
    raw = os.getenv("LAYOUT_SAFETY_MODE", "shadow").strip().lower()
    return raw if raw in VALID_LAYOUT_SAFETY_MODES else "shadow"


def build_layout_review_item(
    *,
    start_time: float,
    end_time: float,
    requested_layout: str,
    attempted_layout: str,
    layout_auto_fix_reason: str | None,
    suggested_layout: str,
    clip_index: int | None = None,
    ui_title: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "start_time": round(float(start_time), 3),
        "end_time": round(float(end_time), 3),
        "requested_layout": requested_layout,
        "attempted_layout": attempted_layout,
        "layout_auto_fix_reason": layout_auto_fix_reason,
        "suggested_layout": suggested_layout,
        "suggested_actions": list(REVIEW_SUGGESTED_ACTIONS),
    }
    if clip_index is not None:
        payload["clip_index"] = clip_index
    if ui_title:
        payload["ui_title"] = ui_title
    return payload


def build_quarantine_output_path(project: ProjectPaths, clip_filename: str) -> Path:
    quarantine_dir = project.root / ".quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    return quarantine_dir / Path(clip_filename).name


def cleanup_render_output(path: str | Path | None) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Render artifact temizlenemedi: {} - {}", path, exc)


def cleanup_render_bundle(path: str | Path | None) -> None:
    if not path:
        return
    output_path = Path(path)
    cleanup_render_output(output_path)
    cleanup_render_output(output_path.with_name(f"{output_path.stem}_raw.mp4"))
    cleanup_render_output(output_path.with_suffix(".json"))


def promote_render_bundle(
    *,
    project: ProjectPaths,
    quarantine_output: str | Path,
    clip_filename: str,
) -> Path:
    quarantine_path = Path(quarantine_output)
    public_output = project.outputs / Path(clip_filename).name
    move_file_atomic(quarantine_path, public_output)

    quarantine_raw = quarantine_path.with_name(f"{quarantine_path.stem}_raw.mp4")
    if quarantine_raw.exists():
        move_file_atomic(
            quarantine_raw,
            project.outputs / f"{public_output.stem}_raw.mp4",
        )

    return public_output


def assess_layout_safety(
    *,
    render_plan,
    requested_layout: str,
    tracking_quality: dict[str, object] | None,
    manual_center_x: float | None,
    layout_auto_fix_reason_override: str | None = None,
    layout_auto_fix_applied_override: bool | None = None,
    auto_repair_attempted: bool = False,
) -> dict[str, object]:
    tracking = dict(tracking_quality or {})
    layout_safety_mode = _resolve_render_plan_value(
        render_plan,
        "layout_safety_mode",
        resolve_layout_safety_mode(),
    )
    layout_safety_status = _resolve_layout_safety_status(render_plan, tracking)
    layout_auto_fix_reason = _resolve_layout_auto_fix_reason(
        render_plan,
        layout_auto_fix_reason_override,
    )
    layout_auto_fix_applied = _resolve_layout_auto_fix_applied(
        render_plan=render_plan,
        requested_layout=requested_layout,
        manual_center_x=manual_center_x,
        layout_auto_fix_reason=layout_auto_fix_reason,
        layout_auto_fix_applied_override=layout_auto_fix_applied_override,
    )
    quality_gate_reasons = _resolve_quality_gate_reasons(
        render_plan=render_plan,
        requested_layout=requested_layout,
        tracking=tracking,
        layout_auto_fix_reason=layout_auto_fix_reason,
    )
    render_publication_status = _resolve_render_publication_status(
        layout_safety_status=layout_safety_status,
        quality_gate_reasons=quality_gate_reasons,
    )

    return {
        "layout_auto_fix_applied": bool(layout_auto_fix_applied),
        "layout_auto_fix_reason": layout_auto_fix_reason,
        "layout_safety_status": layout_safety_status,
        "render_publication_status": render_publication_status,
        "quality_gate_reasons": quality_gate_reasons,
        "auto_repair_recommended": render_publication_status == PUBLICATION_STATUS_AUTO_REPAIR,
        "review_recommended": render_publication_status == PUBLICATION_STATUS_REVIEW_REQUIRED,
        "auto_repair_attempted": bool(auto_repair_attempted),
        "layout_safety_mode": layout_safety_mode,
        "layout_safety_contract_version": int(
            getattr(
                render_plan,
                "layout_safety_contract_version",
                LAYOUT_SAFETY_CONTRACT_VERSION,
            )
            or LAYOUT_SAFETY_CONTRACT_VERSION
        ),
        "scene_class": _resolve_render_plan_value(
            render_plan,
            "scene_class",
            "single_dynamic",
        ),
        "speaker_count_peak": int(getattr(render_plan, "speaker_count_peak", 1) or 1),
        "dominant_speaker_confidence": getattr(
            render_plan,
            "dominant_speaker_confidence",
            None,
        ),
    }


def commit_render_bundle(
    *,
    project: ProjectPaths,
    quarantine_output: str | Path,
    clip_filename: str,
    clip_metadata: dict[str, object],
    subject: str | None,
    project_id: str,
    ui_title: str | None,
    message: str,
    progress: int,
    job_id: str | None = None,
    clip_event_port: ClipEventPort | None = None,
) -> str:
    public_output = promote_render_bundle(
        project=project,
        quarantine_output=quarantine_output,
        clip_filename=clip_filename,
    )
    write_json_atomic(public_output.with_suffix(".json"), clip_metadata, indent=4)
    publish_clip_ready_event(
        subject=subject,
        job_id=job_id,
        project_id=project_id,
        clip_name=clip_filename,
        message=message,
        progress=progress,
        ui_title=ui_title,
        clip_event_port=clip_event_port,
    )
    return str(public_output)


def publish_clip_ready_event(
    *,
    subject: str | None = None,
    job_id: str | None = None,
    project_id: str,
    clip_name: str,
    message: str,
    progress: int,
    ui_title: str | None = None,
    clip_event_port: ClipEventPort | None = None,
) -> bool:
    """Broadcast a clip-ready signal after the clip metadata has been committed."""
    port = clip_event_port or NullClipEventPort()
    safe_progress = max(0, min(progress, 99))
    port.invalidate_clips_cache(reason=f"clip_ready:{project_id}/{clip_name}")
    resolved_job_id = port.resolve_clip_ready_job_id(
        subject=subject,
        project_id=project_id,
        job_id=job_id,
    )

    if not resolved_job_id:
        logger.warning(
            "event=clip_ready_job_missing project_id={} clip_name={} subject={} requested_job_id={}",
            project_id,
            clip_name,
            subject or "-",
            job_id or "-",
        )
        return False

    extra_payload: dict[str, object] = {
        "event_type": "clip_ready",
        "project_id": project_id,
        "clip_name": clip_name,
    }
    if ui_title:
        extra_payload["ui_title"] = ui_title

    port.broadcast_clip_ready(
        message=message,
        progress=safe_progress,
        job_id=resolved_job_id,
        extra=extra_payload,
    )
    return True


def persist_debug_artifacts(
    *,
    project: ProjectPaths,
    clip_name: str,
    render_report: dict | None,
    subtitle_layout_quality: dict | None,
    snap_report: dict | None,
    debug_timing: dict | None,
) -> dict | None:
    if os.getenv("DEBUG_RENDER_ARTIFACTS") != "1":
        return None

    clip_stem = Path(clip_name).stem
    debug_dir = project.debug / clip_stem
    render_payload = render_report if isinstance(render_report, dict) else {}
    subtitle_payload = (
        subtitle_layout_quality
        if isinstance(subtitle_layout_quality, dict)
        else {}
    )
    tracking_payload = render_payload.get("debug_tracking")
    chunk_payload = subtitle_payload.get("chunk_dump", [])
    snap_payload = (
        snap_report
        if isinstance(snap_report, dict)
        else {"enabled": False, "reason": "not_applicable"}
    )
    timing_payload = debug_timing if isinstance(debug_timing, dict) else {}
    overlay_source = render_payload.get("debug_overlay_temp_path")

    status = "complete"
    preferred_status = str(
        render_payload.get("debug_artifacts_status", "complete") or "complete"
    )
    if preferred_status == "partial":
        status = "partial"

    artifacts: dict[str, str] = {}
    artifact_specs = [
        ("tracking_timeline", "tracking_timeline.json", tracking_payload or {}),
        (
            "subtitle_chunks",
            "subtitle_chunks.json",
            chunk_payload if isinstance(chunk_payload, list) else [],
        ),
        ("boundary_snap", "boundary_snap.json", snap_payload),
        ("timing_report", "timing_report.json", timing_payload),
    ]
    for artifact_key, filename, payload in artifact_specs:
        status = _persist_debug_json_artifact(
            project=project,
            debug_dir=debug_dir,
            clip_name=clip_name,
            artifact_key=artifact_key,
            filename=filename,
            payload=payload,
            artifacts=artifacts,
            current_status=status,
        )

    if overlay_source and Path(str(overlay_source)).exists():
        try:
            destination = debug_dir / "tracking_overlay.mp4"
            move_file_atomic(str(overlay_source), destination)
            artifacts["tracking_overlay"] = _project_relative_path(project, destination)
        except Exception as exc:
            logger.warning("Tracking overlay artifact tasinamadi: {} - {}", clip_name, exc)
            status = "partial"
    else:
        status = "partial"

    artifacts["status"] = status
    return artifacts


def resolve_initial_slot_centers(
    opening_report: dict[str, object],
) -> tuple[float, float] | None:
    raw_centers = opening_report.get("initial_slot_centers")
    if not isinstance(raw_centers, list) or len(raw_centers) != 2:
        return None
    left, right = raw_centers
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return None
    return float(left), float(right)


def write_reburn_metadata(
    *,
    ctx,
    meta_path: str,
    transcript: list,
    existing_metadata: dict | None,
    existing_render_metadata: dict | None,
    style_name: str,
    animation_type: str,
    resolved_animation_type: str,
    resolved_layout: str,
    layout_fallback_reason: str | None,
    transcript_quality: dict,
    subtitle_layout_quality: dict,
    debug_environment: dict,
    render_quality_score: float,
    debug_artifacts: dict | None,
) -> None:
    merged_metadata = ctx._build_clip_metadata(
        transcript,
        viral_metadata=(existing_metadata or {}).get("viral_metadata"),
        render_metadata=(existing_metadata or {}).get("render_metadata"),
    )
    render_metadata = merged_metadata.get("render_metadata")
    if not isinstance(render_metadata, dict):
        render_metadata = {}
        merged_metadata["render_metadata"] = render_metadata

    render_metadata["style_name"] = style_name
    render_metadata["animation_type"] = animation_type
    render_metadata["resolved_animation_type"] = resolved_animation_type
    render_metadata["resolved_layout"] = resolved_layout
    render_metadata["layout_fallback_reason"] = layout_fallback_reason
    render_metadata["transcript_quality"] = transcript_quality
    render_metadata["subtitle_layout_quality"] = subtitle_layout_quality
    render_metadata["debug_environment"] = debug_environment
    render_metadata["render_quality_score"] = render_quality_score

    _copy_existing_render_dict(
        existing_render_metadata,
        render_metadata,
        key="debug_timing",
    )
    _copy_existing_render_dict(
        existing_render_metadata,
        render_metadata,
        key="tracking_quality",
    )
    _copy_existing_render_dict(
        existing_render_metadata,
        render_metadata,
        key="audio_validation",
    )
    _copy_existing_render_dict(
        existing_render_metadata,
        render_metadata,
        key="debug_tracking",
    )
    if debug_artifacts:
        render_metadata["debug_artifacts"] = debug_artifacts

    write_json_atomic(Path(meta_path), merged_metadata)


def _resolve_render_plan_value(render_plan, field: str, default: str) -> str:
    return str(getattr(render_plan, field, default) or default)


def _resolve_layout_safety_status(
    render_plan,
    tracking: dict[str, object],
) -> str:
    layout_safety_status = str(
        tracking.get("layout_safety_status")
        or getattr(render_plan, "layout_safety_status", "safe")
        or "safe"
    )
    panel_swap_count = int(tracking.get("panel_swap_count", 0) or 0)
    unsafe_split_frames = int(tracking.get("unsafe_split_frames", 0) or 0)
    face_edge_violation_frames = int(
        tracking.get("face_edge_violation_frames", 0) or 0
    )
    tracking_status = str(tracking.get("status", "good") or "good")
    listener_lock_suspected = bool(tracking.get("listener_lock_suspected"))
    startup_settle_ms = _safe_float(tracking.get("startup_settle_ms"), default=0.0)

    # Enforce politikasında "fallback" takip, kullanıcıya açık yayın için güvenli değildir.
    # Bu sinyali layout_safety_status'a yansıtarak review_required akışını tetikleriz.
    if tracking_status == "fallback":
        return "unsafe"

    if layout_safety_status != "unsafe":
        if panel_swap_count > 0 or unsafe_split_frames > 0:
            layout_safety_status = "unsafe"
        elif (
            tracking_status in {"degraded", "fallback"}
            or face_edge_violation_frames > 0
            or listener_lock_suspected
            or startup_settle_ms >= AUTO_REPAIR_STARTUP_SETTLE_MS
        ):
            layout_safety_status = "degraded"
        else:
            layout_safety_status = "safe"
    return layout_safety_status


def _resolve_quality_gate_reasons(
    *,
    render_plan,
    requested_layout: str,
    tracking: dict[str, object],
    layout_auto_fix_reason: str | None,
) -> list[str]:
    reasons: list[str] = []
    tracking_status = str(tracking.get("status", "good") or "good")
    if tracking_status == "fallback":
        reasons.append("tracking_fallback")
    elif tracking_status == "degraded":
        reasons.append("tracking_degraded")

    if bool(tracking.get("listener_lock_suspected")):
        reasons.append("listener_lock_suspected")

    startup_settle_ms = _safe_float(tracking.get("startup_settle_ms"), default=0.0)
    if startup_settle_ms >= AUTO_REPAIR_STARTUP_SETTLE_MS:
        reasons.append("startup_settle_slow")

    identity_confidence = _safe_float(tracking.get("identity_confidence"), default=1.0)
    if identity_confidence < 0.72:
        reasons.append("identity_unstable")

    speaker_activity = tracking.get("speaker_activity_confidence")
    if speaker_activity is not None and _safe_float(speaker_activity, default=1.0) < LOW_SPEAKER_ACTIVITY_CONFIDENCE:
        reasons.append("speaker_activity_weak")

    if (
        requested_layout in {"auto", "split"}
        and str(getattr(render_plan, "resolved_layout", "single") or "single") == "single"
        and layout_auto_fix_reason in {"split_face_safety", "split_identity_unstable"}
    ):
        reasons.append("split_layout_fallback")

    scene_class = str(getattr(render_plan, "scene_class", "") or "")
    speaker_count_peak = int(getattr(render_plan, "speaker_count_peak", 1) or 1)
    if scene_class == "dual_overlap_risky" and speaker_count_peak >= 3:
        reasons.append("multi_person_overlap_risky")

    panel_swap_count = int(tracking.get("panel_swap_count", 0) or 0)
    unsafe_split_frames = int(tracking.get("unsafe_split_frames", 0) or 0)
    if panel_swap_count > 0 or unsafe_split_frames > 0:
        reasons.append("split_runtime_unsafe")

    return list(dict.fromkeys(reasons))


def _resolve_render_publication_status(
    *,
    layout_safety_status: str,
    quality_gate_reasons: list[str],
) -> str:
    if layout_safety_status == "unsafe" or "tracking_fallback" in quality_gate_reasons or "split_runtime_unsafe" in quality_gate_reasons:
        return PUBLICATION_STATUS_REVIEW_REQUIRED
    if quality_gate_reasons:
        return PUBLICATION_STATUS_AUTO_REPAIR
    return PUBLICATION_STATUS_PUBLISH_READY


def _safe_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_layout_auto_fix_reason(
    render_plan,
    layout_auto_fix_reason_override: str | None,
) -> str | None:
    if layout_auto_fix_reason_override is not None:
        return layout_auto_fix_reason_override

    layout_auto_fix_reason = getattr(render_plan, "layout_auto_fix_reason", None)
    if layout_auto_fix_reason is not None:
        return layout_auto_fix_reason

    fallback_reason = str(getattr(render_plan, "layout_fallback_reason", "") or "")
    if fallback_reason in {"split_not_stable", "split_face_safety"}:
        return "split_face_safety"
    if fallback_reason == "split_identity_unstable":
        return "split_identity_unstable"
    return None


def _resolve_layout_auto_fix_applied(
    *,
    render_plan,
    requested_layout: str,
    manual_center_x: float | None,
    layout_auto_fix_reason: str | None,
    layout_auto_fix_applied_override: bool | None,
) -> bool:
    if layout_auto_fix_applied_override is not None:
        layout_auto_fix_applied = layout_auto_fix_applied_override
    else:
        layout_auto_fix_applied = bool(
            getattr(render_plan, "layout_auto_fix_applied", False)
        )

    resolved_layout = _resolve_render_plan_value(render_plan, "resolved_layout", "single")
    if (
        manual_center_x is None
        and requested_layout in {"auto", "split"}
        and resolved_layout != requested_layout
    ):
        layout_auto_fix_applied = True
    if layout_auto_fix_reason is not None:
        layout_auto_fix_applied = True
    return bool(layout_auto_fix_applied)


def _persist_debug_json_artifact(
    *,
    project: ProjectPaths,
    debug_dir: Path,
    clip_name: str,
    artifact_key: str,
    filename: str,
    payload: object,
    artifacts: dict[str, str],
    current_status: str,
) -> str:
    try:
        artifact_path = debug_dir / filename
        write_json_atomic(artifact_path, payload)
        artifacts[artifact_key] = _project_relative_path(project, artifact_path)
        return current_status
    except Exception as exc:
        logger.warning("{} artifact yazilamadi: {} - {}", artifact_key, clip_name, exc)
        return "partial"


def _copy_existing_render_dict(
    existing_render_metadata: dict | None,
    render_metadata: dict[str, object],
    *,
    key: str,
) -> None:
    if not isinstance(existing_render_metadata, dict):
        return
    value = existing_render_metadata.get(key)
    if isinstance(value, dict):
        render_metadata[key] = value


def _project_relative_path(project: ProjectPaths, path: Path) -> str:
    return path.relative_to(project.root).as_posix()


__all__ = [
    "LAYOUT_SAFETY_CONTRACT_VERSION",
    "SAFE_PUBLIC_LAYOUT_STATUSES",
    "REVIEW_SUGGESTED_ACTIONS",
    "ProgressStepMapper",
    "resolve_layout_safety_mode",
    "build_layout_review_item",
    "build_quarantine_output_path",
    "cleanup_render_output",
    "cleanup_render_bundle",
    "promote_render_bundle",
    "assess_layout_safety",
    "commit_render_bundle",
    "publish_clip_ready_event",
    "persist_debug_artifacts",
    "resolve_initial_slot_centers",
    "write_reburn_metadata",
]
