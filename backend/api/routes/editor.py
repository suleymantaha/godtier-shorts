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
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from loguru import logger
from pydantic import ValidationError

from backend.config import (
    TEMP_DIR, VIDEO_METADATA, ProjectPaths,
    get_project_path, sanitize_clip_name, sanitize_project_name,
)
from backend.api.clip_events import build_api_clip_event_port
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.security import AuthContext, ensure_project_access, require_policy
from backend.api.routes.clips import (
    ACTIVE_JOB_STATUSES,
    build_secure_clip_url,
    build_clip_transcript_response,
    ensure_project_transcript,
    finalize_job_error,
    finalize_job_review_required,
    finalize_job_success,
    find_clip_recovery_job,
    find_project_transcript_job,
    load_clip_payload,
    prepare_uploaded_project,
    resolve_project_transcript_state,
)
from backend.core.external_tools import ffmpeg as resolve_ffmpeg
from backend.core.workflow_common import run_blocking
from backend.core.media_ops import build_shifted_transcript_segments
from backend.core.cut_points import parse_cut_points
from backend.core.render_contracts import resolve_duration_range
from backend.core.orchestrator import GodTierShortsCreator
from backend.core.exceptions import AppError, InvalidInputError, JobExecutionError, RenderReviewRequiredError
from backend.models.schemas import (
    BatchJobRequest,
    ClipTranscriptRecoveryRequest,
    ManualAutoCutRequest,
    ManualJobRequest,
    ProjectTranscriptRecoveryRequest,
    ReburnRequest,
    TranscriptSegment,
)
from backend.services.subtitle_styles import StyleManager
from backend.services.transcription import run_transcription

router = APIRouter(prefix="/api", tags=["editor"])
DEFAULT_MANUAL_CUT_STYLE = "HORMOZI"
DEFAULT_MANUAL_CUT_LAYOUT = "auto"
CLIP_RECOVERY_JOB_PREFIX = "cliprecover"


def _check_job_cancelled(job_id: str) -> None:
    event = manager.jobs.get(job_id, {}).get("cancel_event")
    if event is not None and event.is_set():
        raise asyncio.CancelledError


def _broadcast_editor_job(payload: dict, job_id: str) -> None:
    if manager.jobs.get(job_id, {}).get("status") != "cancelled":
        thread_safe_broadcast(payload, job_id)


def _attach_editor_task(job_id: str, task: asyncio.Task) -> None:
    manager.jobs[job_id]["task"] = task
    manager.jobs[job_id]["task_handle"] = task

    def completed(done: asyncio.Task) -> None:
        job = manager.jobs.get(job_id)
        if job is None:
            return
        if done.cancelled():
            job["cancel_event"].set()
            job["status"] = "cancelled"
            job["last_message"] = "İş iptal edildi."
            thread_safe_broadcast({"status": "cancelled", "message": job["last_message"]}, job_id)
        elif (error := done.exception()) is not None:
            _finalize_background_job_error(job_id, "Düzenleme işlemi başarısız", error)

    task.add_done_callback(completed)


def _require_production_project(project_id: str | None) -> None:
    if os.getenv("APP_ENV", "development").strip().lower() == "production" and not project_id:
        raise InvalidInputError("Production düzenleme işlemleri için project_id zorunlu")


def _read_job_timeout_seconds(env_var: str, default: float) -> float:
    raw = os.getenv(env_var)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else 0.0


PROCESS_BATCH_TIMEOUT_SECONDS = _read_job_timeout_seconds("PROCESS_BATCH_TIMEOUT_SECONDS", 900.0)
MANUAL_CUT_UPLOAD_TIMEOUT_SECONDS = _read_job_timeout_seconds("MANUAL_CUT_UPLOAD_TIMEOUT_SECONDS", 900.0)
PROCESS_MANUAL_TIMEOUT_SECONDS = _read_job_timeout_seconds("PROCESS_MANUAL_TIMEOUT_SECONDS", 900.0)


async def _await_with_job_timeout(
    awaitable, *, timeout_seconds: float, timeout_message: str,
    cancel_event: threading.Event | None = None,
):
    task = asyncio.ensure_future(awaitable)
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout_seconds if timeout_seconds > 0 else None)
        if done:
            result = await task
            if cancel_event is not None and cancel_event.is_set():
                raise asyncio.CancelledError
            return result
        if cancel_event is not None:
            cancel_event.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise JobExecutionError(timeout_message, details=f"{timeout_seconds:.0f}s timeout")
    except asyncio.CancelledError:
        if cancel_event is not None:
            cancel_event.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise


def _map_background_job_error(default_message: str, exc: Exception) -> JobExecutionError:
    if isinstance(exc, JobExecutionError):
        return exc
    if isinstance(exc, AppError):
        return JobExecutionError(exc.message, details=exc.details)
    if isinstance(exc, ValidationError):
        return JobExecutionError(default_message, details=json.loads(exc.json()))
    return JobExecutionError(default_message, details=str(exc))


def _finalize_background_job_error(job_id: str, default_message: str, exc: Exception) -> None:
    if manager.jobs.get(job_id, {}).get("status") == "cancelled":
        return
    mapped_error = _map_background_job_error(default_message, exc)
    logger.exception("{} ({}): {}", default_message, job_id, mapped_error.message)
    finalize_job_error(job_id, mapped_error)


def _write_clip_metadata(metadata_path: Path, payload: dict, transcript_data: list[dict]) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "transcript": transcript_data,
                "viral_metadata": payload.get("viral_metadata"),
                "render_metadata": payload.get("render_metadata"),
            },
            f,
            ensure_ascii=False,
            indent=4,
        )


def _resolve_recovery_project_id(payload: dict, request_project_id: str | None, resolved_project_id: str | None) -> str | None:
    if resolved_project_id:
        return resolved_project_id

    render_metadata = payload.get("render_metadata")
    if isinstance(render_metadata, dict):
        candidate = render_metadata.get("project_id")
        if isinstance(candidate, str) and candidate and candidate != "legacy":
            return sanitize_project_name(candidate)

    if request_project_id and request_project_id != "legacy":
        return sanitize_project_name(request_project_id)
    return None


def _extract_render_range(payload: dict) -> tuple[float, float]:
    render_metadata = payload.get("render_metadata")
    if not isinstance(render_metadata, dict):
        raise InvalidInputError("Klip metadata içinde render aralığı bulunamadı.")

    start_time = render_metadata.get("start_time")
    end_time = render_metadata.get("end_time")
    if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)) or end_time <= start_time:
        raise InvalidInputError("Klip metadata içinde geçerli bir render aralığı bulunamadı.")

    return float(start_time), float(end_time)


def _extract_audio_from_video(video_path: Path, audio_path: Path) -> None:
    try:
        result = subprocess.run(
            [
                resolve_ffmpeg(),
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired as exc:
        raise JobExecutionError("Klip kaynağından ses çıkarma zaman aşımına uğradı") from exc
    if result.returncode != 0:
        raise JobExecutionError(
            "Klip kaynağından ses çıkarılamadı",
            details=(result.stderr or "")[-300:],
        )


def _recover_clip_transcript_from_project(
    clip_name: str,
    project_id: str | None,
    progress_callback,
) -> None:
    payload, _video_path, metadata_path, resolved_project_id = load_clip_payload(clip_name, project_id)
    recovery_project_id = _resolve_recovery_project_id(payload, project_id, resolved_project_id)
    if not recovery_project_id:
        raise InvalidInputError("Bu klip için proje transkriptinden kurtarma yapılamıyor.")

    project_transcript_path = ProjectPaths(recovery_project_id).transcript
    if not project_transcript_path.exists():
        raise FileNotFoundError(f"Proje transkripti bulunamadı: {project_transcript_path}")

    start_time, end_time = _extract_render_range(payload)
    progress_callback("Proje transkripti yükleniyor...", 20)
    with open(project_transcript_path, "r", encoding="utf-8") as f:
        project_transcript = json.load(f)

    progress_callback("Klip transkripti proje aralığından türetiliyor...", 60)
    transcript_data = build_shifted_transcript_segments(project_transcript, start_time, end_time)
    if not transcript_data:
        raise JobExecutionError("Proje transkriptinden klip aralığı çıkarılamadı")
    _write_clip_metadata(metadata_path, payload, transcript_data)
    progress_callback("Klip transkripti metadata dosyasına yazıldı.", 90)


def _recover_clip_transcript_from_source(
    clip_name: str,
    project_id: str | None,
    progress_callback,
    cancel_event: threading.Event | None = None,
) -> None:
    payload, video_path, metadata_path, _resolved_project_id = load_clip_payload(clip_name, project_id)
    raw_video_path = video_path.with_name(f"{video_path.stem}_raw.mp4")
    source_video = raw_video_path if raw_video_path.exists() else video_path
    if not source_video.exists():
        raise FileNotFoundError(f"Kurtarma için kaynak video bulunamadı: {source_video}")

    audio_fd, audio_temp = tempfile.mkstemp(suffix=".wav", dir=TEMP_DIR)
    os.close(audio_fd)
    transcript_fd, transcript_temp = tempfile.mkstemp(suffix=".json", dir=TEMP_DIR)
    os.close(transcript_fd)

    try:
        progress_callback("Kaynak klipten ses çıkarılıyor...", 10)
        _extract_audio_from_video(source_video, Path(audio_temp))
        progress_callback("Kaynak klip yeniden transkribe ediliyor...", 25)
        run_transcription(
            audio_file=audio_temp,
            output_json=transcript_temp,
            status_callback=progress_callback,
            cancel_event=cancel_event,
        )
        with open(transcript_temp, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Transcript recovery cancelled")
        _write_clip_metadata(metadata_path, payload, transcript_data)
        progress_callback("Yeni klip transkripti kaydedildi.", 90)
    finally:
        for temp_path in (audio_temp, transcript_temp):
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass


def _resolve_auto_recovery_strategy(response: dict) -> str | None:
    strategy = response.get("recommended_strategy")
    if strategy in {"project_slice", "transcribe_source"}:
        return strategy
    return None


def _resolve_effective_recovery_project_id(response: dict, request_project_id: str | None) -> str | None:
    capabilities = response.get("capabilities")
    if isinstance(capabilities, dict):
        resolved = capabilities.get("resolved_project_id")
        if isinstance(resolved, str) and resolved and resolved != "legacy":
            return resolved
    if request_project_id and request_project_id != "legacy":
        return request_project_id
    return None


async def _run_auto_clip_transcript_recovery(
    clip_name: str,
    project_id: str | None,
    response: dict,
    job_id: str,
) -> str:
    capabilities = response.get("capabilities") if isinstance(response.get("capabilities"), dict) else {}
    can_recover_from_project = bool(capabilities.get("can_recover_from_project"))
    can_transcribe_source = bool(capabilities.get("can_transcribe_source"))

    if can_recover_from_project:
        try:
            manager.jobs[job_id]["recovery_strategy"] = "project_slice"
            manager.jobs[job_id]["last_message"] = "Proje transkriptinden klip metadata kurtarılıyor..."
            _broadcast_editor_job(
                {"message": "Proje transkriptinden klip metadata kurtarılıyor...", "progress": 1, "status": "processing"},
                job_id,
            )
            await run_blocking(
                _recover_clip_transcript_from_project,
                clip_name,
                project_id,
                lambda msg, pct: _broadcast_editor_job({"message": msg, "progress": pct}, job_id),
            )
            return "project_slice"
        except (RuntimeError, ValueError, OSError, InvalidInputError, JobExecutionError) as exc:
            if not can_transcribe_source:
                raise
            logger.warning("Project slice recovery failed for {}: {}", clip_name, exc)
            _broadcast_editor_job(
                {
                    "message": "Proje dilimi bos veya gecersiz. Kaynak videodan transkripsiyona geciliyor...",
                    "progress": 45,
                    "status": "processing",
                },
                job_id,
            )

    if not can_transcribe_source:
        raise InvalidInputError("Bu klip için otomatik kurtarma kaynağı bulunamadı.")

    async with manager.gpu_lock:
        manager.jobs[job_id]["recovery_strategy"] = "transcribe_source"
        manager.jobs[job_id]["last_message"] = "Kaynak videodan transkript çıkarılıyor..."
        _broadcast_editor_job(
            {"message": "Kaynak videodan transkript çıkarılıyor...", "progress": 50, "status": "processing"},
            job_id,
        )
        await run_blocking(
            _recover_clip_transcript_from_source,
            clip_name,
            project_id,
            lambda msg, pct: _broadcast_editor_job({"message": msg, "progress": pct}, job_id),
            cancel_event=manager.jobs[job_id]["cancel_event"],
        )
    return "transcribe_source"


@router.post("/process-batch")
async def process_batch_clips(
    http_request: Request,
    request: BatchJobRequest,
    auth: AuthContext = Depends(require_policy("process_batch")),
) -> dict:
    """Seçilen aralıkta AI ile toplu klip üretir."""
    _require_production_project(request.project_id)
    if request.project_id:
        try:
            request.project_id = sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e
        ensure_project_access(http_request, auth, request.project_id)

    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.project_id or "",
        "style": request.style_name,
        "animation_type": request.animation_type,
        "status": "queued",
        "progress": 0,
        "last_message": "Toplu üretim kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
        "subject": auth.subject,
        "cancel_event": threading.Event(),
    }
    manager.seed_job_timeline(
        job_id,
        message="Toplu üretim kuyruğa alındı...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        _broadcast_editor_job({"message": "İşlem sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.processing_lock:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Toplu üretim başladı..."
                _broadcast_editor_job({"message": "Toplu üretim başladı...", "progress": 1, "status": "processing"}, job_id)
                cb = lambda s: _broadcast_editor_job(s, job_id)
                orchestrator = GodTierShortsCreator(
                    ui_callback=cb,
                    cancel_event=manager.jobs[job_id]["cancel_event"],
                    subject=auth.subject,
                    clip_event_port=build_api_clip_event_port(),
                    gpu_stage_lock=manager.gpu_lock,
                )
                try:
                    resolved_duration_min, resolved_duration_max = resolve_duration_range(
                        request.duration_min,
                        request.duration_max,
                    )
                    path = get_project_path(request.project_id, "transcript.json") if request.project_id else VIDEO_METADATA
                    if path.exists():
                        with open(path, "r", encoding="utf-8") as f:
                            transcript_data = json.load(f)
                    else:
                        transcript_data = []

                    output_paths = await _await_with_job_timeout(
                        orchestrator.run_batch_manual_clips_async(
                            start_t=request.start_time,
                            end_t=request.end_time,
                            num_clips=request.num_clips,
                            transcript_data=transcript_data,
                            job_id=job_id,
                            duration_min=resolved_duration_min,
                            duration_max=resolved_duration_max,
                            style_name=request.style_name,
                            animation_type=request.animation_type,
                            project_id=request.project_id,
                            layout=request.layout,
                            skip_subtitles=request.skip_subtitles,
                        ),
                        cancel_event=manager.jobs[job_id]["cancel_event"],
                        timeout_seconds=PROCESS_BATCH_TIMEOUT_SECONDS,
                        timeout_message="Toplu üretim zaman aşımına uğradı",
                    )
                    if output_paths:
                        first_name = os.path.basename(output_paths[0])
                        manager.jobs[job_id]["clip_name"] = first_name
                        manager.jobs[job_id]["output_url"] = build_secure_clip_url(request.project_id, first_name) if request.project_id else None
                        manager.jobs[job_id]["output_paths"] = output_paths
                        manager.jobs[job_id]["output_path"] = output_paths[0]
                        manager.jobs[job_id]["num_clips"] = len(output_paths)
                    _check_job_cancelled(job_id)
                    finalize_job_success(job_id, "Toplu klip üretimi tamamlandı.")
                except RenderReviewRequiredError as exc:
                    safe_outputs = list(exc.output_paths or [])
                    first_name = os.path.basename(safe_outputs[0]) if safe_outputs else None
                    finalize_job_review_required(
                        job_id,
                        exc.message,
                        review_items=exc.review_items,
                        output_paths=safe_outputs,
                        output_url=build_secure_clip_url(request.project_id, first_name) if request.project_id and first_name else None,
                        clip_name=first_name,
                        num_clips=exc.num_clips if exc.num_clips is not None else len(safe_outputs),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _finalize_background_job_error(job_id, "Toplu üretim başarısız", exc)
                finally:
                    await run_blocking(orchestrator.cleanup_gpu)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _finalize_background_job_error(job_id, "Toplu üretim başarısız", exc)

    task = asyncio.create_task(_run())
    _attach_editor_task(job_id, task)
    return {"status": "started", "job_id": job_id}


@router.post("/manual-cut-upload")
async def manual_cut_upload(
    http_request: Request,
    file: UploadFile = File(...),
    start_time: float = Form(...),
    end_time: float = Form(...),
    style_name: str = Form("HORMOZI"),
    animation_type: str = Form("default"),
    skip_subtitles: bool = Form(False),
    num_clips: int = Form(1),
    cut_points: str | None = Form(None),
    cut_as_short: bool = Form(True),
    layout: str = Form(DEFAULT_MANUAL_CUT_LAYOUT),
    duration_min: float | None = Form(None),
    duration_max: float | None = Form(None),
    auth: AuthContext = Depends(require_policy("manual_cut_upload")),
) -> dict:
    """Video + zaman aralığı ile otomatik manual cut üretir. cut_points veya num_clips>1 ile çoklu klip."""
    try:
        request = ManualAutoCutRequest(
            start_time=start_time,
            end_time=end_time,
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
        )
    except ValidationError as exc:
        raise InvalidInputError("İstek doğrulaması başarısız", details=json.loads(exc.json())) from exc
    try:
        style_name = StyleManager.ensure_valid_preset_name(style_name)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc
    try:
        animation_type = StyleManager.ensure_valid_animation_type(animation_type)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc
    try:
        layout = StyleManager.ensure_valid_requested_layout(layout)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc

    resolved_duration_min, resolved_duration_max = resolve_duration_range(duration_min, duration_max)

    pts = parse_cut_points(cut_points, start_time=request.start_time, end_time=request.end_time)
    use_cut_points = pts is not None and len(pts) >= 2
    num_clips = request.num_clips
    is_batch = not use_cut_points and num_clips > 1

    project, project_id, _is_cached = prepare_uploaded_project(file, owner_subject=auth.subject)
    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"manualcut_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    planned_clip_name = f"manual_{job_id}.mp4" if not is_batch else None

    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": str(project.master_video),
        "style": style_name,
        "animation_type": animation_type,
        "status": "queued",
        "progress": 0,
        "last_message": "Video alındı, otomatik kesim kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": project_id,
        "clip_name": None,
        "output_url": None,
        "num_clips": num_clips,
        "layout": layout,
        "subject": auth.subject,
        "cancel_event": threading.Event(),
    }
    manager.seed_job_timeline(
        job_id,
        message="Video alındı, otomatik kesim kuyruğa alındı...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        _broadcast_editor_job({"message": "İşlem sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.processing_lock:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Video hazırlanıyor..."
                _broadcast_editor_job({"message": "Video hazırlanıyor...", "progress": 1, "status": "processing"}, job_id)

                await run_blocking(
                    ensure_project_transcript,
                    project,
                    lambda msg, pct: _broadcast_editor_job({"message": msg, "progress": pct}, job_id),
                )

                with open(project.transcript, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)

                cb = lambda s: _broadcast_editor_job(s, job_id)
                orchestrator = GodTierShortsCreator(
                    ui_callback=cb,
                    cancel_event=manager.jobs[job_id]["cancel_event"],
                    subject=auth.subject,
                    clip_event_port=build_api_clip_event_port(),
                    gpu_stage_lock=manager.gpu_lock,
                )
                try:
                    if use_cut_points:
                        assert pts is not None  # use_cut_points implies pts is not None
                        output_paths = await _await_with_job_timeout(
                            orchestrator.run_manual_clips_from_cut_points_async(
                                cut_points=pts,
                                transcript_data=transcript_data,
                                job_id=job_id,
                                style_name=style_name,
                                animation_type=animation_type,
                                project_id=project_id,
                                layout=layout,
                                skip_subtitles=skip_subtitles,
                                cut_as_short=cut_as_short,
                            ),
                            cancel_event=manager.jobs[job_id]["cancel_event"],
                            timeout_seconds=MANUAL_CUT_UPLOAD_TIMEOUT_SECONDS,
                            timeout_message="Otomatik manual cut zaman aşımına uğradı",
                        )
                        if not output_paths:
                            manager.jobs[job_id]["status"] = "empty"
                            manager.jobs[job_id]["progress"] = 100
                            manager.jobs[job_id]["last_message"] = "Kesim tamamlandı ancak çıktı üretilemedi."
                            manager.jobs[job_id]["output_paths"] = []
                            manager.jobs[job_id]["output_path"] = None
                            _broadcast_editor_job({"message": "Kesim tamamlandı ancak çıktı üretilemedi.", "progress": 100}, job_id)
                            return

                        first_name = os.path.basename(output_paths[0])
                        manager.jobs[job_id]["clip_name"] = first_name
                        manager.jobs[job_id]["output_url"] = build_secure_clip_url(project_id, first_name)
                        manager.jobs[job_id]["output_paths"] = output_paths
                        manager.jobs[job_id]["output_path"] = output_paths[0]
                        manager.jobs[job_id]["num_clips"] = len(output_paths)
                    elif is_batch:
                        output_paths = await _await_with_job_timeout(
                            orchestrator.run_batch_manual_clips_async(
                                start_t=request.start_time,
                                end_t=request.end_time,
                                num_clips=num_clips,
                                transcript_data=transcript_data,
                                job_id=job_id,
                                duration_min=resolved_duration_min,
                                duration_max=resolved_duration_max,
                                style_name=style_name,
                                animation_type=animation_type,
                                project_id=project_id,
                                layout=layout,
                                skip_subtitles=skip_subtitles,
                                cut_as_short=cut_as_short,
                            ),
                            cancel_event=manager.jobs[job_id]["cancel_event"],
                            timeout_seconds=MANUAL_CUT_UPLOAD_TIMEOUT_SECONDS,
                            timeout_message="Otomatik manual cut zaman aşımına uğradı",
                        )
                        if not output_paths:
                            manager.jobs[job_id]["status"] = "empty"
                            manager.jobs[job_id]["progress"] = 100
                            manager.jobs[job_id]["last_message"] = "Toplu kesim tamamlandı ancak çıktı üretilemedi."
                            manager.jobs[job_id]["output_paths"] = []
                            manager.jobs[job_id]["output_path"] = None
                            _broadcast_editor_job({"message": "Toplu kesim tamamlandı ancak çıktı üretilemedi.", "progress": 100}, job_id)
                            return

                        first_name = os.path.basename(output_paths[0])
                        manager.jobs[job_id]["clip_name"] = first_name
                        manager.jobs[job_id]["output_url"] = build_secure_clip_url(project_id, first_name)
                        manager.jobs[job_id]["output_paths"] = output_paths
                        manager.jobs[job_id]["output_path"] = output_paths[0]
                        manager.jobs[job_id]["num_clips"] = len(output_paths)
                    else:
                        output_path = await _await_with_job_timeout(
                            orchestrator.run_manual_clip_async(
                                start_t=request.start_time,
                                end_t=request.end_time,
                                transcript_data=transcript_data,
                                job_id=job_id,
                                style_name=style_name,
                                animation_type=animation_type,
                                project_id=project_id,
                                center_x=None,
                                layout=layout,
                                output_name=planned_clip_name,
                                skip_subtitles=skip_subtitles,
                                cut_as_short=cut_as_short,
                            ),
                            cancel_event=manager.jobs[job_id]["cancel_event"],
                            timeout_seconds=MANUAL_CUT_UPLOAD_TIMEOUT_SECONDS,
                            timeout_message="Otomatik manual cut zaman aşımına uğradı",
                        )
                        manager.jobs[job_id]["output_path"] = output_path
                        if output_path:
                            final_name = os.path.basename(output_path)
                            manager.jobs[job_id]["clip_name"] = final_name
                            manager.jobs[job_id]["output_url"] = build_secure_clip_url(project_id, final_name)
                            manager.jobs[job_id]["output_paths"] = [output_path]
                            manager.jobs[job_id]["num_clips"] = 1

                    _check_job_cancelled(job_id)

                    finalize_job_success(job_id, "Otomatik manual cut işlemi tamamlandı.")
                except RenderReviewRequiredError as exc:
                    safe_outputs = list(exc.output_paths or [])
                    first_name = os.path.basename(safe_outputs[0]) if safe_outputs else None
                    finalize_job_review_required(
                        job_id,
                        exc.message,
                        review_items=exc.review_items,
                        output_paths=safe_outputs,
                        output_url=build_secure_clip_url(project_id, first_name) if first_name else None,
                        clip_name=first_name,
                        num_clips=exc.num_clips if exc.num_clips is not None else len(safe_outputs),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _finalize_background_job_error(job_id, "Otomatik manual cut başarısız", exc)
                finally:
                    await run_blocking(orchestrator.cleanup_gpu)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _finalize_background_job_error(job_id, "Otomatik manual cut başarısız", exc)

    task = asyncio.create_task(_run())
    _attach_editor_task(job_id, task)
    return {
        "status": "started",
        "job_id": job_id,
        "project_id": project_id,
        "clip_name": None,
        "output_url": None,
        "message": f"Otomatik manual cut başlatıldı ({num_clips} klip)." if is_batch else "Otomatik manual cut başlatıldı.",
    }


@router.get("/transcript")
async def get_transcript(
    request: Request,
    project_id: str | None = None,
    auth: AuthContext = Depends(require_policy("view_transcript")),
) -> dict:
    """Belirli bir projenin transkriptini arayüze gönderir."""
    if not project_id:
        return {
            "transcript": [],
            "transcript_status": "ready",
            "active_job_id": None,
            "last_error": None,
        }
    try:
        project_id = sanitize_project_name(project_id)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e
    ensure_project_access(request, auth, project_id)

    path = get_project_path(project_id, "transcript.json")
    state = resolve_project_transcript_state(project_id)

    if not path.exists():
        return {"transcript": [], **state}
    with open(path, "r", encoding="utf-8") as f:
        return {"transcript": json.load(f), **state}


@router.post("/transcript")
async def save_transcript(
    request: Request,
    data: list[TranscriptSegment],
    project_id: str | None = None,
    auth: AuthContext = Depends(require_policy("save_transcript")),
) -> dict:
    """Arayüzden gelen düzenlenmiş transkripti projeye veya varsayılana kaydeder."""
    _require_production_project(project_id)
    if project_id:
        try:
            project_id = sanitize_project_name(project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e
        ensure_project_access(request, auth, project_id)
        path = get_project_path(project_id, "transcript.json")
    else:
        path = VIDEO_METADATA

    with open(str(path), "w", encoding="utf-8") as f:
        json.dump([seg.model_dump() for seg in data], f, ensure_ascii=False, indent=4)
    return {"status": "success"}


@router.post("/transcript/recover")
async def recover_project_transcript(
    http_request: Request,
    request: ProjectTranscriptRecoveryRequest,
    auth: AuthContext = Depends(require_policy("recover_project_transcript")),
) -> dict:
    try:
        request.project_id = sanitize_project_name(request.project_id)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e
    ensure_project_access(http_request, auth, request.project_id)

    existing_job = find_project_transcript_job(request.project_id, ACTIVE_JOB_STATUSES)
    if existing_job:
        return {"status": "started", "job_id": existing_job["job_id"]}

    project = ProjectPaths(request.project_id)
    if not project.master_video.exists():
        raise InvalidInputError("Proje master videosu bulunamadı.")

    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"projecttranscript_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": str(project.master_video),
        "style": "PROJECT_TRANSCRIPT",
        "status": "queued",
        "progress": 0,
        "last_message": "Proje transkript kurtarma kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
        "subject": auth.subject,
        "cancel_event": threading.Event(),
    }
    manager.seed_job_timeline(
        job_id,
        message="Proje transkript kurtarma kuyruğa alındı...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        _broadcast_editor_job({"message": "İşlem sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.processing_lock:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Proje transkripti yeniden çıkarılıyor..."
                _broadcast_editor_job(
                    {"message": "Proje transkripti yeniden çıkarılıyor...", "progress": 1, "status": "processing"},
                    job_id,
                )
                await run_blocking(
                    ensure_project_transcript,
                    project,
                    lambda msg, pct: _broadcast_editor_job({"message": msg, "progress": pct}, job_id),
                )
            _check_job_cancelled(job_id)
            finalize_job_success(job_id, "Proje transkripti hazır.")
        except (RuntimeError, ValueError, OSError) as exc:
            mapped_error = JobExecutionError("Proje transkripti üretilemedi", details=str(exc))
            logger.error(f"Proje transkript kurtarma hatası ({job_id}): {mapped_error.message}")
            finalize_job_error(job_id, mapped_error)

    task = asyncio.create_task(_run())
    _attach_editor_task(job_id, task)
    return {"status": "started", "job_id": job_id}


@router.post("/clip-transcript/recover")
async def recover_clip_transcript(
    http_request: Request,
    request: ClipTranscriptRecoveryRequest,
    auth: AuthContext = Depends(require_policy("recover_clip_transcript")),
) -> dict:
    """Recover a clip transcript from project timing metadata or source transcription."""
    if request.project_id:
        try:
            request.project_id = sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e
        ensure_project_access(http_request, auth, request.project_id, clip_name=request.clip_name)

    response = build_clip_transcript_response(request.clip_name, request.project_id)
    effective_project_id = _resolve_effective_recovery_project_id(response, request.project_id)
    existing_job = find_clip_recovery_job(request.clip_name, effective_project_id, ACTIVE_JOB_STATUSES)
    if existing_job:
        return {"status": "started", "job_id": existing_job["job_id"]}

    if request.strategy == "auto":
        if response.get("transcript_status") == "ready":
            return {"status": "ready", "job_id": response.get("active_job_id")}
        if response.get("transcript_status") == "project_pending":
            return {"status": "project_pending", "job_id": response.get("active_job_id")}

    selected_strategy = request.strategy if request.strategy != "auto" else _resolve_auto_recovery_strategy(response)
    if selected_strategy is None:
        raise InvalidInputError("Bu klip için kullanılabilir transcript kurtarma stratejisi bulunamadı.")

    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"{CLIP_RECOVERY_JOB_PREFIX}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.clip_name,
        "style": "TRANSCRIPT_RECOVERY",
        "status": "queued",
        "progress": 0,
        "last_message": "Klip transkripti kurtarma kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": effective_project_id,
        "clip_name": request.clip_name,
        "recovery_strategy": selected_strategy,
        "subject": auth.subject,
        "cancel_event": threading.Event(),
    }
    manager.seed_job_timeline(
        job_id,
        message="Klip transkripti kurtarma kuyruğa alındı...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        _broadcast_editor_job({"message": "Kurtarma sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.processing_lock:
                if request.strategy == "auto":
                    manager.jobs[job_id]["status"] = "processing"
                    manager.jobs[job_id]["last_message"] = "Akilli transcript kurtarma başlatıldı..."
                    await _run_auto_clip_transcript_recovery(
                        request.clip_name,
                        effective_project_id,
                        response,
                        job_id,
                    )
                elif request.strategy == "transcribe_source":
                    async with manager.gpu_lock:
                        manager.jobs[job_id]["status"] = "processing"
                        manager.jobs[job_id]["last_message"] = "Kaynak videodan transkript çıkarılıyor..."
                        _broadcast_editor_job({"message": "Kaynak videodan transkript çıkarılıyor...", "progress": 1, "status": "processing"}, job_id)
                        await run_blocking(
                            _recover_clip_transcript_from_source,
                            request.clip_name,
                            effective_project_id,
                            lambda msg, pct: _broadcast_editor_job({"message": msg, "progress": pct}, job_id),
                            cancel_event=manager.jobs[job_id]["cancel_event"],
                        )
                else:
                    manager.jobs[job_id]["status"] = "processing"
                    manager.jobs[job_id]["last_message"] = "Proje transkriptinden klip metadata kurtarılıyor..."
                    _broadcast_editor_job({"message": "Proje transkriptinden klip metadata kurtarılıyor...", "progress": 1, "status": "processing"}, job_id)
                    await run_blocking(
                        _recover_clip_transcript_from_project,
                        request.clip_name,
                        effective_project_id,
                        lambda msg, pct: _broadcast_editor_job({"message": msg, "progress": pct}, job_id),
                    )

            _check_job_cancelled(job_id)

            finalize_job_success(job_id, "Klip transkripti kurtarma tamamlandı.")
        except (RuntimeError, ValueError, OSError, InvalidInputError, JobExecutionError) as exc:
            mapped_error = JobExecutionError("Klip transkripti kurtarma başarısız", details=str(exc))
            logger.error(f"Klip transkript kurtarma hatası ({job_id}): {mapped_error.message}")
            finalize_job_error(job_id, mapped_error)

    task = asyncio.create_task(_run())
    _attach_editor_task(job_id, task)
    return {"status": "started", "job_id": job_id}


@router.post("/process-manual")
async def process_manual_clip(
    http_request: Request,
    request: ManualJobRequest,
    auth: AuthContext = Depends(require_policy("process_manual")),
) -> dict:
    """Kullanıcının elle seçtiği aralığı işler."""
    _require_production_project(request.project_id)
    if request.project_id:
        try:
            request.project_id = sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e
        ensure_project_access(http_request, auth, request.project_id)

    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"manual_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.project_id or "",
        "style": request.style_name,
        "animation_type": request.animation_type,
        "status": "queued",
        "progress": 0,
        "last_message": "Manuel render kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
        "subject": auth.subject,
        "cancel_event": threading.Event(),
    }
    manager.seed_job_timeline(
        job_id,
        message="Manuel render kuyruğa alındı...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        _broadcast_editor_job({"message": "İşlem sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.processing_lock:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Manuel render başladı..."
                _broadcast_editor_job({"message": "Manuel render başladı...", "progress": 1, "status": "processing"}, job_id)
                cb = lambda s: _broadcast_editor_job(s, job_id)
                orchestrator = GodTierShortsCreator(
                    ui_callback=cb,
                    cancel_event=manager.jobs[job_id]["cancel_event"],
                    subject=auth.subject,
                    clip_event_port=build_api_clip_event_port(),
                    gpu_stage_lock=manager.gpu_lock,
                )
                try:
                    output_path = await _await_with_job_timeout(
                        orchestrator.run_manual_clip_async(
                            start_t=request.start_time,
                            end_t=request.end_time,
                            transcript_data=request.transcript,
                            style_name=request.style_name,
                            animation_type=request.animation_type,
                            project_id=request.project_id,
                            center_x=request.center_x,
                            layout=request.layout,
                        ),
                        cancel_event=manager.jobs[job_id]["cancel_event"],
                        timeout_seconds=PROCESS_MANUAL_TIMEOUT_SECONDS,
                        timeout_message="Manuel render zaman aşımına uğradı",
                    )
                    if output_path:
                        final_name = os.path.basename(output_path)
                        manager.jobs[job_id]["clip_name"] = final_name
                        manager.jobs[job_id]["output_url"] = build_secure_clip_url(request.project_id, final_name) if request.project_id else None
                        manager.jobs[job_id]["output_path"] = output_path
                        manager.jobs[job_id]["output_paths"] = [output_path]
                        manager.jobs[job_id]["num_clips"] = 1
                    _check_job_cancelled(job_id)
                    finalize_job_success(job_id, "Manuel render tamamlandı.")
                except RenderReviewRequiredError as exc:
                    safe_outputs = list(exc.output_paths or [])
                    first_name = os.path.basename(safe_outputs[0]) if safe_outputs else None
                    finalize_job_review_required(
                        job_id,
                        exc.message,
                        review_items=exc.review_items,
                        output_paths=safe_outputs,
                        output_url=build_secure_clip_url(request.project_id, first_name) if request.project_id and first_name else None,
                        clip_name=first_name,
                        num_clips=exc.num_clips if exc.num_clips is not None else len(safe_outputs),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    _finalize_background_job_error(job_id, "Manuel render başarısız", exc)
                finally:
                    await run_blocking(orchestrator.cleanup_gpu)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _finalize_background_job_error(job_id, "Manuel render başarısız", exc)

    task = asyncio.create_task(_run())
    _attach_editor_task(job_id, task)
    return {"status": "started", "job_id": job_id}


@router.post("/reburn")
async def reburn_clip(
    http_request: Request,
    request: ReburnRequest,
    auth: AuthContext = Depends(require_policy("reburn")),
) -> dict:
    """Klibin altyazılarını yeniden basar."""
    _require_production_project(request.project_id)
    try:
        request.clip_name = sanitize_clip_name(request.clip_name)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc
    if request.project_id:
        try:
            request.project_id = sanitize_project_name(request.project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e
        ensure_project_access(http_request, auth, request.project_id, clip_name=request.clip_name)

    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"reburn_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    manager.jobs[job_id] = {
        "job_id": job_id,
        "url": request.clip_name,
        "style": request.style_name,
        "animation_type": request.animation_type,
        "status": "queued",
        "progress": 0,
        "last_message": "Altyazı yeniden basım kuyruğa alındı...",
        "created_at": time.time(),
        "project_id": request.project_id,
        "subject": auth.subject,
        "cancel_event": threading.Event(),
    }
    manager.seed_job_timeline(
        job_id,
        message="Altyazı yeniden basım kuyruğa alındı...",
        progress=0,
        status="queued",
        source="api",
    )

    async def _run() -> None:
        _broadcast_editor_job({"message": "İşlem sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.processing_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Altyazı yeniden basım başladı..."
            _broadcast_editor_job({"message": "Altyazı yeniden basım başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: _broadcast_editor_job(s, job_id)
            orchestrator = GodTierShortsCreator(
                ui_callback=cb,
                cancel_event=manager.jobs[job_id]["cancel_event"],
                subject=auth.subject,
                clip_event_port=build_api_clip_event_port(),
                gpu_stage_lock=manager.gpu_lock,
            )
            try:
                await orchestrator.reburn_subtitles_async(
                    clip_name=request.clip_name,
                    transcript=request.transcript,
                    project_id=request.project_id,
                    style_name=request.style_name,
                    animation_type=request.animation_type,
                )
                _check_job_cancelled(job_id)
                finalize_job_success(job_id, "Altyazı yeniden basımı tamamlandı.")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _finalize_background_job_error(job_id, "Reburn işlemi başarısız", exc)
            finally:
                await run_blocking(orchestrator.cleanup_gpu)

    task = asyncio.create_task(_run())
    _attach_editor_task(job_id, task)
    return {"status": "started", "job_id": job_id}
