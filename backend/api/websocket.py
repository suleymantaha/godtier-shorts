"""
backend/api/websocket.py
==========================
WebSocket bağlantı yöneticisi.
(eski: api_server.py içindeki ConnectionManager sınıfı)
"""
import asyncio
import os
import threading
import time
from concurrent.futures import Future
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import WebSocket
from loguru import logger

from backend.config import JOB_STATE_PATH
from backend.core.exceptions import RateLimitError
from backend.services.job_state import JobStateRepository


class ConnectionManager:
    """Tüm aktif WebSocket bağlantılarını ve iş (job) durumlarını yönetir."""

    # Job expiration süresi (saniye)
    JOB_EXPIRATION_SECONDS = 3600  # 1 saat
    # Periyodik temizlik aralığı (saniye)
    CLEANUP_INTERVAL_SECONDS = 300  # 5 dakika
    DEFAULT_MAX_ACTIVE_JOBS_PER_SUBJECT = 1
    DEFAULT_MAX_PENDING_JOBS_PER_SUBJECT = 3
    MAX_JOB_TIMELINE_ENTRIES = 300

    def __init__(self, *, job_repository: JobStateRepository | None = None) -> None:
        self.active_connections: dict[WebSocket, str] = {}
        self.processing_lock = asyncio.Lock()
        self.gpu_lock = asyncio.Lock()
        self.jobs: Dict[str, Dict[str, Any]] = job_repository if job_repository is not None else JobStateRepository()
        self._cleanup_task: asyncio.Task | None = None

    @staticmethod
    def _read_positive_int_env(name: str, default: int) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    def subject_job_counts(self, subject: str) -> tuple[int, int]:
        active = 0
        pending = 0
        for job in self.jobs.values():
            if str(job.get("subject") or "") != subject:
                continue
            status = str(job.get("status") or "")
            if status == "processing":
                active += 1
            elif status == "queued":
                pending += 1
        return active, pending

    def assert_subject_can_enqueue(self, subject: str) -> None:
        max_active = self._read_positive_int_env(
            "MAX_ACTIVE_JOBS_PER_SUBJECT",
            self.DEFAULT_MAX_ACTIVE_JOBS_PER_SUBJECT,
        )
        max_pending = self._read_positive_int_env(
            "MAX_PENDING_JOBS_PER_SUBJECT",
            self.DEFAULT_MAX_PENDING_JOBS_PER_SUBJECT,
        )
        active, pending = self.subject_job_counts(subject)
        if pending >= max_pending:
            raise RateLimitError(
                "Ayni kullanici icin bekleyen is limiti asildi.",
                details={
                    "subject": subject,
                    "active_jobs": active,
                    "pending_jobs": pending,
                    "max_active_jobs": max_active,
                    "max_pending_jobs": max_pending,
                },
            )

    async def start_cleanup_task(self) -> None:
        """Periyodik job temizleme görevini başlatır."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_jobs())
            logger.info("🧹 Job cleanup görevi başlatıldı.")

    async def stop_cleanup_task(self) -> None:
        """Shutdown sırasında cleanup görevini iptal eder."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("🧹 Job cleanup görevi durduruldu.")

    async def _cleanup_expired_jobs(self) -> None:
        """Süresi dolmuş jobları temizler."""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
                current_time = time.time()
                expired_jobs = []
                
                for job_id, job in self.jobs.items():
                    # Tamamlanmış veya hatalı job'ları kontrol et
                    status = job.get("status", "")
                    created_at = job.get("created_at", 0)
                    
                    if status in ("completed", "error", "cancelled", "review_required"):
                        # Süresi dolmuş tamamlanmış jobları temizle
                        if current_time - created_at > self.JOB_EXPIRATION_SECONDS:
                            expired_jobs.append(job_id)
                
                for job_id in expired_jobs:
                    del self.jobs[job_id]
                    logger.info(f"🧹 Süresi dolmuş job temizlendi: {job_id}")
                    
            except asyncio.CancelledError:
                logger.info("🧹 Job cleanup görevi durduruldu.")
                break
            except Exception as e:
                logger.error(f"🧹 Job cleanup hatası: {e}")

    async def connect(self, websocket: WebSocket, *, subject: str, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self.active_connections[websocket] = subject
        logger.info(f"🟢 Yeni WebSocket bağlantısı kuruldu. Aktif bağlantı: {len(self.active_connections)}")
        logger.debug(f"🔢 Aktif WebSocket bağlantı sayısı: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.pop(websocket, None)
            logger.info(f"🔴 WebSocket bağlantısı koptu. Aktif bağlantı: {len(self.active_connections)}")
            logger.debug(f"🔢 Aktif WebSocket bağlantı sayısı: {len(self.active_connections)}")

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _resolve_status(
        *,
        current_status: str,
        progress: int,
        status: str | None,
    ) -> str:
        if status is not None:
            return status
        if progress < 0:
            return "error"
        if progress >= 100:
            return current_status if current_status in {"empty", "cancelled", "review_required"} else "completed"
        if current_status in {"queued", "processing"}:
            return current_status
        return "processing"

    @staticmethod
    def _resolve_event_source(
        *,
        event_type: str | None,
        source: str | None,
    ) -> str:
        if source in {"api", "worker", "websocket", "clip_ready"}:
            return source
        if event_type == "clip_ready":
            return "clip_ready"
        return "worker"

    @staticmethod
    def _normalize_download_progress(download_progress: Any) -> dict[str, Any] | None:
        if not isinstance(download_progress, dict):
            return None
        normalized: dict[str, Any] = {"phase": "download"}
        for key in ("downloaded_bytes", "total_bytes", "total_bytes_estimate"):
            value = download_progress.get(key)
            if isinstance(value, int):
                normalized[key] = value
        percent = download_progress.get("percent")
        if isinstance(percent, (int, float)):
            normalized["percent"] = float(percent)
        for key in ("speed_text", "eta_text", "status"):
            value = download_progress.get(key)
            if isinstance(value, str) and value:
                normalized[key] = value
        return normalized if len(normalized) > 1 else None

    def _apply_job_extra(
        self,
        job: dict[str, Any],
        event: dict[str, Any],
        extra: dict[str, Any] | None,
    ) -> None:
        if not extra:
            return
        download_progress = self._normalize_download_progress(extra.get("download_progress"))
        if download_progress is None:
            return
        event["download_progress"] = download_progress
        job["download_progress"] = download_progress

    def append_job_timeline_event(
        self,
        job_id: str,
        *,
        message: str,
        progress: int,
        status: str | None = None,
        source: str = "worker",
        at: str | None = None,
        event_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None

        current_status = str(job.get("status", ""))
        resolved_status = self._resolve_status(
            current_status=current_status,
            progress=progress,
            status=status,
        )
        timeline = list(job.get("timeline") or [])
        resolved_at = at or self._utc_now_iso()
        resolved_event_id = event_id
        if not resolved_event_id:
            if not timeline and source == "api" and resolved_status == "queued" and progress == 0:
                resolved_event_id = f"{job_id}:queued"
            else:
                resolved_event_id = f"{job_id}:{time.time_ns()}"

        for existing_event in timeline:
            if str(existing_event.get("id") or "") == resolved_event_id:
                job["status"] = resolved_status
                job["progress"] = progress
                job["last_message"] = message
                self._apply_job_extra(job, existing_event, extra)
                return existing_event

        event = {
            "id": resolved_event_id,
            "at": resolved_at,
            "job_id": job_id,
            "status": resolved_status,
            "progress": progress,
            "message": message,
            "source": source,
        }
        self._apply_job_extra(job, event, extra)
        timeline.append(event)
        job["timeline"] = timeline[-self.MAX_JOB_TIMELINE_ENTRIES :]
        job["status"] = resolved_status
        job["progress"] = progress
        job["last_message"] = message
        return event

    def seed_job_timeline(
        self,
        job_id: str,
        *,
        message: str,
        progress: int,
        status: str = "queued",
        source: str = "api",
    ) -> dict[str, Any] | None:
        return self.append_job_timeline_event(
            job_id,
            message=message,
            progress=progress,
            status=status,
            source=source,
        )

    async def close_subject_connections(self, subject: str) -> int:
        closed = 0
        for websocket, ws_subject in list(self.active_connections.items()):
            if ws_subject != subject:
                continue
            closed += 1
            close = getattr(websocket, "close", None)
            if callable(close):
                try:
                    result = close(code=1000)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"WebSocket kapatma hatası: {e}")
            self.disconnect(websocket)
        return closed

    def purge_subject_jobs(self, subject: str) -> int:
        purged_job_ids = [
            job_id
            for job_id, job in self.jobs.items()
            if str(job.get("subject") or "") == subject
        ]
        for job_id in purged_job_ids:
            job = self.jobs.get(job_id)
            if job is None:
                continue
            cancel_event = job.get("cancel_event")
            if cancel_event is not None:
                cancel_event.set()
            task_handle = job.get("task_handle")
            if task_handle is not None:
                try:
                    task_handle.cancel()
                except Exception as e:
                    logger.error(f"Job task iptal edilemedi: {e}")
            job["status"] = "cancelled"
            self.jobs.pop(job_id, None)
        return len(purged_job_ids)

    async def broadcast_progress(
        self,
        message: str,
        progress: int,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {"message": message, "progress": progress}
        if status:
            payload["status"] = status
        if extra:
            payload.update(extra)

        if job_id:
            payload["job_id"] = job_id
            resolved_source = self._resolve_event_source(
                event_type=str(payload.get("event_type") or "") or None,
                source=str(payload.get("source") or "") or None,
            )
            event = self.append_job_timeline_event(
                job_id,
                message=message,
                progress=progress,
                status=status,
                source=resolved_source,
                at=str(payload.get("at") or "") or None,
                event_id=str(payload.get("event_id") or "") or None,
                extra=extra,
            )
            if event is not None:
                payload["event_id"] = event["id"]
                payload["at"] = event["at"]
                payload["status"] = event["status"]
                payload["source"] = event["source"]
                if "download_progress" in event:
                    payload["download_progress"] = event["download_progress"]

        target_subject = None
        if job_id:
            target_subject = self.jobs.get(job_id, {}).get("subject")

        for ws, ws_subject in list(self.active_connections.items()):
            if target_subject is not None and ws_subject != target_subject:
                continue
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.error(f"WebSocket gönderim hatası: {e}")
                self.disconnect(ws)


# Singleton — tüm route modülleri bu nesneyi import eder
manager = ConnectionManager(job_repository=JobStateRepository(JOB_STATE_PATH))

# Ana event loop referansı (thread'lerden güvenli erişim için)
_main_loop: asyncio.AbstractEventLoop | None = None
_pending_broadcasts: Dict[str, int] = {}
_pending_lock = threading.Lock()
_MAX_PENDING_PER_JOB = 20


def _is_priority_broadcast(
    status: dict,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    event_type = str((extra or {}).get("event_type") or "")
    resolved_status = str(status.get("status") or "")
    progress = int(status.get("progress", 0))
    return event_type == "clip_ready" or resolved_status in {"completed", "error", "review_required"} or progress >= 100


def get_main_loop() -> asyncio.AbstractEventLoop | None:
    return _main_loop


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def _broadcast_bucket(job_id: Optional[str]) -> str:
    return job_id if job_id else "__global__"


def _release_pending(bucket: str) -> None:
    with _pending_lock:
        pending_count = _pending_broadcasts.get(bucket, 0)
        if pending_count <= 1:
            _pending_broadcasts.pop(bucket, None)
        else:
            _pending_broadcasts[bucket] = pending_count - 1


def _log_broadcast_result(future: Future[None], bucket: str) -> None:
    try:
        future.result()
    except Exception as e:
        logger.error(f"⚠️ WebSocket mesaj gönderilemedi: {e}")
    finally:
        _release_pending(bucket)


def thread_safe_broadcast(
    status: dict,
    job_id: Optional[str] = None,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Background thread'inden WebSocket mesajı gönderir."""
    loop = get_main_loop()
    if loop and loop.is_running():
        bucket = _broadcast_bucket(job_id)
        merged_extra = {
            key: value
            for key, value in status.items()
            if key not in {"message", "progress", "status"}
        }
        if extra:
            merged_extra.update(extra)
        normalized_extra = merged_extra or None
        is_priority = _is_priority_broadcast(status, normalized_extra)

        with _pending_lock:
            pending_count = _pending_broadcasts.get(bucket, 0)
            if pending_count >= _MAX_PENDING_PER_JOB and not is_priority:
                logger.warning(
                    "⚠️ WebSocket mesajı düşürüldü (backpressure): "
                    f"job_id={job_id or 'global'}, pending={pending_count}"
                )
                return
            _pending_broadcasts[bucket] = pending_count + 1

        try:
            future = asyncio.run_coroutine_threadsafe(
                manager.broadcast_progress(
                    status["message"],
                    status["progress"],
                    job_id,
                    status.get("status"),
                    normalized_extra,
                ),
                loop,
            )
            future.add_done_callback(lambda fut: _log_broadcast_result(fut, bucket))
        except Exception as e:
            _release_pending(bucket)
            logger.error(f"⚠️ WebSocket mesaj gönderilemedi: {e}")
    else:
        logger.warning("⚠️ Event loop hazır değil, WebSocket mesajı gönderilemedi.")
