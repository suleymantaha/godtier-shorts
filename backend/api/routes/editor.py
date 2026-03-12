"""
backend/api/routes/editor.py
==============================
Manuel klip ve altyazı düzenleme endpoint'leri:
  GET  /api/transcript
  POST /api/transcript
  POST /api/process-manual
  POST /api/reburn
"""
import asyncio
import json
import os
import time
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from loguru import logger
from pydantic import ValidationError

from backend.config import (
    VIDEO_METADATA, OUTPUTS_DIR, ProjectPaths, PROJECTS_DIR,
    get_project_path, sanitize_project_name,
)
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.security import AuthContext, require_policy
from backend.api.routes.clips import (
    build_secure_clip_url,
    ensure_project_transcript,
    finalize_job_error,
    finalize_job_success,
    prepare_uploaded_project,
)
from backend.core.orchestrator import GodTierShortsCreator
from backend.core.exceptions import InvalidInputError, JobExecutionError
from backend.models.schemas import (
    BatchJobRequest,
    ManualAutoCutRequest,
    ManualJobRequest,
    ReburnRequest,
    TranscriptSegment,
)

router = APIRouter(prefix="/api", tags=["editor"])
DEFAULT_MANUAL_CUT_STYLE = "HORMOZI"
DEFAULT_MANUAL_CUT_LAYOUT = "single"


@router.post("/process-batch")
async def process_batch_clips(
    request: BatchJobRequest,
    _: AuthContext = Depends(require_policy("process_batch")),
) -> dict:
    """Seçilen aralıkta AI ile toplu klip üretir."""
    if request.project_id:
        try:
            sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e

    job_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.project_id or "",
        "style": request.style_name,
        "status": "queued",
        "progress": 0,
        "last_message": "Toplu üretim kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.gpu_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Toplu üretim başladı..."
            thread_safe_broadcast({"message": "Toplu üretim başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: thread_safe_broadcast(s, job_id)
            orchestrator = GodTierShortsCreator(ui_callback=cb)
            try:
                path = get_project_path(request.project_id, "transcript.json") if request.project_id else VIDEO_METADATA
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        transcript_data = json.load(f)
                else:
                    transcript_data = []

                await asyncio.to_thread(
                    orchestrator.run_batch_manual_clips,
                    request.start_time,
                    request.end_time,
                    request.num_clips,
                    transcript_data,
                    request.style_name,
                    request.project_id,
                    request.layout,
                )
                finalize_job_success(job_id, "Toplu klip üretimi tamamlandı.")
            except (RuntimeError, ValueError, OSError) as exc:
                mapped_error = JobExecutionError("Toplu üretim başarısız", details=str(exc))
                logger.error(f"Toplu üretim hatası ({job_id}): {mapped_error.message}")
                finalize_job_error(job_id, mapped_error)
            finally:
                await asyncio.to_thread(orchestrator.cleanup_gpu)

    asyncio.create_task(_run())
    return {"status": "started", "job_id": job_id}


def _parse_cut_points(raw: str | None) -> list[float] | None:
    """Parse cut_points JSON string. Returns sorted list or None."""
    if not raw or not raw.strip():
        return None
    try:
        pts = json.loads(raw)
        if not isinstance(pts, list) or len(pts) < 2:
            return None
        nums = [float(x) for x in pts if isinstance(x, (int, float))]
        if len(nums) < 2:
            return None
        return sorted(set(nums))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


@router.post("/manual-cut-upload")
async def manual_cut_upload(
    file: UploadFile = File(...),
    start_time: float = Form(...),
    end_time: float = Form(...),
    style_name: str = Form("HORMOZI"),
    skip_subtitles: bool = Form(False),
    num_clips: int = Form(1),
    cut_points: str | None = Form(None),
    cut_as_short: bool = Form(True),
    _: AuthContext = Depends(require_policy("manual_cut_upload")),
) -> dict:
    """Video + zaman aralığı ile otomatik manual cut üretir. cut_points veya num_clips>1 ile çoklu klip."""
    try:
        request = ManualAutoCutRequest(start_time=start_time, end_time=end_time)
    except ValidationError as exc:
        raise InvalidInputError("İstek doğrulaması başarısız", details=json.loads(exc.json())) from exc

    pts = _parse_cut_points(cut_points)
    use_cut_points = pts is not None and len(pts) >= 2
    num_clips = max(1, min(20, num_clips))
    is_batch = not use_cut_points and num_clips > 1

    project, project_id, _is_cached = prepare_uploaded_project(file)
    job_id = f"manualcut_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    clip_name = f"manual_{job_id}.mp4" if not is_batch else None
    output_url = build_secure_clip_url(project_id, clip_name) if clip_name else None

    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": str(project.master_video),
        "style": style_name,
        "status": "queued",
        "progress": 0,
        "last_message": "Video alındı, otomatik kesim kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": project_id,
        "clip_name": clip_name,
        "output_url": output_url,
        "num_clips": num_clips,
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.gpu_lock:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Video hazırlanıyor..."
                thread_safe_broadcast({"message": "Video hazırlanıyor...", "progress": 1, "status": "processing"}, job_id)

                await asyncio.to_thread(
                    ensure_project_transcript,
                    project,
                    lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
                )

                with open(project.transcript, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)

                cb = lambda s: thread_safe_broadcast(s, job_id)
                orchestrator = GodTierShortsCreator(ui_callback=cb)
                try:
                    if use_cut_points:
                        assert pts is not None  # use_cut_points implies pts is not None
                        output_paths = await orchestrator.run_manual_clips_from_cut_points_async(
                            cut_points=pts,
                            transcript_data=transcript_data,
                            style_name=style_name,
                            project_id=project_id,
                            layout=DEFAULT_MANUAL_CUT_LAYOUT,
                            skip_subtitles=skip_subtitles,
                            cut_as_short=cut_as_short,
                        )
                        if not output_paths:
                            manager.jobs[job_id]["status"] = "empty"
                            manager.jobs[job_id]["progress"] = 100
                            manager.jobs[job_id]["last_message"] = "Kesim tamamlandı ancak çıktı üretilemedi."
                            manager.jobs[job_id]["output_paths"] = []
                            manager.jobs[job_id]["output_path"] = None
                            thread_safe_broadcast({"message": "Kesim tamamlandı ancak çıktı üretilemedi.", "progress": 100}, job_id)
                            return

                        first_name = os.path.basename(output_paths[0])
                        manager.jobs[job_id]["clip_name"] = first_name
                        manager.jobs[job_id]["output_url"] = build_secure_clip_url(project_id, first_name)
                        manager.jobs[job_id]["output_paths"] = output_paths
                        manager.jobs[job_id]["output_path"] = output_paths[0]
                        manager.jobs[job_id]["num_clips"] = len(output_paths)
                    elif is_batch:
                        output_paths = await orchestrator.run_batch_manual_clips_async(
                            start_t=request.start_time,
                            end_t=request.end_time,
                            num_clips=num_clips,
                            transcript_data=transcript_data,
                            style_name=style_name,
                            project_id=project_id,
                            layout=DEFAULT_MANUAL_CUT_LAYOUT,
                            skip_subtitles=skip_subtitles,
                            cut_as_short=cut_as_short,
                        )
                        if not output_paths:
                            manager.jobs[job_id]["status"] = "empty"
                            manager.jobs[job_id]["progress"] = 100
                            manager.jobs[job_id]["last_message"] = "Toplu kesim tamamlandı ancak çıktı üretilemedi."
                            manager.jobs[job_id]["output_paths"] = []
                            manager.jobs[job_id]["output_path"] = None
                            thread_safe_broadcast({"message": "Toplu kesim tamamlandı ancak çıktı üretilemedi.", "progress": 100}, job_id)
                            return

                        first_name = os.path.basename(output_paths[0])
                        manager.jobs[job_id]["clip_name"] = first_name
                        manager.jobs[job_id]["output_url"] = build_secure_clip_url(project_id, first_name)
                        manager.jobs[job_id]["output_paths"] = output_paths
                        manager.jobs[job_id]["output_path"] = output_paths[0]
                        manager.jobs[job_id]["num_clips"] = len(output_paths)
                    else:
                        output_path = await orchestrator.run_manual_clip_async(
                            start_t=request.start_time,
                            end_t=request.end_time,
                            transcript_data=None,
                            style_name=style_name,
                            project_id=project_id,
                            center_x=None,
                            layout=DEFAULT_MANUAL_CUT_LAYOUT,
                            output_name=clip_name,
                            skip_subtitles=skip_subtitles,
                            cut_as_short=cut_as_short,
                        )
                        manager.jobs[job_id]["output_path"] = output_path
                        if output_path:
                            final_name = os.path.basename(output_path)
                            manager.jobs[job_id]["clip_name"] = final_name
                            manager.jobs[job_id]["output_url"] = build_secure_clip_url(project_id, final_name)
                            manager.jobs[job_id]["output_paths"] = [output_path]
                            manager.jobs[job_id]["num_clips"] = 1

                    finalize_job_success(job_id, "Otomatik manual cut işlemi tamamlandı.")
                except (RuntimeError, ValueError, OSError) as exc:
                    mapped_error = JobExecutionError("Otomatik manual cut başarısız", details=str(exc))
                    logger.error(f"Otomatik manual cut hatası ({job_id}): {mapped_error.message}")
                    finalize_job_error(job_id, mapped_error)
                finally:
                    await asyncio.to_thread(orchestrator.cleanup_gpu)
        except (RuntimeError, ValueError, OSError) as exc:
            mapped_error = JobExecutionError("Otomatik manual cut başarısız", details=str(exc))
            logger.error(f"Otomatik manual cut hatası ({job_id}): {mapped_error.message}")
            finalize_job_error(job_id, mapped_error)

    task = asyncio.create_task(_run())
    manager.jobs[job_id]["task"] = task
    return {
        "status": "started",
        "job_id": job_id,
        "project_id": project_id,
        "clip_name": clip_name,
        "output_url": output_url,
        "message": f"Otomatik manual cut başlatıldı ({num_clips} klip)." if is_batch else "Otomatik manual cut başlatıldı.",
    }


@router.get("/transcript")
async def get_transcript(
    project_id: str | None = None,
    _: AuthContext = Depends(require_policy("view_transcript")),
) -> dict:
    """Belirli bir projenin transkriptini arayüze gönderir."""
    if not project_id:
        return {"transcript": []}
    try:
        sanitize_project_name(project_id)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e

    path = get_project_path(project_id, "transcript.json")

    if not path.exists():
        return {"transcript": []}
    with open(path, "r", encoding="utf-8") as f:
        return {"transcript": json.load(f)}


@router.post("/transcript")
async def save_transcript(
    data: list[TranscriptSegment],
    project_id: str | None = None,
    _: AuthContext = Depends(require_policy("save_transcript")),
) -> dict:
    """Arayüzden gelen düzenlenmiş transkripti projeye veya varsayılana kaydeder."""
    if project_id:
        try:
            sanitize_project_name(project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e
        path = get_project_path(project_id, "transcript.json")
    else:
        path = VIDEO_METADATA

    with open(str(path), "w", encoding="utf-8") as f:
        json.dump([seg.model_dump() for seg in data], f, ensure_ascii=False, indent=4)
    return {"status": "success"}


@router.post("/process-manual")
async def process_manual_clip(
    request: ManualJobRequest,
    _: AuthContext = Depends(require_policy("process_manual")),
) -> dict:
    """Kullanıcının elle seçtiği aralığı işler."""
    if request.project_id:
        try:
            sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e

    job_id = f"manual_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.project_id or "",
        "style": request.style_name,
        "status": "queued",
        "progress": 0,
        "last_message": "Manuel render kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.gpu_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Manuel render başladı..."
            thread_safe_broadcast({"message": "Manuel render başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: thread_safe_broadcast(s, job_id)
            orchestrator = GodTierShortsCreator(ui_callback=cb)
            try:
                await orchestrator.run_manual_clip_async(
                    start_t=request.start_time,
                    end_t=request.end_time,
                    transcript_data=request.transcript,
                    style_name=request.style_name,
                    project_id=request.project_id,
                    center_x=request.center_x,
                    layout=request.layout,
                )
                finalize_job_success(job_id, "Manuel render tamamlandı.")
            except (RuntimeError, ValueError, OSError) as exc:
                mapped_error = JobExecutionError("Manuel render başarısız", details=str(exc))
                logger.error(f"Manuel render hatası ({job_id}): {mapped_error.message}")
                finalize_job_error(job_id, mapped_error)
            finally:
                await asyncio.to_thread(orchestrator.cleanup_gpu)

    task = asyncio.create_task(_run())
    manager.jobs[job_id]["task"] = task
    return {"status": "started", "job_id": job_id}


@router.post("/reburn")
async def reburn_clip(
    request: ReburnRequest,
    _: AuthContext = Depends(require_policy("reburn")),
) -> dict:
    """Klibin altyazılarını yeniden basar."""
    if request.project_id:
        try:
            sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e

    job_id = f"reburn_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.clip_name,
        "style": request.style_name,
        "status": "queued",
        "progress": 0,
        "last_message": "Altyazı yeniden basım kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.gpu_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Altyazı yeniden basım başladı..."
            thread_safe_broadcast({"message": "Altyazı yeniden basım başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: thread_safe_broadcast(s, job_id)
            orchestrator = GodTierShortsCreator(ui_callback=cb)
            try:
                await orchestrator.reburn_subtitles_async(
                    clip_name=request.clip_name,
                    transcript=request.transcript,
                    project_id=request.project_id,
                    style_name=request.style_name,
                )
                finalize_job_success(job_id, "Altyazı yeniden basımı tamamlandı.")
            except (RuntimeError, ValueError, OSError) as exc:
                mapped_error = JobExecutionError("Reburn işlemi başarısız", details=str(exc))
                logger.error(f"Reburn hatası ({job_id}): {mapped_error.message}")
                finalize_job_error(job_id, mapped_error)
            finally:
                await asyncio.to_thread(orchestrator.cleanup_gpu)

    task = asyncio.create_task(_run())
    manager.jobs[job_id]["task"] = task
    return {"status": "started", "job_id": job_id}
