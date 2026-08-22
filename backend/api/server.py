"""
backend/api/server.py
=======================
FastAPI uygulama fabrikası.
CORS, router kayıtları ve startup event burada.
"""
import asyncio
import os
import re
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import health
from backend.api.security import (
    authenticate_websocket_token,
    validate_auth_configuration,
)
from backend.api.websocket import manager, set_main_loop
from backend.config import (
    LOGS_DIR,
    MASTER_VIDEO,
    OUTPUTS_DIR,
    REQUEST_BODY_HARD_LIMIT_BYTES,
    WORKER_MODE,
    get_cors_origins,
)
from backend.runtime_validation import validate_runtime_configuration
from backend.services.social.crypto import validate_social_security_configuration
from backend.services.social.scheduler import get_social_scheduler
from backend.system_validation import validate_accelerator_support_configuration

# Loglama
logger.add(
    str(LOGS_DIR / "api_server_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")
PRODUCTION_API_CSP = (
    "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def _request_id(request: Request) -> str:
    for header_name in ("x-request-id", "x-trace-id"):
        candidate = request.headers.get(header_name, "").strip()
        if REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
    return str(uuid4())


def _apply_response_security_headers(response, *, request_id: str, production: bool) -> None:
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Trace-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    if production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = PRODUCTION_API_CSP


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü yönetimi."""
    # Startup
    app.state.ready = False
    validate_runtime_configuration()
    validate_accelerator_support_configuration()
    validate_auth_configuration()
    validate_social_security_configuration()
    set_main_loop(asyncio.get_running_loop())
    logger.info("✅ Ana asyncio event loop kaydedildi.")
    
    # Job cleanup görevini başlat
    await manager.start_cleanup_task()
    logger.info("🧹 Job cleanup görevi etkinleştirildi.")

    social_scheduler = get_social_scheduler()
    await social_scheduler.start()
    logger.info("📣 Social publish scheduler etkinleştirildi.")
    
    # outputs klasörüne master_video sembolik bağı oluştur
    link_path = OUTPUTS_DIR / "master_video.mp4"
    if MASTER_VIDEO.exists() and not (link_path.exists() or link_path.is_symlink()):
        try:
            link_path.symlink_to(MASTER_VIDEO.resolve())
            logger.info("🔗 master_video.mp4 sembolik bağı oluşturuldu.")
        except Exception as e:
            logger.error(f"🔗 Sembolik bağ oluşturulamadı: {e}")
    
    logger.info("🚀 Uygulama başlatıldı.")

    app.state.ready = True
    yield  # App runs here

    # Shutdown
    app.state.ready = False
    await social_scheduler.stop()
    await manager.stop_cleanup_task()
    logger.info("👋 Uygulama kapatılıyor...")


def create_app() -> FastAPI:
    """FastAPI uygulamasını oluşturur ve yapılandırır."""
    production = os.getenv("APP_ENV", "development").strip().lower() == "production"
    app = FastAPI(
        title="God-Tier Shorts API",
        version="2.0.0",
        description="AI destekli viral short video üretimi",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.state.ready = False

    # Register CORS first so request/security middleware wraps preflight responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Trace-ID",
        ],
    )

    @app.middleware("http")
    async def attach_trace_id(request: Request, call_next):
        request_id = _request_id(request)
        request.state.request_id = request_id
        request.state.trace_id = request_id
        response = None
        guarded_upload_paths = {"/api/upload", "/api/manual-cut-upload"}
        if request.method == "POST" and request.url.path in guarded_upload_paths:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > REQUEST_BODY_HARD_LIMIT_BYTES:
                        response = JSONResponse(
                            status_code=413,
                            content={
                                "code": "REQUEST_TOO_LARGE",
                                "message": "İstek gövdesi izin verilen sınırı aşıyor.",
                                "details": {
                                    "limit_bytes": REQUEST_BODY_HARD_LIMIT_BYTES,
                                },
                                "trace_id": request_id,
                            },
                        )
                except ValueError:
                    pass

        with logger.contextualize(request_id=request_id):
            if response is None:
                response = await call_next(request)
            logger.info(
                "request_completed request_id={} method={} path={} status={}",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
            )
        _apply_response_security_headers(response, request_id=request_id, production=production)
        return response

    register_exception_handlers(app)

    # --- Control-plane router'larını kaydet ---
    from backend.api.routes import account, admin_metrics, auth, billing, clerk, preview, security_gate, social, settings, uploads, webhooks

    app.include_router(social.router)
    app.include_router(settings.router)
    app.include_router(account.router)
    app.include_router(auth.router)
    app.include_router(billing.router)
    app.include_router(webhooks.router)
    app.include_router(clerk.router)
    app.include_router(preview.router)
    app.include_router(security_gate.router)
    app.include_router(uploads.router)
    app.include_router(health.router)
    app.include_router(admin_metrics.router)

    if WORKER_MODE == "api":
        from backend.api.routes import production_jobs

        app.include_router(production_jobs.router)

    # Mevcut lokal GPU akislarini yalniz local modda yukle. Production API
    # control-plane, queue/worker siniri kurulmadan GPU runtime import etmez.
    if WORKER_MODE == "local":
        from backend.api.routes import clips, editor, jobs

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
            auth = authenticate_websocket_token(token, headers=websocket.headers)
        except Exception:
            await websocket.close(code=1008)
            return
        await manager.connect(websocket, subject=auth.subject, subprotocol=selected_subprotocol)
        try:
            while True:
                await websocket.receive_text()  # Bağlantıyı açık tut
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()

