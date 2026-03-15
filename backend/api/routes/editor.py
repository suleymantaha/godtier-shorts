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
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from loguru import logger
from pydantic import ValidationError

from backend.config import (
    TEMP_DIR, VIDEO_METADATA, ProjectPaths,
    get_project_path, sanitize_project_name,
)
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.security import AuthContext, ensure_project_access, require_policy
from backend.api.routes.clips import (
    ACTIVE_JOB_STATUSES,
    build_secure_clip_url,
    build_clip_transcript_response,
    ensure_project_transcript,
    finalize_job_error,
    finalize_job_success,
    find_clip_recovery_job,
    find_project_transcript_job,
    load_clip_payload,
    prepare_uploaded_project,
    resolve_project_transcript_state,
)
from backend.core.media_ops import build_shifted_transcript_segments
from backend.core.orchestrator import GodTierShortsCreator
from backend.core.exceptions import InvalidInputError, JobExecutionError
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
DEFAULT_MANUAL_CUT_LAYOUT = "single"
CLIP_RECOVERY_JOB_PREFIX = "cliprecover"


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
                "ffmpeg",
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
        )
        with open(transcript_temp, "r", encoding="utf-8") as f:
            transcript_data = json.load(f)
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
            thread_safe_broadcast(
                {"message": "Proje transkriptinden klip metadata kurtarılıyor...", "progress": 1, "status": "processing"},
                job_id,
            )
            await asyncio.to_thread(
                _recover_clip_transcript_from_project,
                clip_name,
                project_id,
                lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
            )
            return "project_slice"
        except (RuntimeError, ValueError, OSError, InvalidInputError, JobExecutionError) as exc:
            if not can_transcribe_source:
                raise
            logger.warning("Project slice recovery failed for {}: {}", clip_name, exc)
            thread_safe_broadcast(
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
        thread_safe_broadcast(
            {"message": "Kaynak videodan transkript çıkarılıyor...", "progress": 50, "status": "processing"},
            job_id,
        )
        await asyncio.to_thread(
            _recover_clip_transcript_from_source,
            clip_name,
            project_id,
            lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
        )
    return "transcribe_source"


@router.post("/process-batch")
async def process_batch_clips(
    http_request: Request,
    request: BatchJobRequest,
    auth: AuthContext = Depends(require_policy("process_batch")),
) -> dict:
    """Seçilen aralıkta AI ile toplu klip üretir."""
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
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.gpu_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Toplu üretim başladı..."
            thread_safe_broadcast({"message": "Toplu üretim başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: thread_safe_broadcast(s, job_id)
            orchestrator = GodTierShortsCreator(ui_callback=cb, subject=auth.subject)
            try:
                path = get_project_path(request.project_id, "transcript.json") if request.project_id else VIDEO_METADATA
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        transcript_data = json.load(f)
                else:
                    transcript_data = []

                await asyncio.to_thread(
                    orchestrator.run_batch_manual_clips,
                    start_t=request.start_time,
                    end_t=request.end_time,
                    num_clips=request.num_clips,
                    transcript_data=transcript_data,
                    duration_min=120.0,
                    duration_max=180.0,
                    style_name=request.style_name,
                    animation_type=request.animation_type,
                    project_id=request.project_id,
                    layout=request.layout,
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
    auth: AuthContext = Depends(require_policy("manual_cut_upload")),
) -> dict:
    """Video + zaman aralığı ile otomatik manual cut üretir. cut_points veya num_clips>1 ile çoklu klip."""
    try:
        request = ManualAutoCutRequest(start_time=start_time, end_time=end_time)
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

    pts = _parse_cut_points(cut_points)
    use_cut_points = pts is not None and len(pts) >= 2
    num_clips = max(1, min(20, num_clips))
    is_batch = not use_cut_points and num_clips > 1

    project, project_id, _is_cached = prepare_uploaded_project(file, owner_subject=auth.subject)
    manager.assert_subject_can_enqueue(auth.subject)
    job_id = f"manualcut_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    clip_name = f"manual_{job_id}.mp4" if not is_batch else None
    output_url = build_secure_clip_url(project_id, clip_name) if clip_name else None

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
        "clip_name": clip_name,
        "output_url": output_url,
        "num_clips": num_clips,
        "subject": auth.subject,
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
                orchestrator = GodTierShortsCreator(ui_callback=cb, subject=auth.subject)
                try:
                    if use_cut_points:
                        assert pts is not None  # use_cut_points implies pts is not None
                        output_paths = await orchestrator.run_manual_clips_from_cut_points_async(
                            cut_points=pts,
                            transcript_data=transcript_data,
                            style_name=style_name,
                            animation_type=animation_type,
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
                            duration_min=120.0,
                            duration_max=180.0,
                            style_name=style_name,
                            animation_type=animation_type,
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
                            animation_type=animation_type,
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
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
            async with manager.gpu_lock:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Proje transkripti yeniden çıkarılıyor..."
                thread_safe_broadcast(
                    {"message": "Proje transkripti yeniden çıkarılıyor...", "progress": 1, "status": "processing"},
                    job_id,
                )
                await asyncio.to_thread(
                    ensure_project_transcript,
                    project,
                    lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
                )
            finalize_job_success(job_id, "Proje transkripti hazır.")
        except (RuntimeError, ValueError, OSError) as exc:
            mapped_error = JobExecutionError("Proje transkripti üretilemedi", details=str(exc))
            logger.error(f"Proje transkript kurtarma hatası ({job_id}): {mapped_error.message}")
            finalize_job_error(job_id, mapped_error)

    task = asyncio.create_task(_run())
    manager.jobs[job_id]["task"] = task
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
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "Kurtarma sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        try:
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
                    thread_safe_broadcast({"message": "Kaynak videodan transkript çıkarılıyor...", "progress": 1, "status": "processing"}, job_id)
                    await asyncio.to_thread(
                        _recover_clip_transcript_from_source,
                        request.clip_name,
                        effective_project_id,
                        lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
                    )
            else:
                manager.jobs[job_id]["status"] = "processing"
                manager.jobs[job_id]["last_message"] = "Proje transkriptinden klip metadata kurtarılıyor..."
                thread_safe_broadcast({"message": "Proje transkriptinden klip metadata kurtarılıyor...", "progress": 1, "status": "processing"}, job_id)
                await asyncio.to_thread(
                    _recover_clip_transcript_from_project,
                    request.clip_name,
                    effective_project_id,
                    lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
                )

            finalize_job_success(job_id, "Klip transkripti kurtarma tamamlandı.")
        except (RuntimeError, ValueError, OSError, InvalidInputError, JobExecutionError) as exc:
            mapped_error = JobExecutionError("Klip transkripti kurtarma başarısız", details=str(exc))
            logger.error(f"Klip transkript kurtarma hatası ({job_id}): {mapped_error.message}")
            finalize_job_error(job_id, mapped_error)

    task = asyncio.create_task(_run())
    manager.jobs[job_id]["task"] = task
    return {"status": "started", "job_id": job_id}


@router.post("/process-manual")
async def process_manual_clip(
    http_request: Request,
    request: ManualJobRequest,
    auth: AuthContext = Depends(require_policy("process_manual")),
) -> dict:
    """Kullanıcının elle seçtiği aralığı işler."""
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
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.gpu_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Manuel render başladı..."
            thread_safe_broadcast({"message": "Manuel render başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: thread_safe_broadcast(s, job_id)
            orchestrator = GodTierShortsCreator(ui_callback=cb, subject=auth.subject)
            try:
                await orchestrator.run_manual_clip_async(
                    start_t=request.start_time,
                    end_t=request.end_time,
                    transcript_data=request.transcript,
                    style_name=request.style_name,
                    animation_type=request.animation_type,
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
    http_request: Request,
    request: ReburnRequest,
    auth: AuthContext = Depends(require_policy("reburn")),
) -> dict:
    """Klibin altyazılarını yeniden basar."""
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
    }

    async def _run() -> None:
        thread_safe_broadcast({"message": "GPU sırası bekleniyor...", "progress": 0, "status": "queued"}, job_id)
        async with manager.gpu_lock:
            manager.jobs[job_id]["status"] = "processing"
            manager.jobs[job_id]["last_message"] = "Altyazı yeniden basım başladı..."
            thread_safe_broadcast({"message": "Altyazı yeniden basım başladı...", "progress": 1, "status": "processing"}, job_id)
            cb = lambda s: thread_safe_broadcast(s, job_id)
            orchestrator = GodTierShortsCreator(ui_callback=cb, subject=auth.subject)
            try:
                await orchestrator.reburn_subtitles_async(
                    clip_name=request.clip_name,
                    transcript=request.transcript,
                    project_id=request.project_id,
                    style_name=request.style_name,
                    animation_type=request.animation_type,
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
