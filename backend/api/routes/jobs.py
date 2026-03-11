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

from fastapi import APIRouter, Depends
from loguru import logger

from backend.models.schemas import JobRequest
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.security import AuthContext, require_policy
from backend.core.orchestrator import GodTierShortsCreator
from backend.core.exceptions import JobExecutionError, NotFoundError
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
            orchestrator = GodTierShortsCreator(ui_callback=callback, cancel_event=cancel_event)
            orchestrator.analyzer.engine = request.ai_engine

            duration_min = 120.0
            duration_max = 180.0
            if not request.auto_mode and request.duration_min is not None and request.duration_max is not None:
                duration_min = float(request.duration_min)
                duration_max = float(request.duration_max)

            try:
                await orchestrator.run_pipeline_async(
                    request.youtube_url,
                    request.style_name,
                    request.layout,
                    request.skip_subtitles,
                    request.num_clips,
                    duration_min,
                    duration_max,
                    request.resolution,
                )
                _finalize_job(job_id, "completed", progress=100)
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
async def get_available_styles() -> dict:
    """Arayüzdeki Dropdown için mevcut stilleri döner."""
    return {"styles": StyleManager.list_presets() + ["CUSTOM"]}


@router.post("/start-job")
@logger.catch
async def start_processing_job(
    request: JobRequest,
    _: AuthContext = Depends(require_policy("start_job")),
) -> dict[str, Any]:
    """UI'dan 'VİDEOYU ÜRET' butonuna basıldığında tetiklenir."""
    job_id = str(uuid.uuid4())[:8]
    logger.info(f"🚀 Yeni görev: {job_id} | {request.youtube_url}")

    cancel_event = threading.Event()
    job_info: dict[str, Any] = {
        "job_id":       job_id,
        "url":          request.youtube_url,
        "style":        request.style_name,
        "status":       "queued",
        "progress":     0,
        "last_message": "Sıraya alındı...",
        "created_at":   time.time(),
        "cancel_event": cancel_event,
    }
    task = asyncio.create_task(run_gpu_job(job_id, request))
    job_info["task_handle"] = task
    manager.jobs[job_id] = job_info

    return {
        "status":     "queued",
        "job_id":     job_id,
        "message":    "İşlem kuyruğa alındı. GPU müsait olduğunda başlayacak.",
        "gpu_locked": manager.gpu_lock.locked(),
    }


@router.get("/jobs")
async def list_jobs() -> dict:
    """Tüm aktif ve bekleyen işleri listeler."""
    return {
        "jobs": [
            {k: v for k, v in job.items() if k not in {"task_handle", "cancel_event"}}
            for job in manager.jobs.values()
        ]
    }


@router.post("/cancel-job/{job_id}")
async def cancel_job(
    job_id: str,
    _: AuthContext = Depends(require_policy("cancel_job")),
) -> dict:
    """Belirli bir işi iptal eder."""
    if job_id not in manager.jobs:
        raise NotFoundError("İş bulunamadı.")

    job = manager.jobs[job_id]
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
