import asyncio
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.config as config
from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import clips, editor
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _clip_transcript_response(clip_name: str, project_id: str | None = None) -> dict:
    return clips.build_clip_transcript_response(clip_name, project_id)


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(editor.router)
    return app


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token:editor")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    return {"Authorization": "Bearer editor-token"}


def _static_subject(token: str) -> str:
    import hashlib

    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def test_get_clip_transcript_includes_recovery_capabilities(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "1")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    ensure_project_manifest(project_id, owner_subject=_static_subject("editor-token"), source="test")

    (project_dir / "transcript.json").write_text(json.dumps([]), encoding="utf-8")
    (shorts_dir / "clip_1.mp4").write_bytes(b"video")
    (shorts_dir / "clip_1_raw.mp4").write_bytes(b"raw-video")
    (shorts_dir / "clip_1.json").write_text(json.dumps({
        "transcript": [],
        "viral_metadata": {"ui_title": "Title"},
        "render_metadata": {
            "clip_name": "clip_1.mp4",
            "debug_artifacts": {
                "status": "partial",
                "timing_report": "debug/clip_1/timing_report.json",
            },
            "end_time": 18.0,
            "project_id": project_id,
            "start_time": 10.0,
        },
    }), encoding="utf-8")

    response = _clip_transcript_response("clip_1.mp4", project_id)

    assert response["transcript"] == []
    assert response["viral_metadata"] == {"ui_title": "Title"}
    assert response["render_metadata"]["start_time"] == 10.0
    assert response["render_metadata"]["debug_artifacts"] == {
        "status": "partial",
        "timing_report": "debug/clip_1/timing_report.json",
    }
    assert response["capabilities"] == {
        "can_recover_from_project": True,
        "can_transcribe_source": True,
        "has_clip_metadata": True,
        "has_clip_transcript": False,
        "has_raw_backup": True,
        "project_has_transcript": True,
        "resolved_project_id": project_id,
    }
    assert response["transcript_status"] == "needs_recovery"
    assert response["recommended_strategy"] == "project_slice"
    assert response["active_job_id"] is None
    assert response["last_error"] is None


def test_get_clip_transcript_reports_source_transcription_only_when_metadata_is_missing(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "2")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    ensure_project_manifest(project_id, owner_subject=_static_subject("editor-token"), source="test")

    (shorts_dir / "clip_2.mp4").write_bytes(b"video")

    response = _clip_transcript_response("clip_2.mp4", project_id)

    assert response["transcript"] == []
    assert response["render_metadata"]["clip_name"] == "clip_2.mp4"
    assert "debug_artifacts" not in response["render_metadata"]
    assert response["capabilities"] == {
        "can_recover_from_project": False,
        "can_transcribe_source": True,
        "has_clip_metadata": False,
        "has_clip_transcript": False,
        "has_raw_backup": False,
        "project_has_transcript": False,
        "resolved_project_id": project_id,
    }
    assert response["transcript_status"] == "needs_recovery"
    assert response["recommended_strategy"] == "transcribe_source"
    assert response["active_job_id"] is None
    assert response["last_error"] is None


def test_get_clip_transcript_reports_project_pending_status(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "3")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    ensure_project_manifest(project_id, owner_subject=_static_subject("editor-token"), source="test")
    clips.manager.jobs.clear()
    clips.manager.jobs["upload_1"] = {
        "created_at": 1,
        "job_id": "upload_1",
        "last_message": "Transkripsiyon başladı...",
        "progress": 20,
        "project_id": project_id,
        "status": "processing",
        "style": "UPLOAD",
        "url": "",
    }

    (shorts_dir / "clip_3.mp4").write_bytes(b"video")
    (shorts_dir / "clip_3.json").write_text(json.dumps({
        "transcript": [],
        "render_metadata": {
            "clip_name": "clip_3.mp4",
            "end_time": 18.0,
            "project_id": project_id,
            "start_time": 10.0,
        },
    }), encoding="utf-8")

    response = _clip_transcript_response("clip_3.mp4", project_id)

    assert response["transcript_status"] == "project_pending"
    assert response["recommended_strategy"] == "project_slice"
    assert response["active_job_id"] == "upload_1"
    clips.manager.jobs.clear()


def test_get_project_transcript_reports_pending_and_failed_states(monkeypatch, tmp_path: Path, auth_headers: dict[str, str]):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    pending_project_id = _owned_project_id("editor-token", "pending")
    failed_project_id = _owned_project_id("editor-token", "failed")
    pending_dir = config.get_project_dir(pending_project_id)
    failed_dir = config.get_project_dir(failed_project_id)
    pending_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    ensure_project_manifest(pending_project_id, owner_subject=_static_subject("editor-token"), source="test")
    ensure_project_manifest(failed_project_id, owner_subject=_static_subject("editor-token"), source="test")
    editor.manager.jobs.clear()
    editor.manager.jobs["upload_pending"] = {
        "created_at": 1,
        "job_id": "upload_pending",
        "last_message": "Transkripsiyon başladı...",
        "progress": 25,
        "project_id": pending_project_id,
        "status": "processing",
        "style": "UPLOAD",
        "url": "",
    }
    editor.manager.jobs["projecttranscript_failed"] = {
        "created_at": 2,
        "error": "GPU unavailable",
        "job_id": "projecttranscript_failed",
        "last_message": "HATA: GPU unavailable",
        "progress": 0,
        "project_id": failed_project_id,
        "status": "error",
        "style": "PROJECT_TRANSCRIPT",
        "url": "",
    }

    client = TestClient(_build_app())
    pending_response = client.get("/api/transcript", headers=auth_headers, params={"project_id": pending_project_id}).json()
    failed_response = client.get("/api/transcript", headers=auth_headers, params={"project_id": failed_project_id}).json()

    assert pending_response == {
        "active_job_id": "upload_pending",
        "last_error": None,
        "transcript": [],
        "transcript_status": "pending",
    }
    assert failed_response == {
        "active_job_id": None,
        "last_error": "GPU unavailable",
        "transcript": [],
        "transcript_status": "failed",
    }
    editor.manager.jobs.clear()
