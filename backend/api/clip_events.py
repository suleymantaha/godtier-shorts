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

        if job_id is not None:
            job = manager.jobs.get(job_id)
            if job is None:
                return None
            if subject and str(job.get("subject") or "") != subject:
                return None
            known_project = str(job.get("project_id") or "")
            if known_project and known_project != project_id:
                return None
            return job_id

        # A missing explicit ID is common in older workflows. Only infer a
        # target when the active project/subject pair is unambiguous.
        active_jobs = [
            candidate_job_id
            for candidate_job_id, job in manager.jobs.items()
            if str(job.get("project_id") or "") == project_id
            and (not subject or str(job.get("subject") or "") == subject)
            and str(job.get("status") or "") in {"queued", "processing"}
        ]
        return active_jobs[0] if len(active_jobs) == 1 else None

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
