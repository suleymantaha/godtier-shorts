"""
backend/api/websocket.py
==========================
WebSocket bağlantı yöneticisi.
(eski: api_server.py içindeki ConnectionManager sınıfı)
"""
import asyncio
import threading
import time
from concurrent.futures import Future
from typing import Any, Dict, Optional

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Tüm aktif WebSocket bağlantılarını ve iş (job) durumlarını yönetir."""

    # Job expiration süresi (saniye)
    JOB_EXPIRATION_SECONDS = 3600  # 1 saat
    # Periyodik temizlik aralığı (saniye)
    CLEANUP_INTERVAL_SECONDS = 300  # 5 dakika

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.gpu_lock = asyncio.Lock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._cleanup_task: asyncio.Task | None = None

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

    async def connect(self, websocket: WebSocket, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self.active_connections.append(websocket)
        logger.info(f"🟢 Yeni WebSocket bağlantısı kuruldu. Aktif bağlantı: {len(self.active_connections)}")
        logger.debug(f"🔢 Aktif WebSocket bağlantı sayısı: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"🔴 WebSocket bağlantısı koptu. Aktif bağlantı: {len(self.active_connections)}")
            logger.debug(f"🔢 Aktif WebSocket bağlantı sayısı: {len(self.active_connections)}")

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

        for ws in list(self.active_connections):
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
