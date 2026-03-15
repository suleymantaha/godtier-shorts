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
from typing import Any, Dict, Optional

from fastapi import WebSocket
from loguru import logger

from backend.core.exceptions import RateLimitError


class ConnectionManager:
    """Tüm aktif WebSocket bağlantılarını ve iş (job) durumlarını yönetir."""

    # Job expiration süresi (saniye)
    JOB_EXPIRATION_SECONDS = 3600  # 1 saat
    # Periyodik temizlik aralığı (saniye)
    CLEANUP_INTERVAL_SECONDS = 300  # 5 dakika
    DEFAULT_MAX_ACTIVE_JOBS_PER_SUBJECT = 1
    DEFAULT_MAX_PENDING_JOBS_PER_SUBJECT = 3

    def __init__(self) -> None:
        self.active_connections: dict[WebSocket, str] = {}
        self.gpu_lock = asyncio.Lock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
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
                    
                    if status in ("completed", "error", "cancelled"):
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
    ) -> None:
        payload: Dict[str, Any] = {"message": message, "progress": progress}
        if status:
            payload["status"] = status

        if job_id:
            payload["job_id"] = job_id
            if job_id in self.jobs:
                current_status = str(self.jobs[job_id].get("status", ""))
                if status is not None:
                    resolved_status = status
                elif progress < 0:
                    resolved_status = "error"
                elif progress >= 100:
                    resolved_status = current_status if current_status in {"empty", "cancelled"} else "completed"
                elif current_status in {"queued", "processing"}:
                    resolved_status = current_status
                else:
                    resolved_status = "processing"
                self.jobs[job_id]["status"]       = resolved_status
                self.jobs[job_id]["progress"]     = progress
                self.jobs[job_id]["last_message"] = message

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
manager = ConnectionManager()

# Ana event loop referansı (thread'lerden güvenli erişim için)
_main_loop: asyncio.AbstractEventLoop | None = None
_pending_broadcasts: Dict[str, int] = {}
_pending_lock = threading.Lock()
_MAX_PENDING_PER_JOB = 20


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


def thread_safe_broadcast(status: dict, job_id: Optional[str] = None) -> None:
    """Background thread'inden WebSocket mesajı gönderir."""
    loop = get_main_loop()
    if loop and loop.is_running():
        bucket = _broadcast_bucket(job_id)

        with _pending_lock:
            pending_count = _pending_broadcasts.get(bucket, 0)
            if pending_count >= _MAX_PENDING_PER_JOB:
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
                    status.get("status")
                ),
                loop,
            )
            future.add_done_callback(lambda fut: _log_broadcast_result(fut, bucket))
        except Exception as e:
            _release_pending(bucket)
            logger.error(f"⚠️ WebSocket mesaj gönderilemedi: {e}")
    else:
        logger.warning("⚠️ Event loop hazır değil, WebSocket mesajı gönderilemedi.")
