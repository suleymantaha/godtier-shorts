"""Internal clip event port contracts for workflow modules."""

from __future__ import annotations

from typing import Protocol


class ClipEventPort(Protocol):
    def invalidate_clips_cache(self, *, reason: str) -> None:
        ...

    def resolve_clip_ready_job_id(
        self,
        *,
        subject: str | None,
        project_id: str,
        job_id: str | None,
    ) -> str | None:
        ...

    def broadcast_clip_ready(
        self,
        *,
        message: str,
        progress: int,
        job_id: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        ...


class NullClipEventPort:
    def invalidate_clips_cache(self, *, reason: str) -> None:
        return None

    def resolve_clip_ready_job_id(
        self,
        *,
        subject: str | None,
        project_id: str,
        job_id: str | None,
    ) -> str | None:
        return None

    def broadcast_clip_ready(
        self,
        *,
        message: str,
        progress: int,
        job_id: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        return None
