"""Unauthenticated process health endpoints for runtime orchestration."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
async def ready(request: Request):
    if not getattr(request.app.state, "ready", False):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    checker = getattr(request.app.state, "readiness_checker", None)
    if checker is None:
        return {"status": "ready"}
    report = await checker.check()
    content = {"status": report.status, "dependencies": report.dependencies}
    if report.status != "ready":
        return JSONResponse(status_code=503, content=content)
    return content
