"""
backend/api/routes/clips.py
=================================
Üretilen klipleri yönetmek için endpoint'ler:
  GET  /api/clips
  DELETE /api/projects/{project_id}/shorts/{clip_name}
  GET  /api/clip-transcript/{clip_name}
  POST /api/upload
"""
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field

import backend.config as config
from backend.config import (
    OUTPUTS_DIR, PROJECTS_DIR, ProjectPaths,
    get_project_path, sanitize_clip_name, sanitize_project_name,
)
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.security import AuthContext, ensure_project_access, ensure_project_owner, require_policy
from backend.api.upload_validation import stream_upload_to_path, validate_upload
from backend.services.transcription import run_transcription
from backend.services.ownership import (
    build_owner_scoped_project_id,
    build_subject_hash,
    ensure_project_manifest,
    grant_support_access,
    is_support_subject_allowed,
    list_accessible_project_ids,
    read_project_manifest,
    revoke_support_access,
)
from backend.core.exceptions import (
    FileOperationError,
    InvalidInputError,
    JobExecutionError,
    MediaSubprocessError,
    TranscriptionError,
)

router = APIRouter(prefix="/api", tags=["clips"])
ProgressCallback = Callable[[str, int], None]


def finalize_job_success(job_id: str, last_message: str) -> None:
    """İşi başarıyla tamamlar ve son durum yayınını standardize eder."""
    if job_id in manager.jobs:
        manager.jobs[job_id]["status"] = "completed"
        manager.jobs[job_id]["progress"] = 100
        manager.jobs[job_id]["last_message"] = last_message
    thread_safe_broadcast({"message": last_message, "progress": 100, "status": "completed"}, job_id)
    invalidate_clips_cache(reason=f"job_success:{job_id}")


def finalize_job_error(job_id: str, error: Exception) -> None:
    """İşi hataya düşürür ve standart hata bilgisini yayınlar."""
    message = f"HATA: {error}"
    if job_id in manager.jobs:
        manager.jobs[job_id]["status"] = "error"
        manager.jobs[job_id]["error"] = str(error)
        manager.jobs[job_id]["last_message"] = message
    thread_safe_broadcast({"message": message, "progress": -1, "status": "error"}, job_id)


ALLOWED_CONTAINERS = {"mp4", "mov", "m4a", "3gp", "3g2", "mj2"}

ALLOWED_PROJECT_FILE_EXTENSIONS = {".mp4", ".json"}
ALLOWED_PROJECT_FILE_KINDS = {"clip", "master", "clip_metadata", "transcript"}
CLIPS_CACHE_TTL_SECONDS = int(os.getenv("CLIPS_CACHE_TTL_SECONDS", "20"))
CLIP_RECOVERY_JOB_PREFIX = "cliprecover_"
PROJECT_TRANSCRIPT_JOB_PREFIXES = ("upload_", "manualcut_", "projecttranscript_")
ACTIVE_JOB_STATUSES = {"queued", "processing"}
FAILED_JOB_STATUSES = {"error", "cancelled"}


class SupportGrantRequest(BaseModel):
    support_subject: str = Field(..., min_length=3)
    ttl_seconds: int = Field(default=24 * 60 * 60, ge=60, le=7 * 24 * 60 * 60)


@dataclass
class ClipsCacheState:
    """`/api/clips` için process-level in-memory cache state."""
    index: list[dict] | None = None
    index_version: int = 0
    built_at: float = 0.0
    page_cache: dict[tuple[str, int, int, int], dict] = field(default_factory=dict)


_clips_cache_state = ClipsCacheState()
_clips_cache_lock = threading.RLock()


def invalidate_clips_cache(reason: str = "unknown") -> None:
    """Klip liste cache'ini geçersiz kılar."""
    with _clips_cache_lock:
        _clips_cache_state.index = None
        _clips_cache_state.built_at = 0.0
        _clips_cache_state.page_cache.clear()
        _clips_cache_state.index_version += 1
        logger.debug(
            "🗂️ Clips cache invalidated. reason={} version={}",
            reason,
            _clips_cache_state.index_version,
        )


def build_project_file_url(project_id: str, file_kind: str, clip_name: str | None = None) -> str:
    """UI için güvenli proje dosya URL'i üretir."""
    safe_project = sanitize_project_name(project_id)
    if clip_name is None:
        return f"/api/projects/{safe_project}/files/{file_kind}"
    safe_clip = sanitize_clip_name(clip_name)
    return f"/api/projects/{safe_project}/files/{file_kind}/{safe_clip}"


def _safe_project_file_path(project_id: str, file_kind: str, clip_name: str | None = None) -> Path:
    """Whitelisted proje dosya yolunu döndürür."""
    try:
        safe_project_id = sanitize_project_name(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if file_kind not in ALLOWED_PROJECT_FILE_KINDS:
        raise HTTPException(status_code=400, detail="Geçersiz dosya türü")

    project = ProjectPaths(safe_project_id)

    if file_kind == "master":
        path = project.master_video
    elif file_kind == "transcript":
        path = project.transcript
    else:
        if not clip_name:
            raise HTTPException(status_code=400, detail="clip_name gerekli")
        try:
            safe_clip_name = sanitize_clip_name(clip_name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if file_kind == "clip":
            path = project.outputs / safe_clip_name
        else:
            stem = Path(safe_clip_name).stem
            path = project.outputs / f"{stem}.json"

    if path.suffix.lower() not in ALLOWED_PROJECT_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Bu dosya uzantısına izin verilmiyor")

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")

    return path


def build_secure_clip_url(project_id: str, clip_name: str) -> str:
    """Sadece shorts altındaki klip/metadata dosyaları için güvenli public URL üretir."""
    return f"/api/projects/{project_id}/shorts/{clip_name}"


def _resolve_project_shorts_dir(project_id: str) -> tuple[Path, str]:
    try:
        safe_project = sanitize_project_name(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    shorts_dir = get_project_path(safe_project, "shorts").resolve()
    return shorts_dir, safe_project


def _resolve_project_short_asset_path(
    project_id: str,
    clip_name: str,
    *,
    allowed_exts: set[str],
) -> tuple[Path, str, str]:
    shorts_dir, safe_project = _resolve_project_shorts_dir(project_id)

    try:
        safe_clip = sanitize_clip_name(clip_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ext = os.path.splitext(safe_clip)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=403, detail="Yalnızca .mp4 ve .json shorts varlıklarına izin verilir")

    asset_path = (shorts_dir / safe_clip).resolve()
    if shorts_dir not in asset_path.parents:
        raise HTTPException(status_code=403, detail="Geçersiz dosya yolu")

    return asset_path, safe_project, safe_clip


def _upload_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _validate_video_with_ffprobe(video_path: str) -> None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise _upload_http_error(
            status_code=400,
            code="VIDEO_VALIDATION_TIMEOUT",
            message="Video doğrulama süresi aşıldı. Lütfen dosyayı tekrar deneyin.",
        )

    if result.returncode != 0:
        raise _upload_http_error(
            status_code=400,
            code="INVALID_VIDEO_FILE",
            message="Yüklenen dosya geçerli bir video olarak doğrulanamadı.",
        )

    try:
        probe_data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        raise _upload_http_error(
            status_code=400,
            code="INVALID_VIDEO_FILE",
            message="Video bilgileri okunamadı. Lütfen geçerli bir video dosyası yükleyin.",
        )

    format_data = probe_data.get("format") if isinstance(probe_data, dict) else None
    if not isinstance(format_data, dict):
        raise _upload_http_error(
            status_code=400,
            code="INVALID_VIDEO_FILE",
            message="Video konteyner bilgisi bulunamadı.",
        )

    format_names = format_data.get("format_name")
    if not isinstance(format_names, str):
        raise _upload_http_error(
            status_code=400,
            code="INVALID_VIDEO_FILE",
            message="Video konteyner bilgisi okunamadı.",
        )

    normalized_formats = {name.strip().lower() for name in format_names.split(",") if name.strip()}
    if not normalized_formats.intersection(ALLOWED_CONTAINERS):
        raise _upload_http_error(
            status_code=400,
            code="UNSUPPORTED_CONTAINER",
            message="Desteklenmeyen video konteyneri. Lütfen MP4/MOV/M4V dosyası yükleyin.",
        )

    streams = probe_data.get("streams") if isinstance(probe_data, dict) else None
    has_video_stream = isinstance(streams, list) and any(
        isinstance(stream, dict) and stream.get("codec_type") == "video"
        for stream in streams
    )
    if not has_video_stream:
        raise _upload_http_error(
            status_code=400,
            code="MISSING_VIDEO_STREAM",
            message="Dosyada video akışı bulunamadı. Lütfen geçerli bir video dosyası yükleyin.",
        )


def prepare_uploaded_project(file: UploadFile, owner_subject: str | None = None) -> tuple[ProjectPaths, str, bool]:
    """Yüklenen videodan proje oluşturur veya mevcut projeyi reuse eder."""
    if not owner_subject:
        raise InvalidInputError("Upload işlemi için owner subject gerekli")

    try:
        validate_upload(file)
    except HTTPException as exc:
        raise _upload_http_error(
            status_code=exc.status_code,
            code="INVALID_UPLOAD",
            message=str(exc.detail),
        ) from exc

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        try:
            _bytes_written, file_hash = stream_upload_to_path(file, temp_path)
        except InvalidInputError as exc:
            raise _upload_http_error(
                status_code=413,
                code="REQUEST_TOO_LARGE",
                message=exc.message,
            ) from exc

        _validate_video_with_ffprobe(temp_path)

        project_id = build_owner_scoped_project_id("up", owner_subject, file_hash[:12])
        project = ProjectPaths(project_id)
        is_cached = project.master_video.exists() and project.transcript.exists()
        ensure_project_manifest(project_id, owner_subject=owner_subject, source="upload")

        if is_cached:
            logger.info(f"♻️ Proje zaten mevcut (Cache Hit): {project_id}")
            return project, project_id, True

        if not project.master_video.exists():
            shutil.move(temp_path, str(project.master_video))
            logger.info(f"📁 Yeni video yüklendi: {project.master_video}")
        else:
            logger.info(f"♻️ Aynı video daha önce yüklenmiş, mevcut master reuse ediliyor: {project.master_video}")

        return project, project_id, False
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def ensure_project_audio(project: ProjectPaths, progress_callback: ProgressCallback | None = None) -> str:
    """Proje videosundan WAV ses çıkarır veya mevcut sesi reuse eder."""
    audio_path = str(project.master_audio)
    if os.path.exists(audio_path):
        if progress_callback:
            progress_callback("Ses izi hazır, mevcut kütüphane kullanılıyor...", 5)
        return audio_path

    logger.info("🎙️ Video'dan ses çıkarılıyor (ffmpeg)...")
    if progress_callback:
        progress_callback("Ses çıkarılıyor...", 5)

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(project.master_video),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaSubprocessError("Ses çıkarma işlemi timeout oldu (15 dakika)") from exc
    except OSError as exc:
        raise FileOperationError("FFmpeg çalıştırılamadı", details=str(exc)) from exc
    if result.returncode != 0:
        raise MediaSubprocessError("FFmpeg ile ses çıkarma başarısız oldu", details=result.stderr[-300:])

    logger.info(f"✅ WAV çıkarıldı: {audio_path}")
    return audio_path


def ensure_project_transcript(
    project: ProjectPaths,
    progress_callback: ProgressCallback | None = None,
) -> str:
    """Proje transkriptini üretir veya mevcut transkripti reuse eder."""
    transcript_path = str(project.transcript)
    if os.path.exists(transcript_path):
        if progress_callback:
            progress_callback("Transkript hazır, mevcut kütüphane kullanılıyor...", 35)
        return transcript_path

    audio_path = ensure_project_audio(project, progress_callback)
    run_transcription(
        audio_file=audio_path,
        output_json=transcript_path,
        status_callback=progress_callback,
    )
    return transcript_path


def normalize_clip_payload(payload: object, clip_name: str, project_id: str | None) -> dict:
    if isinstance(payload, list):
        return {
            "transcript": payload,
            "viral_metadata": None,
            "render_metadata": {
                "clip_name": clip_name,
                "project_id": project_id,
            },
        }

    if isinstance(payload, dict):
        transcript = payload.get("transcript")
        if not isinstance(transcript, list):
            transcript = []

        render_metadata = payload.get("render_metadata")
        if not isinstance(render_metadata, dict):
            render_metadata = {}

        render_metadata.setdefault("clip_name", clip_name)
        render_metadata.setdefault("project_id", project_id)

        return {
            "transcript": transcript,
            "viral_metadata": payload.get("viral_metadata"),
            "render_metadata": render_metadata,
        }

    return {
        "transcript": [],
        "viral_metadata": None,
        "render_metadata": {
            "clip_name": clip_name,
            "project_id": project_id,
        },
    }


def resolve_clip_asset_paths(clip_name: str, project_id: str | None = None) -> tuple[Path, Path, str | None]:
    """Resolve clip video/metadata paths for project storage only."""
    resolved_project_id = project_id
    metadata_name = clip_name.replace(".mp4", ".json")

    if not resolved_project_id:
        raise InvalidInputError("project_id zorunlu")

    return (
        get_project_path(resolved_project_id, "shorts", clip_name),
        get_project_path(resolved_project_id, "shorts", metadata_name),
        resolved_project_id,
    )


def _clip_asset_exists(project_id: str, clip_name: str) -> bool:
    video_path, metadata_path, _resolved_project_id = resolve_clip_asset_paths(clip_name, project_id)
    return video_path.exists() or metadata_path.exists()


def resolve_accessible_clip_project_id(
    subject: str,
    clip_name: str,
    requested_project_id: str | None,
) -> str | None:
    normalized_requested = _normalize_project_match(requested_project_id)
    accessible_ids = list_accessible_project_ids(subject)

    if normalized_requested and normalized_requested in accessible_ids and _clip_asset_exists(normalized_requested, clip_name):
        return normalized_requested

    matching_projects = [
        project_id
        for project_id in accessible_ids
        if _clip_asset_exists(project_id, clip_name)
    ]

    if len(matching_projects) == 1:
        return matching_projects[0]

    return None


def load_clip_payload(clip_name: str, project_id: str | None = None) -> tuple[dict, Path, Path, str | None]:
    """Load clip metadata and normalize legacy/list payload variants."""
    video_path, metadata_path, resolved_project_id = resolve_clip_asset_paths(clip_name, project_id)
    if not metadata_path.exists():
        return normalize_clip_payload([], clip_name, resolved_project_id), video_path, metadata_path, resolved_project_id

    with open(metadata_path, "r", encoding="utf-8") as f:
        return (
            normalize_clip_payload(json.load(f), clip_name, resolved_project_id),
            video_path,
            metadata_path,
            resolved_project_id,
        )


def _normalize_project_match(project_id: str | None) -> str | None:
    return project_id or None


def _job_matches_project(job: dict, project_id: str | None) -> bool:
    return _normalize_project_match(job.get("project_id")) == _normalize_project_match(project_id)


def _sorted_matching_jobs(
    predicate: Callable[[dict], bool],
    statuses: set[str] | None = None,
) -> list[dict]:
    matching_jobs: list[dict] = []
    for job in manager.jobs.values():
        if statuses is not None and str(job.get("status")) not in statuses:
            continue
        if predicate(job):
            matching_jobs.append(job)
    return sorted(matching_jobs, key=lambda job: float(job.get("created_at", 0.0)), reverse=True)


def find_project_transcript_job(
    project_id: str | None,
    statuses: set[str] | None = None,
) -> dict | None:
    if not _normalize_project_match(project_id):
        return None

    jobs = _sorted_matching_jobs(
        lambda job: _job_matches_project(job, project_id)
        and any(str(job.get("job_id", "")).startswith(prefix) for prefix in PROJECT_TRANSCRIPT_JOB_PREFIXES),
        statuses,
    )
    return jobs[0] if jobs else None


def find_clip_recovery_job(
    clip_name: str,
    project_id: str | None,
    statuses: set[str] | None = None,
) -> dict | None:
    normalized_project_id = _normalize_project_match(project_id)
    jobs = _sorted_matching_jobs(
        lambda job: str(job.get("job_id", "")).startswith(CLIP_RECOVERY_JOB_PREFIX)
        and job.get("clip_name") == clip_name
        and _normalize_project_match(job.get("project_id")) == normalized_project_id,
        statuses,
    )
    return jobs[0] if jobs else None


def _job_error_message(job: dict | None) -> str | None:
    if not job:
        return None
    error = job.get("error")
    if isinstance(error, str) and error.strip():
        return error
    message = job.get("last_message")
    if isinstance(message, str) and message.strip():
        return message
    return None


def _resolve_recommended_recovery_strategy(capabilities: dict) -> str | None:
    if capabilities.get("can_recover_from_project"):
        return "project_slice"
    if capabilities.get("can_transcribe_source"):
        return "transcribe_source"
    return None


def resolve_project_transcript_state(project_id: str | None) -> dict:
    normalized_project_id = _normalize_project_match(project_id)
    if not normalized_project_id:
        return {
            "transcript_status": "ready",
            "active_job_id": None,
            "last_error": None,
        }

    transcript_path = ProjectPaths(normalized_project_id).transcript
    if transcript_path.exists():
        return {
            "transcript_status": "ready",
            "active_job_id": None,
            "last_error": None,
        }

    active_job = find_project_transcript_job(normalized_project_id, ACTIVE_JOB_STATUSES)
    if active_job:
        return {
            "transcript_status": "pending",
            "active_job_id": active_job.get("job_id"),
            "last_error": None,
        }

    failed_job = find_project_transcript_job(normalized_project_id, FAILED_JOB_STATUSES)
    return {
        "transcript_status": "failed",
        "active_job_id": None,
        "last_error": _job_error_message(failed_job),
    }


def _has_recovery_time_range(render_metadata: object) -> bool:
    if not isinstance(render_metadata, dict):
        return False

    start_time = render_metadata.get("start_time")
    end_time = render_metadata.get("end_time")
    return (
        isinstance(start_time, (int, float))
        and isinstance(end_time, (int, float))
        and end_time > start_time
    )


def build_clip_transcript_capabilities(
    payload: dict,
    video_path: Path,
    metadata_path: Path,
    resolved_project_id: str | None,
) -> dict:
    """Expose the frontend-facing recovery capabilities for a clip transcript."""
    transcript = payload.get("transcript")
    render_metadata = payload.get("render_metadata")
    raw_video_path = video_path.with_name(f"{video_path.stem}_raw.mp4")
    project_has_transcript = bool(
        resolved_project_id and ProjectPaths(resolved_project_id).transcript.exists()
    )

    return {
        "has_clip_metadata": metadata_path.exists(),
        "has_clip_transcript": isinstance(transcript, list) and len(transcript) > 0,
        "has_raw_backup": raw_video_path.exists(),
        "project_has_transcript": project_has_transcript,
        "can_recover_from_project": project_has_transcript and _has_recovery_time_range(render_metadata),
        "can_transcribe_source": raw_video_path.exists() or video_path.exists(),
        "resolved_project_id": resolved_project_id,
    }


def resolve_clip_transcript_state(
    clip_name: str,
    requested_project_id: str | None,
    payload: dict,
    capabilities: dict,
    resolved_project_id: str | None,
) -> dict:
    recommended_strategy = _resolve_recommended_recovery_strategy(capabilities)
    has_render_range = _has_recovery_time_range(payload.get("render_metadata"))

    if capabilities.get("has_clip_transcript"):
        return {
            "transcript_status": "ready",
            "recommended_strategy": None,
            "active_job_id": None,
            "last_error": None,
        }

    recovery_project_id = resolved_project_id or requested_project_id
    active_recovery_job = find_clip_recovery_job(clip_name, recovery_project_id, ACTIVE_JOB_STATUSES)
    if active_recovery_job:
        return {
            "transcript_status": "recovering",
            "recommended_strategy": active_recovery_job.get("recovery_strategy") or recommended_strategy,
            "active_job_id": active_recovery_job.get("job_id"),
            "last_error": None,
        }

    active_project_job = None
    if has_render_range and not capabilities.get("project_has_transcript"):
        active_project_job = find_project_transcript_job(resolved_project_id, ACTIVE_JOB_STATUSES)
    if active_project_job:
        return {
            "transcript_status": "project_pending",
            "recommended_strategy": "project_slice",
            "active_job_id": active_project_job.get("job_id"),
            "last_error": None,
        }

    failed_recovery_job = find_clip_recovery_job(clip_name, recovery_project_id, FAILED_JOB_STATUSES)
    if failed_recovery_job:
        return {
            "transcript_status": "failed",
            "recommended_strategy": recommended_strategy,
            "active_job_id": None,
            "last_error": _job_error_message(failed_recovery_job),
        }

    failed_project_job = None
    if has_render_range and not capabilities.get("project_has_transcript"):
        failed_project_job = find_project_transcript_job(resolved_project_id, FAILED_JOB_STATUSES)

    if recommended_strategy:
        return {
            "transcript_status": "needs_recovery",
            "recommended_strategy": recommended_strategy,
            "active_job_id": None,
            "last_error": _job_error_message(failed_project_job),
        }

    return {
        "transcript_status": "failed" if failed_project_job else "needs_recovery",
        "recommended_strategy": None,
        "active_job_id": None,
        "last_error": _job_error_message(failed_project_job),
    }


def build_clip_transcript_response(clip_name: str, project_id: str | None = None) -> dict:
    payload, video_path, metadata_path, resolved_project_id = load_clip_payload(clip_name, project_id)
    capabilities = build_clip_transcript_capabilities(
        payload,
        video_path,
        metadata_path,
        resolved_project_id,
    )
    payload["capabilities"] = capabilities
    payload.update(
        resolve_clip_transcript_state(
            clip_name=clip_name,
            requested_project_id=project_id,
            payload=payload,
            capabilities=capabilities,
            resolved_project_id=resolved_project_id,
        )
    )
    return payload


def extract_ui_title(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""

    viral_metadata = payload.get("viral_metadata")
    if isinstance(viral_metadata, dict):
        ui_title = viral_metadata.get("ui_title")
        if isinstance(ui_title, str):
            return ui_title

    render_metadata = payload.get("render_metadata")
    if isinstance(render_metadata, dict):
        clip_name = render_metadata.get("clip_name")
        if isinstance(clip_name, str):
            return clip_name.replace(".mp4", "")

    return ""


def extract_clip_duration(payload: object) -> float | None:
    if not isinstance(payload, dict):
        return None

    render_metadata = payload.get("render_metadata")
    if not isinstance(render_metadata, dict):
        return None

    start_time = render_metadata.get("start_time")
    end_time = render_metadata.get("end_time")
    if isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
        duration = float(end_time) - float(start_time)
        if duration > 0:
            return duration

    debug_timing = render_metadata.get("debug_timing")
    if not isinstance(debug_timing, dict):
        return None

    merged_output_duration = debug_timing.get("merged_output_duration")
    if isinstance(merged_output_duration, (int, float)) and float(merged_output_duration) > 0:
        return float(merged_output_duration)

    return None


def _build_clip_index_entry(
    project_id: str,
    clip_file: Path,
    *,
    has_transcript: bool,
    duration: float | None = None,
    resolved_project_id: str | None = None,
    transcript_status: str | None = None,
    ui_title: str = "",
) -> dict[str, object]:
    return {
        "name": clip_file.name,
        "project": project_id,
        "url": build_project_file_url(project_id, "clip", clip_file.name),
        "has_transcript": has_transcript,
        "resolved_project_id": resolved_project_id,
        "transcript_status": transcript_status,
        "ui_title": ui_title,
        "created_at": clip_file.stat().st_ctime,
        "duration": duration,
    }


def _resolve_clip_index_transcript_details(
    project_id: str,
    clip_file: Path,
    metadata_path: Path,
    payload: dict | None = None,
) -> tuple[bool, str | None, str | None]:
    normalized_payload = payload if payload is not None else normalize_clip_payload([], clip_file.name, project_id)
    capabilities = build_clip_transcript_capabilities(
        normalized_payload,
        clip_file,
        metadata_path,
        project_id,
    )
    state = resolve_clip_transcript_state(
        clip_name=clip_file.name,
        requested_project_id=project_id,
        payload=normalized_payload,
        capabilities=capabilities,
        resolved_project_id=project_id,
    )
    return (
        bool(capabilities.get("has_clip_transcript")),
        state.get("transcript_status"),
        capabilities.get("resolved_project_id"),
    )


def _is_internal_short_asset(filename: str) -> bool:
    """Exclude non-user-facing intermediate shorts assets from listings."""
    stem = Path(filename).stem
    return filename.startswith("temp_") or stem.endswith("_raw") or stem.endswith("_temp_reburn")


def _count_legacy_flat_project_dirs(projects_root: Path) -> int:
    """Count legacy/flat project folders that are excluded by strict owner-scoped layout."""
    legacy_flat_dirs = 0
    for candidate in projects_root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            config.sanitize_subject_hash(candidate.name)
        except ValueError:
            legacy_flat_dirs += 1
    return legacy_flat_dirs


def _scan_clips_index() -> list[dict]:
    """Projeleri tarayıp normalize klip indeksini oluşturur."""
    clips: list[dict] = []
    if not config.PROJECTS_DIR.exists():
        return clips

    stats = {
        "projects_discovered": 0,
        "projects_scanned": 0,
        "projects_manifest_missing": 0,
        "projects_manifest_inactive": 0,
        "projects_without_shorts": 0,
        "files_non_mp4_skipped": 0,
        "files_internal_skipped": 0,
        "files_metadata_missing_skipped": 0,
        "files_metadata_invalid_skipped": 0,
        "clips_indexed": 0,
        "legacy_flat_dirs": _count_legacy_flat_project_dirs(config.PROJECTS_DIR),
    }

    for project_dir in config.iter_project_dirs(config.PROJECTS_DIR):
        stats["projects_discovered"] += 1
        manifest = read_project_manifest(project_dir.name)
        if manifest is None:
            stats["projects_manifest_missing"] += 1
            continue
        if manifest.status != "active":
            stats["projects_manifest_inactive"] += 1
            continue

        stats["projects_scanned"] += 1
        shorts_dir = project_dir / "shorts"
        if not shorts_dir.exists():
            stats["projects_without_shorts"] += 1
            continue

        for clip_file in shorts_dir.iterdir():
            if clip_file.suffix != ".mp4":
                stats["files_non_mp4_skipped"] += 1
                continue
            if _is_internal_short_asset(clip_file.name):
                stats["files_internal_skipped"] += 1
                continue

            meta_path = shorts_dir / clip_file.name.replace(".mp4", ".json")
            if not meta_path.exists():
                has_transcript, transcript_status, resolved_project_id = _resolve_clip_index_transcript_details(
                    project_dir.name,
                    clip_file,
                    meta_path,
                )
                stats["files_metadata_missing_skipped"] += 1
                clips.append(
                    _build_clip_index_entry(
                        project_dir.name,
                        clip_file,
                        has_transcript=has_transcript,
                        resolved_project_id=resolved_project_id,
                        transcript_status=transcript_status,
                    )
                )
                stats["clips_indexed"] += 1
                continue

            ui_title = ""
            duration = None
            has_transcript = False
            transcript_status = None
            resolved_project_id = project_dir.name
            try:
                with open(meta_path, "r", encoding="utf-8") as metadata_file:
                    meta_data = json.load(metadata_file)
                    normalized_payload = normalize_clip_payload(meta_data, clip_file.name, project_dir.name)
                    ui_title = extract_ui_title(meta_data)
                    duration = extract_clip_duration(meta_data)
                    has_transcript, transcript_status, resolved_project_id = _resolve_clip_index_transcript_details(
                        project_dir.name,
                        clip_file,
                        meta_path,
                        normalized_payload,
                    )
            except json.JSONDecodeError as e:
                stats["files_metadata_invalid_skipped"] += 1
                logger.warning(f"JSON decode error in {meta_path}: {e}")
                has_transcript, transcript_status, resolved_project_id = _resolve_clip_index_transcript_details(
                    project_dir.name,
                    clip_file,
                    meta_path,
                )
            except OSError as e:
                stats["files_metadata_invalid_skipped"] += 1
                logger.error(f"Error reading metadata {meta_path}: {e}")
                has_transcript, transcript_status, resolved_project_id = _resolve_clip_index_transcript_details(
                    project_dir.name,
                    clip_file,
                    meta_path,
                )
            clips.append(
                _build_clip_index_entry(
                    project_dir.name,
                    clip_file,
                    has_transcript=has_transcript,
                    duration=duration,
                    resolved_project_id=resolved_project_id,
                    transcript_status=transcript_status,
                    ui_title=ui_title,
                )
            )
            stats["clips_indexed"] += 1

    sorted_clips = sorted(clips, key=lambda x: x["created_at"], reverse=True)
    logger.debug(
        (
            "🗂️ Clip index health: discovered={} scanned={} manifest_missing={} "
            "manifest_inactive={} no_shorts={} indexed={} non_mp4_skipped={} "
            "internal_skipped={} metadata_missing_skipped={} metadata_invalid_skipped={} "
            "legacy_flat_excluded={}"
        ),
        stats["projects_discovered"],
        stats["projects_scanned"],
        stats["projects_manifest_missing"],
        stats["projects_manifest_inactive"],
        stats["projects_without_shorts"],
        stats["clips_indexed"],
        stats["files_non_mp4_skipped"],
        stats["files_internal_skipped"],
        stats["files_metadata_missing_skipped"],
        stats["files_metadata_invalid_skipped"],
        stats["legacy_flat_dirs"],
    )
    return sorted_clips


def _get_clip_index() -> tuple[list[dict], int]:
    """TTL + explicit invalidation destekli clip index döndürür."""
    now = time.time()
    with _clips_cache_lock:
        is_expired = (
            _clips_cache_state.index is None
            or (now - _clips_cache_state.built_at) > CLIPS_CACHE_TTL_SECONDS
        )
        if is_expired:
            _clips_cache_state.index = _scan_clips_index()
            _clips_cache_state.built_at = now
            _clips_cache_state.page_cache.clear()
        return _clips_cache_state.index, _clips_cache_state.index_version


@router.get("/projects")
async def list_projects(
    auth: AuthContext = Depends(require_policy("view_projects")),
) -> dict:
    """Proje klasörlerini listeler. master.mp4 ve transcript.json varlığını döner."""
    projects = []
    accessible_ids = list_accessible_project_ids(auth.subject)
    if config.PROJECTS_DIR.exists():
        for project_id in accessible_ids:
            project = ProjectPaths(project_id)
            if not project.root.is_dir():
                continue
            projects.append({
                **resolve_project_transcript_state(project_id),
                "id": project_id,
                "has_master": project.master_video.exists(),
                "has_transcript": project.transcript.exists(),
            })
    return {"projects": sorted(projects, key=lambda p: p["id"])}


@router.post("/projects/{project_id}/support-grants")
async def create_project_support_grant(
    request: Request,
    project_id: str,
    payload: SupportGrantRequest,
    auth: AuthContext = Depends(require_policy("manage_support_grants")),
) -> dict:
    try:
        safe_project_id = sanitize_project_name(project_id)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e

    ensure_project_owner(request, auth, safe_project_id)
    support_subject = payload.support_subject.strip()
    if not is_support_subject_allowed(support_subject):
        raise InvalidInputError("Support subject allowlist disinda")

    manifest = grant_support_access(
        safe_project_id,
        owner_subject=auth.subject,
        support_subject=support_subject,
        ttl_seconds=payload.ttl_seconds,
    )
    logger.info(
        "🔐 Security event=support_grant_created subject={} project_id={} support_subject_hash={}",
        auth.subject,
        safe_project_id,
        build_subject_hash(support_subject),
    )
    return {
        "status": "granted",
        "project_id": safe_project_id,
        "support_subject_hash": build_subject_hash(support_subject),
        "grant_count": len(manifest.support_grants),
    }


@router.delete("/projects/{project_id}/support-grants")
async def delete_project_support_grant(
    request: Request,
    project_id: str,
    support_subject: str = Query(..., min_length=3),
    auth: AuthContext = Depends(require_policy("manage_support_grants")),
) -> dict:
    try:
        safe_project_id = sanitize_project_name(project_id)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e

    ensure_project_owner(request, auth, safe_project_id)
    normalized_support_subject = support_subject.strip()
    manifest = revoke_support_access(
        safe_project_id,
        owner_subject=auth.subject,
        support_subject=normalized_support_subject,
    )
    logger.info(
        "🔐 Security event=support_grant_revoked subject={} project_id={} support_subject_hash={}",
        auth.subject,
        safe_project_id,
        build_subject_hash(normalized_support_subject),
    )
    return {
        "status": "revoked",
        "project_id": safe_project_id,
        "grant_count": len(manifest.support_grants),
    }


@router.get("/projects/{project_id}/master")
async def get_project_master_video(
    request: Request,
    project_id: str,
    auth: AuthContext = Depends(require_policy("view_project_media")),
) -> FileResponse:
    """Proje master videosunu kontrollü olarak servis eder."""
    try:
        safe_project = sanitize_project_name(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ensure_project_access(request, auth, safe_project)

    path = ProjectPaths(safe_project).master_video.resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Master video bulunamadı")

    return FileResponse(path=path, media_type="video/mp4", filename="master.mp4")


@router.get("/projects/{project_id}/shorts/{clip_name}")
async def get_project_short_asset(
    request: Request,
    project_id: str,
    clip_name: str,
    auth: AuthContext = Depends(require_policy("view_project_media")),
) -> FileResponse:
    """Sadece proje shorts klasöründeki .mp4/.json dosyalarını kontrollü olarak servis eder."""
    ensure_project_access(request, auth, project_id, clip_name=clip_name)
    asset_path, _safe_project, safe_clip = _resolve_project_short_asset_path(
        project_id,
        clip_name,
        allowed_exts={".mp4", ".json"},
    )
    if not asset_path.exists() or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")

    ext = os.path.splitext(safe_clip)[1].lower()
    media_type = "video/mp4" if ext == ".mp4" else "application/json"
    return FileResponse(path=asset_path, media_type=media_type, filename=safe_clip)


@router.delete("/projects/{project_id}/shorts/{clip_name}")
async def delete_project_short(
    request: Request,
    project_id: str,
    clip_name: str,
    auth: AuthContext = Depends(require_policy("delete_clip")),
) -> dict:
    """Belirli bir klibin kullanıcıya açık shorts varlıklarını siler."""
    ensure_project_access(request, auth, project_id, clip_name=clip_name)
    shorts_dir, safe_project = _resolve_project_shorts_dir(project_id)

    try:
        safe_clip = sanitize_clip_name(clip_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if Path(safe_clip).suffix.lower() != ".mp4" or _is_internal_short_asset(safe_clip):
        raise HTTPException(status_code=400, detail="Yalnızca kullanıcıya açık .mp4 klipleri silinebilir")

    stem = Path(safe_clip).stem
    managed_assets = [
        (shorts_dir / safe_clip).resolve(),
        (shorts_dir / f"{stem}.json").resolve(),
        (shorts_dir / f"{stem}_raw.mp4").resolve(),
    ]
    for asset_path in managed_assets:
        if shorts_dir not in asset_path.parents:
            raise HTTPException(status_code=403, detail="Geçersiz dosya yolu")

    deleted = False
    for asset_path in managed_assets:
        if not asset_path.exists() or not asset_path.is_file():
            continue
        try:
            asset_path.unlink()
        except OSError as exc:
            raise FileOperationError("Klip dosyalari silinemedi", details=str(exc)) from exc
        deleted = True

    if deleted:
        invalidate_clips_cache(reason=f"clip_deleted:{safe_project}/{safe_clip}")

    return {
        "status": "deleted" if deleted else "not_found",
        "deleted": deleted,
        "project_id": safe_project,
        "clip_name": safe_clip,
    }


@router.get("/clips")
async def list_clips(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_policy("view_clips")),
) -> dict:
    """Proje klasörlerindeki tüm videoları listeler."""
    clips_sorted, index_version = _get_clip_index()
    accessible_ids = set(list_accessible_project_ids(auth.subject))
    subject_cache_key = build_subject_hash(auth.subject)
    cache_key = (subject_cache_key, page, page_size, index_version)
    with _clips_cache_lock:
        cached_response = _clips_cache_state.page_cache.get(cache_key)
    if cached_response is not None:
        return cached_response

    visible_clips = [
        clip
        for clip in clips_sorted
        if str(clip.get("project") or "") in accessible_ids
    ]

    start = (page - 1) * page_size
    end = start + page_size
    paginated = visible_clips[start:end]
    total = len(visible_clips)

    response = {
        "clips": paginated,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": end < total,
    }
    with _clips_cache_lock:
        _clips_cache_state.page_cache[cache_key] = response
    return response


@router.get("/clip-transcript/{clip_name}")
async def get_clip_transcript(
    request: Request,
    clip_name: str,
    project_id: str | None = None,
    auth: AuthContext = Depends(require_policy("view_clip_transcript")),
) -> dict:
    """Belirli bir klibin transkriptini getirir."""
    if not project_id:
        raise InvalidInputError("project_id zorunlu")
    try:
        clip_name = sanitize_clip_name(clip_name)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e
    try:
        safe_project_id = sanitize_project_name(project_id)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e
    resolved_project_id = resolve_accessible_clip_project_id(auth.subject, clip_name, safe_project_id)
    if not resolved_project_id:
        ensure_project_access(request, auth, safe_project_id, clip_name=clip_name)
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı")

    ensure_project_access(request, auth, resolved_project_id, clip_name=clip_name)
    return build_clip_transcript_response(clip_name, resolved_project_id)


@router.get("/projects/{project_id}/files/{file_kind}")
async def get_project_file(
    request: Request,
    project_id: str,
    file_kind: str,
    clip_name: str | None = None,
    auth: AuthContext = Depends(require_policy("view_project_media")),
):
    """Yalnızca whitelist edilen proje dosyalarını döndürür."""
    ensure_project_access(request, auth, project_id, clip_name=clip_name)
    path = _safe_project_file_path(project_id, file_kind, clip_name)
    media_type = "video/mp4" if path.suffix.lower() == ".mp4" else "application/json"
    return FileResponse(path=str(path), media_type=media_type, filename=path.name)


@router.get("/projects/{project_id}/files/{file_kind}/{clip_name}")
async def get_project_file_with_clip_name(
    request: Request,
    project_id: str,
    file_kind: str,
    clip_name: str,
    auth: AuthContext = Depends(require_policy("view_project_media")),
):
    """Klip bazlı dosyaları query string olmadan döndürür."""
    ensure_project_access(request, auth, project_id, clip_name=clip_name)
    path = _safe_project_file_path(project_id, file_kind, clip_name)
    media_type = "video/mp4" if path.suffix.lower() == ".mp4" else "application/json"
    return FileResponse(path=str(path), media_type=media_type, filename=path.name)


@router.post("/upload")
async def upload_local_video(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_policy("upload")),
) -> dict:
    """Arayüzden yüklenen videoyu kaydeder, bir proje oluşturur ve transkripsiyon başlatır."""
    project, project_id, is_cached = prepare_uploaded_project(file, owner_subject=auth.subject)

    if is_cached:
        return {
            "status": "cached",
            "job_id": f"cached_{int(time.time())}",
            "message": "Video zaten analiz edilmiş, kütüphaneden getiriliyor.",
            "project_id": project_id,
        }

    manager.assert_subject_can_enqueue(auth.subject)

    # 4. Transkripsiyon başlat
    job_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": str(project.master_video),
        "style": "UPLOAD",
        "status": "queued",
        "progress": 0,
        "last_message": "Video yüklendi, transkripsiyon bekliyor...",
        "created_at": time.time(),
        "project_id": project_id,
        "subject": auth.subject,
    }
    manager.seed_job_timeline(
        job_id,
        message="Video yüklendi, transkripsiyon bekliyor...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        manager.jobs[job_id]["status"] = "queued"
        manager.jobs[job_id]["last_message"] = "İşlem sırası bekleniyor..."
        thread_safe_broadcast({"message": "İşlem sırası bekleniyor...", "progress": 0}, job_id)

        async with manager.processing_lock:
            try:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Transkripsiyon başladı..."
                thread_safe_broadcast({"message": "Transkripsiyon başladı...", "progress": 1}, job_id)

                await asyncio.to_thread(
                    ensure_project_transcript,
                    project,
                    lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
                )

                finalize_job_success(job_id, "Transkripsiyon tamamlandı.")
            except Exception as exc:
                logger.error(f"Upload transkripsiyon hatası ({job_id}): {exc}")
                finalize_job_error(job_id, exc)

    asyncio.create_task(_run())
    return {"status": "uploaded", "job_id": job_id, "message": "Video yüklendi, transkripsiyon başladı.", "project_id": project_id}
