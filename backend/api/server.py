"""
backend/api/server.py
=======================
FastAPI uygulama fabrikası.
CORS, statik dosya sunumu, router kayıtları ve startup event burada.
"""
import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.config import (
    CORS_ORIGINS, OUTPUTS_DIR, LOGS_DIR,
    MASTER_VIDEO, DOWNLOADS_DIR, PROJECTS_DIR
)
from backend.api.websocket import manager, set_main_loop
from backend.api.routes import jobs, clips, editor
from backend.api.error_handlers import register_exception_handlers

# Loglama
logger.add(
    str(LOGS_DIR / "api_server_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü yönetimi."""
    # Startup
    set_main_loop(asyncio.get_running_loop())
    logger.info("✅ Ana asyncio event loop kaydedildi.")
    
    # Job cleanup görevini başlat
    await manager.start_cleanup_task()
    logger.info("🧹 Job cleanup görevi etkinleştirildi.")
    
    # outputs klasörüne master_video sembolik bağı oluştur
    link_path = OUTPUTS_DIR / "master_video.mp4"
    if MASTER_VIDEO.exists() and not (link_path.exists() or link_path.is_symlink()):
        try:
            link_path.symlink_to(MASTER_VIDEO.resolve())
            logger.info("🔗 master_video.mp4 sembolik bağı oluşturuldu.")
        except Exception as e:
            logger.error(f"🔗 Sembolik bağ oluşturulamadı: {e}")
    
    logger.info("🚀 Uygulama başlatıldı.")
    
    yield  # App runs here

    # Shutdown
    await manager.stop_cleanup_task()
    logger.info("👋 Uygulama kapatılıyor...")


def create_app() -> FastAPI:
    """FastAPI uygulamasını oluşturur ve yapılandırır."""
    app = FastAPI(
        title="God-Tier Shorts API",
        version="2.0.0",
        description="AI destekli viral short video üretimi",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def attach_trace_id(request: Request, call_next):
        request.state.trace_id = (
            request.headers.get("x-trace-id")
            or request.headers.get("x-request-id")
            or str(uuid4())
        )
        return await call_next(request)

    register_exception_handlers(app)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Statik dosya sunumu (üretilen videolar) ---
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
    app.mount("/projects", StaticFiles(directory=str(PROJECTS_DIR)), name="projects")

    # --- Router'ları kaydet ---
    app.include_router(jobs.router)
    app.include_router(clips.router)
    app.include_router(editor.router)

    # --- WebSocket endpoint ---
    @app.websocket("/ws/progress")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()  # Bağlantıyı açık tut
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app
