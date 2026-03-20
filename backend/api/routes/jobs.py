"""
backend/api/routes/jobs.py
============================
İş kuyruğu ile ilgili endpoint'ler:
  POST /api/start-job
  GET  /api/jobs
  POST /api/cancel-job/{job_id}
  GET  /api/styles
"""
import asyncio
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from backend.config import ProjectPaths, YOLO_MODEL_PATH
from backend.models.schemas import JobRequest
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.routes.clips import invalidate_clips_cache
from backend.api.security import AuthContext, require_policy
from backend.core.command_runner import CommandRunner
from backend.core.render_contracts import resolve_duration_range
from backend.core.orchestrator import GodTierShortsCreator
from backend.core.exceptions import JobExecutionError, NotFoundError
from backend.core.workflow_helpers import (
    build_pipeline_cache_identity,
    build_segments_signature,
    extract_pipeline_segments,
    load_cached_pipeline_analysis,
    load_pipeline_render_cache_hit,
    resolve_video_model_identifier,
)
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest
from backend.services.subtitle_styles import StyleManager

router = APIRouter(prefix="/api", tags=["jobs"])


def _finalize_job(job_id: str, status: str, *, progress: int | None = None, error: str | None = None) -> None:
    job = manager.jobs.get(job_id)
    if not job:
        return
    job["status"] = status
    if progress is not None:
        job["progress"] = progress
    if error is not None:
        job["error"] = error


def _build_cache_status_message(cache_status: dict[str, Any]) -> str:
    if bool(cache_status.get("render_cached")):
        return "Bu video icin ayni ayarlarla hazir videolar bulundu."
    if bool(cache_status.get("analysis_cached")):
        return "Bu video icin uygun analiz bulundu. Istersen videolari dogrudan olusturabiliriz."
    if bool(cache_status.get("project_cached")):
        return "Bu video daha once islendi. Bu ayarlarda yeni bir islem yapilacak."
    return "Bu video daha once islenmemis."


def _build_start_job_cached_message(cache_status: dict[str, Any]) -> str:
    if bool(cache_status.get("render_cached")):
        return "Hazir videolar bulundu. Mevcut sonuclar simdi getiriliyor."
    return "Bu video daha once islendi. Islem mevcut proje uzerinden devam edecek."


# -------------------------------------------------------------------------
# Arka plan iş çalıştırıcısı
# -------------------------------------------------------------------------

async def run_gpu_job(job_id: str, request: JobRequest) -> None:
    """GPU işini kuyruğa sokar ve sırası gelince çalıştırır."""
    try:
        async with manager.gpu_lock:
            if manager.jobs.get(job_id, {}).get("status") == "cancelled":
                logger.warning(f"🚫 Başlamadan iptal edildi: {job_id}")
                return

            manager.jobs[job_id]["status"] = "processing"
            logger.info(f"🔒 GPU Kilidi Alındı: {job_id}")

            callback = lambda s: thread_safe_broadcast(s, job_id)
            cancel_event = manager.jobs.get(job_id, {}).get("cancel_event")
            orchestrator = GodTierShortsCreator(
                ui_callback=callback,
                cancel_event=cancel_event,
                subject=manager.jobs.get(job_id, {}).get("subject"),
            )
            orchestrator.analyzer.engine = request.ai_engine

            duration_min, duration_max = resolve_duration_range(
                request.duration_min if not request.auto_mode else None,
                request.duration_max if not request.auto_mode else None,
            )

            try:
                await orchestrator.run_pipeline_async(
                    request.youtube_url,
                    request.style_name,
                    request.animation_type,
                    request.layout,
                    request.skip_subtitles,
                    request.num_clips,
                    duration_min,
                    duration_max,
                    request.resolution,
                    request.force_reanalyze,
                    request.force_rerender,
                )
                _finalize_job(job_id, "completed", progress=100)
                thread_safe_broadcast(
                    {"message": "İşlem tamamlandı.", "progress": 100, "status": "completed"},
                    job_id,
                )
                invalidate_clips_cache(reason=f"job_success:{job_id}")
                logger.success(f"🔓 İşlem tamamlandı: {job_id}")
            except asyncio.CancelledError:
                _finalize_job(job_id, "cancelled")
                logger.warning(f"🛑 İptal edildi: {job_id}")
                raise
            finally:
                orchestrator.cleanup_gpu()

    except asyncio.CancelledError:
        _finalize_job(job_id, "cancelled")
    except (RuntimeError, ValueError, OSError) as exc:
        if "cancelled" in str(exc).lower():
            _finalize_job(job_id, "cancelled")
            logger.warning(f"🛑 İptal edildi: {job_id}")
        else:
            mapped_error = JobExecutionError("Arka plan işi çalıştırılamadı", details=str(exc))
            logger.error(f"İş hatası ({job_id}): {mapped_error.message} | details={mapped_error.details}")
            _finalize_job(job_id, "error", error=mapped_error.message)
        await manager.broadcast_progress(str(exc), -1, job_id)


# -------------------------------------------------------------------------
# Endpoint'ler
# -------------------------------------------------------------------------

@router.get("/styles")
async def get_available_styles(
    _: AuthContext = Depends(require_policy("view_styles")),
) -> dict:
    """Arayüzdeki Dropdown için mevcut stilleri döner."""
    return {
        "styles": StyleManager.list_presets(),
        "animations": StyleManager.list_animation_options(),
    }


async def _inspect_pipeline_cache_state(subject: str, request: JobRequest) -> dict[str, Any]:
    duration_min, duration_max = resolve_duration_range(
        request.duration_min if not request.auto_mode else None,
        request.duration_max if not request.auto_mode else None,
    )

    command_runner = CommandRunner(threading.Event())
    rc, stdout, stderr = await command_runner.run_async(
        ["yt-dlp", "--get-id", request.youtube_url],
        timeout=120,
        error_message="Video ID alma işlemi timeout oldu",
    )
    if rc != 0:
        raise RuntimeError(stderr or "Video ID alınamadı")

    video_id = stdout.strip()
    project_id = build_owner_scoped_project_id("yt", subject, video_id)
    project = ProjectPaths(project_id)
    ensure_project_manifest(project_id, owner_subject=subject, source="youtube")

    if not project.master_video.exists() or not project.transcript.exists():
        return {
            "project_id": project_id,
            "project_cached": False,
            "analysis_cached": False,
            "render_cached": False,
            "cache_scope": "none",
            "clip_count": 0,
        }

    identity = build_pipeline_cache_identity(
        project=project,
        ai_engine=request.ai_engine,
        num_clips=request.num_clips,
        duration_min=duration_min,
        duration_max=duration_max,
        style_name=request.style_name,
        animation_type=request.animation_type,
        layout=request.layout,
        skip_subtitles=request.skip_subtitles,
        video_model_identifier=resolve_video_model_identifier(YOLO_MODEL_PATH),
    )
    viral_results = load_cached_pipeline_analysis(project, analysis_key=identity.analysis_key)
    if viral_results is None:
        return {
            "project_id": project_id,
            "project_cached": True,
            "analysis_cached": False,
            "render_cached": False,
            "cache_scope": "none",
            "clip_count": 0,
        }

    segments = extract_pipeline_segments(viral_results, clip_limit=request.num_clips)
    if segments is None:
        return {
            "project_id": project_id,
            "project_cached": True,
            "analysis_cached": False,
            "render_cached": False,
            "cache_scope": "none",
            "clip_count": 0,
        }
    render_hit = load_pipeline_render_cache_hit(
        project,
        render_key=identity.render_key,
        segments_signature=build_segments_signature(segments),
    )
    if render_hit is None:
        return {
            "project_id": project_id,
            "project_cached": True,
            "analysis_cached": True,
            "render_cached": False,
            "cache_scope": "analysis",
            "clip_count": 0,
        }

    return {
        "project_id": project_id,
        "project_cached": True,
        "analysis_cached": True,
        "render_cached": True,
        "cache_scope": "full_render",
        "clip_count": render_hit.clip_count,
    }


@router.post("/cache-status")
@logger.catch(reraise=True)
async def get_pipeline_cache_status(
    request: JobRequest,
    auth: AuthContext = Depends(require_policy("start_job")),
) -> dict[str, Any]:
    cache_status = await _inspect_pipeline_cache_state(auth.subject, request)
    return {
        **cache_status,
        "message": _build_cache_status_message(cache_status),
    }


@router.post("/start-job")
@logger.catch(reraise=True)
async def start_processing_job(
    request: JobRequest,
    auth: AuthContext = Depends(require_policy("start_job")),
) -> dict[str, Any]:
    """UI'dan 'VİDEOYU ÜRET' butonuna basıldığında tetiklenir."""
    cache_status: dict[str, Any]
    try:
        cache_status = await _inspect_pipeline_cache_state(auth.subject, request)
        if request.force_reanalyze:
            cache_status["cache_scope"] = "none"
        elif request.force_rerender and bool(cache_status.get("analysis_cached")):
            cache_status["cache_scope"] = "analysis"
    except Exception as exc:
        logger.warning("Pipeline cache preflight başarısız, queue akışına düşülüyor: {}", exc)
        cache_status = {
            "project_id": None,
            "project_cached": False,
            "analysis_cached": False,
            "render_cached": False,
            "cache_scope": "none",
        }

    if bool(cache_status.get("render_cached")) and not request.force_reanalyze and not request.force_rerender:
        return {
            "status": "cached",
            "job_id": None,
            "project_id": cache_status.get("project_id"),
            "cache_hit": True,
            "cache_scope": cache_status.get("cache_scope", "full_render"),
            "message": _build_start_job_cached_message(cache_status),
            "gpu_locked": manager.gpu_lock.locked(),
        }

    manager.assert_subject_can_enqueue(auth.subject)
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"🚀 Yeni görev: {job_id} | {request.youtube_url}")

    cancel_event = threading.Event()
    job_info: dict[str, Any] = {
        "job_id":       job_id,
        "url":          request.youtube_url,
        "style":        request.style_name,
        "animation_type": request.animation_type,
        "status":       "queued",
        "progress":     0,
        "last_message": "Sıraya alındı...",
        "created_at":   time.time(),
        "project_id":   cache_status.get("project_id"),
        "subject":      auth.subject,
        "cancel_event": cancel_event,
    }
    task = asyncio.create_task(run_gpu_job(job_id, request))
    job_info["task_handle"] = task
    manager.jobs[job_id] = job_info
    manager.seed_job_timeline(
        job_id,
        message="İşlem kuyruğa alındı. GPU müsait olduğunda başlayacak.",
        progress=0,
        status="queued",
        source="api",
    )

    return {
        "status":     "queued",
        "job_id":     job_id,
        "project_id": cache_status.get("project_id"),
        "cache_hit":  False,
        "cache_scope": cache_status.get("cache_scope", "none"),
        "message":    "İşlem kuyruğa alındı. GPU müsait olduğunda başlayacak.",
        "gpu_locked": manager.gpu_lock.locked(),
    }


@router.get("/jobs")
async def list_jobs(
    auth: AuthContext = Depends(require_policy("view_jobs")),
) -> dict:
    """Tüm aktif ve bekleyen işleri listeler."""
    runtime_only_keys = {"task", "task_handle", "cancel_event"}
    return {
        "jobs": [
            {k: v for k, v in job.items() if k not in runtime_only_keys}
            for job in manager.jobs.values()
            if str(job.get("subject") or "") == auth.subject
        ]
    }


@router.post("/cancel-job/{job_id}")
async def cancel_job(
    job_id: str,
    auth: AuthContext = Depends(require_policy("cancel_job")),
) -> dict:
    """Belirli bir işi iptal eder."""
    if job_id not in manager.jobs:
        raise NotFoundError("İş bulunamadı.")

    job = manager.jobs[job_id]
    if str(job.get("subject") or "") != auth.subject:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")
    if job["status"] in ("completed", "error", "cancelled"):
        return {"status": "ignored", "message": f"İş zaten {job['status']} durumunda."}

    cancel_event = job.get("cancel_event")
    if cancel_event is not None:
        cancel_event.set()

    task = job.get("task_handle")
    if task:
        task.cancel()
        return {"status": "success", "message": "İş iptal sinyali gönderildi."}

    _finalize_job(job_id, "cancelled")
    return {"status": "success", "message": "İş iptal edildi."}
