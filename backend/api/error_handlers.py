"""FastAPI global exception handler ve standart hata cevabı."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from backend.core.exceptions import AppError
from backend.core.log_sanitizer import sanitize_log_value


def _trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    if trace_id:
        return str(trace_id)
    incoming = request.headers.get("x-trace-id") or request.headers.get("x-request-id")
    return incoming or str(uuid4())


def _error_payload(*, code: str, message: str, details: object, trace_id: str) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "details": details,
        "trace_id": trace_id,
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    trace_id = _trace_id(request)
    log_fn = logger.error if exc.log_level == "error" else logger.warning
    sanitized_message = sanitize_log_value(exc.message)
    sanitized_details = sanitize_log_value(exc.details)
    log_fn(f"trace_id={trace_id} code={exc.code} message={sanitized_message} details={sanitized_details}")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=exc.code,
            message=sanitized_message,
            details=sanitized_details,
            trace_id=trace_id,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    trace_id = _trace_id(request)
    level = "warning" if 400 <= exc.status_code < 500 else "error"
    log_fn = logger.error if level == "error" else logger.warning
    log_fn(f"trace_id={trace_id} code=HTTP_{exc.status_code} detail={exc.detail}")

    if exc.status_code in (401, 403):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            payload = exc.detail
        else:
            payload = {
                "error": {
                    "code": "unauthorized" if exc.status_code == 401 else "forbidden",
                    "message": str(exc.detail),
                }
            }
        return JSONResponse(status_code=exc.status_code, content={"detail": payload})

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=f"HTTP_{exc.status_code}",
            message="HTTP error",
            details=exc.detail,
            trace_id=trace_id,
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = _trace_id(request)
    logger.warning(f"trace_id={trace_id} code=REQUEST_VALIDATION_ERROR details={sanitize_log_value(exc.errors())}")
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            code="REQUEST_VALIDATION_ERROR",
            message="Request validation failed",
            details=sanitize_log_value(exc.errors()),
            trace_id=trace_id,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = _trace_id(request)
    sanitized_message = sanitize_log_value(str(exc))
    logger.error(f"trace_id={trace_id} code=INTERNAL_SERVER_ERROR message={sanitized_message}")
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message="Beklenmeyen bir hata oluştu.",
            details=None,
            trace_id=trace_id,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
