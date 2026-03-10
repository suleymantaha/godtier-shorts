"""
backend/api/routes/clips.py
=================================
Üretilen klipleri yönetmek için endpoint'ler:
  GET  /api/clips
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
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from backend.config import (
    OUTPUTS_DIR, DOWNLOADS_DIR, MASTER_VIDEO, MASTER_AUDIO,
    VIDEO_METADATA, VIDEO_HASH, PROJECTS_DIR, ProjectPaths,
    get_project_path, sanitize_clip_name, sanitize_project_name,
    MAX_UPLOAD_BYTES,
)
from backend.api.websocket import manager, thread_safe_broadcast
from backend.api.security import AuthContext, require_policy
from backend.services.transcription import run_transcription
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
    thread_safe_broadcast({"message": last_message, "progress": 100}, job_id)


def finalize_job_error(job_id: str, error: Exception) -> None:
    """İşi hataya düşürür ve standart hata bilgisini yayınlar."""
    message = f"HATA: {error}"
    if job_id in manager.jobs:
        manager.jobs[job_id]["status"] = "error"
        manager.jobs[job_id]["error"] = str(error)
        manager.jobs[job_id]["last_message"] = message
    thread_safe_broadcast({"message": message, "progress": -1}, job_id)


ALLOWED_UPLOAD_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-m4v"}
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".m4v"}
ALLOWED_CONTAINERS = {"mp4", "mov", "m4a", "3gp", "3g2", "mj2"}

ALLOWED_PROJECT_FILE_EXTENSIONS = {".mp4", ".json"}
ALLOWED_PROJECT_FILE_KINDS = {"clip", "master", "clip_metadata", "transcript"}


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


def _compute_file_hash(path: str) -> str:
    """Dosyanın SHA256 hash'ini hesaplar (64KB bloklar halinde)."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _upload_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def validate_upload_size(file: UploadFile) -> None:
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_UPLOAD_BYTES:
        raise InvalidInputError(f"Dosya boyutu çok büyük. Maksimum: {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")


def _validate_upload_type(file: UploadFile) -> None:
    filename = (file.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower()
    content_type = (file.content_type or "").lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise _upload_http_error(
            status_code=400,
            code="UNSUPPORTED_FILE_EXTENSION",
            message="Desteklenmeyen dosya uzantısı. Lütfen MP4/MOV/M4V formatında bir video yükleyin.",
        )

    if content_type and content_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise _upload_http_error(
            status_code=400,
            code="UNSUPPORTED_MIME_TYPE",
            message="Desteklenmeyen dosya türü. Lütfen geçerli bir video dosyası yükleyin (örn. video/mp4).",
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


def prepare_uploaded_project(file: UploadFile) -> tuple[ProjectPaths, str, bool]:
    """Yüklenen videodan proje oluşturur veya mevcut projeyi reuse eder."""
    validate_upload_size(file)
    _validate_upload_type(file)

    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    try:
        with os.fdopen(fd, "wb") as tmp:
            shutil.copyfileobj(file.file, tmp)

        _validate_video_with_ffprobe(temp_path)

        file_hash = _compute_file_hash(temp_path)
        project_id = f"up_{file_hash[:16]}"
        project = ProjectPaths(project_id)
        is_cached = project.master_video.exists() and project.transcript.exists()

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


@router.get("/projects")
async def list_projects() -> dict:
    """Proje klasörlerini listeler. master.mp4 ve transcript.json varlığını döner."""
    projects = []
    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            projects.append({
                "id": project_dir.name,
                "has_master": (project_dir / "master.mp4").exists(),
                "has_transcript": (project_dir / "transcript.json").exists(),
            })
    return {"projects": sorted(projects, key=lambda p: p["id"])}


@router.get("/projects/{project_id}/master")
async def get_project_master_video(project_id: str) -> FileResponse:
    """Proje master videosunu kontrollü olarak servis eder."""
    try:
        safe_project = sanitize_project_name(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    path = (PROJECTS_DIR / safe_project / "master.mp4").resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Master video bulunamadı")

    return FileResponse(path=path, media_type="video/mp4", filename="master.mp4")


@router.get("/projects/{project_id}/shorts/{clip_name}")
async def get_project_short_asset(project_id: str, clip_name: str) -> FileResponse:
    """Sadece proje shorts klasöründeki .mp4/.json dosyalarını kontrollü olarak servis eder."""
    try:
        safe_project = sanitize_project_name(project_id)
        safe_clip = sanitize_clip_name(clip_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ext = os.path.splitext(safe_clip)[1].lower()
    if ext not in {".mp4", ".json"}:
        raise HTTPException(status_code=403, detail="Yalnızca .mp4 ve .json shorts varlıklarına izin verilir")

    shorts_dir = (PROJECTS_DIR / safe_project / "shorts").resolve()
    asset_path = (shorts_dir / safe_clip).resolve()
    if shorts_dir not in asset_path.parents:
        raise HTTPException(status_code=403, detail="Geçersiz dosya yolu")
    if not asset_path.exists() or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")

    media_type = "video/mp4" if ext == ".mp4" else "application/json"
    return FileResponse(path=asset_path, media_type=media_type, filename=safe_clip)


@router.get("/clips")
async def list_clips() -> dict:
    """Proje klasörlerindeki tüm videoları listeler."""
    clips = []
    
    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            
            shorts_dir = project_dir / "shorts"
            if not shorts_dir.exists():
                continue
                
            for f in shorts_dir.iterdir():
                if f.suffix == ".mp4" and not f.name.startswith("temp_"):
                    meta_path = shorts_dir / f.name.replace(".mp4", ".json")
                    ui_title = ""
                    if meta_path.exists():
                        try:
                            with open(meta_path, "r", encoding="utf-8") as m:
                                meta_data = json.load(m)
                                ui_title = extract_ui_title(meta_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error in {meta_path}: {e}")
                        except OSError as e:
                            logger.error(f"Error reading metadata {meta_path}: {e}")
                    
                    clips.append({
                        "name":           f.name,
                        "project":        project_dir.name,
                        "url":            build_project_file_url(project_dir.name, "clip", f.name),
                        "has_transcript": meta_path.exists(),
                        "ui_title":       ui_title,
                        "created_at":     f.stat().st_ctime,
                    })

    # Eski yapıdaki klipleri de dahil et (Geriye dönük uyumluluk)
    if OUTPUTS_DIR.exists():
        for f in OUTPUTS_DIR.iterdir():
            if f.suffix == ".mp4" and not f.name.startswith("temp_") and not any(c["name"] == f.name for c in clips):
                meta_path = OUTPUTS_DIR / f.name.replace(".mp4", ".json")
                ui_title = ""
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as m:
                            meta_data = json.load(m)
                            ui_title = extract_ui_title(meta_data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode error in {meta_path}: {e}")
                    except OSError as e:
                        logger.error(f"Error reading metadata {meta_path}: {e}")
                
                clips.append({
                    "name":           f.name,
                    "project":        "legacy",
                    "url":            f"/outputs/{f.name}",
                    "has_transcript": meta_path.exists(),
                    "ui_title":       ui_title,
                    "created_at":     f.stat().st_ctime,
                })

    return {"clips": sorted(clips, key=lambda x: x["created_at"], reverse=True)}


@router.get("/clip-transcript/{clip_name}")
async def get_clip_transcript(clip_name: str, project_id: str | None = None) -> dict:
    """Belirli bir klibin transkriptini getirir."""
    try:
        clip_name = sanitize_clip_name(clip_name)
    except ValueError as e:
        raise InvalidInputError(str(e)) from e
    if project_id and project_id != "legacy":
        try:
            sanitize_project_name(project_id)
        except ValueError as e:
            raise InvalidInputError(str(e)) from e

    path = OUTPUTS_DIR / clip_name.replace(".mp4", ".json")
    resolved_project_id = project_id
    if project_id and project_id != "legacy":
        project_path = get_project_path(project_id, "shorts", clip_name.replace(".mp4", ".json"))
        if project_path.exists():
            path = project_path
    elif not path.exists() and PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            candidate = project_dir / "shorts" / clip_name.replace(".mp4", ".json")
            if candidate.exists():
                path = candidate
                resolved_project_id = project_dir.name
                break

    if not path.exists():
        return normalize_clip_payload([], clip_name, resolved_project_id)
    with open(path, "r", encoding="utf-8") as f:
        return normalize_clip_payload(json.load(f), clip_name, resolved_project_id)


@router.get("/projects/{project_id}/files/{file_kind}")
async def get_project_file(project_id: str, file_kind: str, clip_name: str | None = None):
    """Yalnızca whitelist edilen proje dosyalarını döndürür."""
    path = _safe_project_file_path(project_id, file_kind, clip_name)
    media_type = "video/mp4" if path.suffix.lower() == ".mp4" else "application/json"
    return FileResponse(path=str(path), media_type=media_type, filename=path.name)


@router.get("/projects/{project_id}/files/{file_kind}/{clip_name}")
async def get_project_file_with_clip_name(project_id: str, file_kind: str, clip_name: str):
    """Klip bazlı dosyaları query string olmadan döndürür."""
    path = _safe_project_file_path(project_id, file_kind, clip_name)
    media_type = "video/mp4" if path.suffix.lower() == ".mp4" else "application/json"
    return FileResponse(path=str(path), media_type=media_type, filename=path.name)


@router.post("/upload")
async def upload_local_video(
    file: UploadFile = File(...),
    _: AuthContext = Depends(require_policy("upload")),
) -> dict:
    """Arayüzden yüklenen videoyu kaydeder, bir proje oluşturur ve transkripsiyon başlatır."""
    project, project_id, is_cached = prepare_uploaded_project(file)

    if is_cached:
        return {
            "status": "cached",
            "job_id": f"cached_{int(time.time())}",
            "message": "Video zaten analiz edilmiş, kütüphaneden getiriliyor.",
            "project_id": project_id,
        }

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
    }

    async def _run() -> None:
        try:
            manager.jobs[job_id]["status"] = "processing"
            await asyncio.to_thread(
                ensure_project_transcript,
                project,
                lambda msg, pct: thread_safe_broadcast({"message": msg, "progress": pct}, job_id),
            )
            finalize_job_success(job_id, "Transkripsiyon tamamlandı.")
        except (MediaSubprocessError, FileOperationError, JobExecutionError, TranscriptionError) as exc:
            logger.error(f"Upload transkripsiyon hatası ({job_id}): {exc.message}")
            finalize_job_error(job_id, exc)

    asyncio.create_task(_run())
    return {"status": "uploaded", "job_id": job_id, "message": "Video yüklendi, transkripsiyon başladı.", "project_id": project_id}
