"""FastAPI global exception handler ve standart hata cevabı."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from backend.core.exceptions import AppError


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
    log_fn(f"trace_id={trace_id} code={exc.code} message={exc.message} details={exc.details}")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=trace_id,
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = _trace_id(request)
    logger.warning(f"trace_id={trace_id} code=REQUEST_VALIDATION_ERROR details={exc.errors()}")
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            code="REQUEST_VALIDATION_ERROR",
            message="Request validation failed",
            details=exc.errors(),
            trace_id=trace_id,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = _trace_id(request)
    logger.error(f"trace_id={trace_id} code=INTERNAL_SERVER_ERROR message={exc}")
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message="Beklenmeyen bir hata oluştu.",
            details=str(exc),
            trace_id=trace_id,
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
