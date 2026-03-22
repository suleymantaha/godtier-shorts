"""API-backed adapters for workflow clip events."""

from __future__ import annotations

from backend.core.clip_events import ClipEventPort


class ApiClipEventPort(ClipEventPort):
    def invalidate_clips_cache(self, *, reason: str) -> None:
        from backend.api.routes.clips import invalidate_clips_cache

        invalidate_clips_cache(reason=reason)

    def resolve_clip_ready_job_id(
        self,
        *,
        subject: str | None,
        project_id: str,
        job_id: str | None,
    ) -> str | None:
        from backend.api.websocket import manager

        resolved_job_id = job_id if job_id in manager.jobs else None
        if resolved_job_id is None and subject:
            active_jobs = [
                (float(job.get("created_at") or 0.0), candidate_job_id)
                for candidate_job_id, job in manager.jobs.items()
                if str(job.get("subject") or "") == subject
                and str(job.get("status") or "") in {"queued", "processing"}
            ]
            if active_jobs:
                resolved_job_id = max(active_jobs)[1]

        if resolved_job_id is None:
            active_jobs = [
                (float(job.get("created_at") or 0.0), candidate_job_id)
                for candidate_job_id, job in manager.jobs.items()
                if str(job.get("project_id") or "") == project_id
                and str(job.get("status") or "") in {"queued", "processing"}
            ]
            if active_jobs:
                resolved_job_id = max(active_jobs)[1]

        return resolved_job_id

    def broadcast_clip_ready(
        self,
        *,
        message: str,
        progress: int,
        job_id: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        from backend.api.websocket import thread_safe_broadcast

        thread_safe_broadcast(
            {"message": message, "progress": progress, "status": "processing"},
            job_id,
            extra=extra,
        )


def build_api_clip_event_port() -> ClipEventPort:
    return ApiClipEventPort()
