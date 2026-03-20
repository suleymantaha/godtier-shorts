from __future__ import annotations

from backend.api.websocket import manager
from backend.core.workflow_helpers import publish_clip_ready_event


def test_publish_clip_ready_event_prefers_explicit_job_id(monkeypatch) -> None:
    captured: list[tuple[dict, str | None, dict | None]] = []

    manager.jobs.clear()
    manager.jobs["upload_older"] = {
        "job_id": "upload_older",
        "status": "processing",
        "created_at": 10.0,
        "project_id": "proj_1",
        "subject": "subject-a",
    }
    manager.jobs["manualcut_target"] = {
        "job_id": "manualcut_target",
        "status": "processing",
        "created_at": 5.0,
        "project_id": "proj_1",
        "subject": "subject-a",
    }

    monkeypatch.setattr(
        "backend.api.websocket.thread_safe_broadcast",
        lambda status, job_id=None, *, extra=None: captured.append((status, job_id, extra)),
    )
    monkeypatch.setattr(
        "backend.api.routes.clips.invalidate_clips_cache",
        lambda reason="unknown": None,
    )

    published = publish_clip_ready_event(
        subject="subject-a",
        job_id="manualcut_target",
        project_id="proj_1",
        clip_name="clip_1.mp4",
        message="Klip hazir.",
        progress=95,
        ui_title="Hook",
    )

    assert published is True
    assert len(captured) == 1
    status, job_id, extra = captured[0]
    assert job_id == "manualcut_target"
    assert status["message"] == "Klip hazir."
    assert extra == {
        "event_type": "clip_ready",
        "project_id": "proj_1",
        "clip_name": "clip_1.mp4",
        "ui_title": "Hook",
    }

    manager.jobs.clear()

