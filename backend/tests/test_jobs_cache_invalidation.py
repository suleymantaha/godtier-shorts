from __future__ import annotations

import asyncio

from backend.api.routes import jobs as jobs_routes
from backend.api.websocket import manager
from backend.models.schemas import JobRequest


class _FakeAnalyzer:
    engine: str = "local"


class _FakeOrchestrator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.analyzer = _FakeAnalyzer()
        self.cleanup_gpu_called = False

    async def run_pipeline_async(self, *_args, **_kwargs) -> None:
        return None

    def cleanup_gpu(self) -> None:
        self.cleanup_gpu_called = True


def test_run_gpu_job_invalidates_clip_cache_after_success(monkeypatch) -> None:
    manager.jobs.clear()
    manager.jobs["job-cache"] = {
        "job_id": "job-cache",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "subject": "static-subject",
    }

    created: dict[str, _FakeOrchestrator] = {}
    invalidate_calls: list[str] = []

    def _orchestrator_factory(*args, **kwargs) -> _FakeOrchestrator:
        orchestrator = _FakeOrchestrator(*args, **kwargs)
        created["instance"] = orchestrator
        return orchestrator

    monkeypatch.setattr(jobs_routes, "GodTierShortsCreator", _orchestrator_factory)
    monkeypatch.setattr(jobs_routes, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs_routes, "invalidate_clips_cache", lambda reason="unknown": invalidate_calls.append(reason))

    request = JobRequest(youtube_url="https://youtube.com/watch?v=test123")
    asyncio.run(jobs_routes.run_gpu_job("job-cache", request))

    job = manager.jobs["job-cache"]
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert invalidate_calls == ["job_success:job-cache"]
    assert created["instance"].cleanup_gpu_called is True

    manager.jobs.clear()
