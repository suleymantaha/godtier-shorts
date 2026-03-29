"""Uygulama genelinde kullanılan domain-spesifik exception sınıfları."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """HTTP katmanında standart hata sözleşmesine çevrilen temel hata."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: Any | None = None,
        status_code: int = 400,
        log_level: str = "warning",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code
        self.log_level = log_level


class InvalidInputError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="INVALID_INPUT",
            message=message,
            details=details,
            status_code=400,
            log_level="warning",
        )


class NotFoundError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=message,
            details=details,
            status_code=404,
            log_level="warning",
        )


class MediaSubprocessError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="MEDIA_SUBPROCESS_ERROR",
            message=message,
            details=details,
            status_code=502,
            log_level="error",
        )


class FileOperationError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="FILE_OPERATION_ERROR",
            message=message,
            details=details,
            status_code=500,
            log_level="error",
        )


class TranscriptionError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="TRANSCRIPTION_ERROR",
            message=message,
            details=details,
            status_code=502,
            log_level="error",
        )


class JobExecutionError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="JOB_EXECUTION_ERROR",
            message=message,
            details=details,
            status_code=500,
            log_level="error",
        )


class RateLimitError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(
            code="RATE_LIMITED",
            message=message,
            details=details,
            status_code=429,
            log_level="warning",
        )


class RenderReviewRequiredError(AppError):
    def __init__(
        self,
        message: str = "Render sonucu manuel inceleme gerektiriyor.",
        *,
        details: Any | None = None,
        review_items: list[dict[str, Any]] | None = None,
        output_paths: list[str] | None = None,
        project_id: str | None = None,
        num_clips: int | None = None,
    ) -> None:
        super().__init__(
            code="RENDER_REVIEW_REQUIRED",
            message=message,
            details=details,
            status_code=409,
            log_level="warning",
        )
        self.review_items = review_items or []
        self.output_paths = output_paths or []
        self.project_id = project_id
        self.num_clips = num_clips
