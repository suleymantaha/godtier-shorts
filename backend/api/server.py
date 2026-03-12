"""
backend/api/server.py
=======================
FastAPI uygulama fabrikası.
CORS, router kayıtları ve startup event burada.
"""
import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from backend.config import (
    CORS_ORIGINS, OUTPUTS_DIR, LOGS_DIR, MASTER_VIDEO, REQUEST_BODY_HARD_LIMIT_BYTES,
)
from backend.api.websocket import manager, set_main_loop
from backend.api.routes import jobs, clips, editor
from backend.api.error_handlers import register_exception_handlers
from backend.api.security import authenticate_websocket_token, validate_auth_configuration

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
    validate_auth_configuration()
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
        guarded_upload_paths = {"/api/upload", "/api/manual-cut-upload"}
        if request.method == "POST" and request.url.path in guarded_upload_paths:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > REQUEST_BODY_HARD_LIMIT_BYTES:
                        trace_id = request.state.trace_id
                        return JSONResponse(
                            status_code=413,
                            content={
                                "code": "REQUEST_TOO_LARGE",
                                "message": "İstek gövdesi izin verilen sınırı aşıyor.",
                                "details": {
                                    "limit_bytes": REQUEST_BODY_HARD_LIMIT_BYTES,
                                },
                                "trace_id": trace_id,
                            },
                        )
                except ValueError:
                    pass

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    register_exception_handlers(app)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Router'ları kaydet ---
    app.include_router(jobs.router)
    app.include_router(clips.router)
    app.include_router(editor.router)

    # --- WebSocket endpoint ---
    @app.websocket("/ws/progress")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        token = None
        selected_subprotocol: str | None = None

        protocol_header = websocket.headers.get("sec-websocket-protocol", "")
        if protocol_header:
            parts = [part.strip() for part in protocol_header.split(",") if part.strip()]
            if len(parts) >= 2 and parts[0].lower() == "bearer":
                token = parts[1]
                selected_subprotocol = "bearer"

        if token is None:
            token = websocket.query_params.get("token")
        try:
            authenticate_websocket_token(token)
        except Exception:
            await websocket.close(code=1008)
            return
        await manager.connect(websocket, subprotocol=selected_subprotocol)
        try:
            while True:
                await websocket.receive_text()  # Bağlantıyı açık tut
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app
