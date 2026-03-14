import asyncio
import json
from pathlib import Path

from backend.api.routes import clips, editor


def _clip_transcript_response(clip_name: str, project_id: str | None = None) -> dict:
    return asyncio.run(clips.get_clip_transcript(clip_name=clip_name, project_id=project_id, _=None))


def test_get_clip_transcript_includes_recovery_capabilities(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    project_dir = project_root / "proj_1"
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

    (project_dir / "transcript.json").write_text(json.dumps([]), encoding="utf-8")
    (shorts_dir / "clip_1.mp4").write_bytes(b"video")
    (shorts_dir / "clip_1_raw.mp4").write_bytes(b"raw-video")
    (shorts_dir / "clip_1.json").write_text(json.dumps({
        "transcript": [],
        "viral_metadata": {"ui_title": "Title"},
        "render_metadata": {
            "clip_name": "clip_1.mp4",
            "end_time": 18.0,
            "project_id": "proj_1",
            "start_time": 10.0,
        },
    }), encoding="utf-8")

    response = _clip_transcript_response("clip_1.mp4", "proj_1")

    assert response["transcript"] == []
    assert response["viral_metadata"] == {"ui_title": "Title"}
    assert response["render_metadata"]["start_time"] == 10.0
    assert response["capabilities"] == {
        "can_recover_from_project": True,
        "can_transcribe_source": True,
        "has_clip_metadata": True,
        "has_clip_transcript": False,
        "has_raw_backup": True,
        "project_has_transcript": True,
        "resolved_project_id": "proj_1",
    }
    assert response["transcript_status"] == "needs_recovery"
    assert response["recommended_strategy"] == "project_slice"
    assert response["active_job_id"] is None
    assert response["last_error"] is None


def test_get_clip_transcript_reports_source_transcription_only_when_metadata_is_missing(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    project_dir = project_root / "proj_2"
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

    (shorts_dir / "clip_2.mp4").write_bytes(b"video")

    response = _clip_transcript_response("clip_2.mp4", "proj_2")

    assert response["transcript"] == []
    assert response["render_metadata"]["clip_name"] == "clip_2.mp4"
    assert response["capabilities"] == {
        "can_recover_from_project": False,
        "can_transcribe_source": True,
        "has_clip_metadata": False,
        "has_clip_transcript": False,
        "has_raw_backup": False,
        "project_has_transcript": False,
        "resolved_project_id": "proj_2",
    }
    assert response["transcript_status"] == "needs_recovery"
    assert response["recommended_strategy"] == "transcribe_source"
    assert response["active_job_id"] is None
    assert response["last_error"] is None


def test_get_clip_transcript_reports_project_pending_status(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    project_dir = project_root / "proj_3"
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)
    clips.manager.jobs.clear()
    clips.manager.jobs["upload_1"] = {
        "created_at": 1,
        "job_id": "upload_1",
        "last_message": "Transkripsiyon başladı...",
        "progress": 20,
        "project_id": "proj_3",
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
            "project_id": "proj_3",
            "start_time": 10.0,
        },
    }), encoding="utf-8")

    response = _clip_transcript_response("clip_3.mp4", "proj_3")

    assert response["transcript_status"] == "project_pending"
    assert response["recommended_strategy"] == "project_slice"
    assert response["active_job_id"] == "upload_1"
    clips.manager.jobs.clear()


def test_get_project_transcript_reports_pending_and_failed_states(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    pending_dir = project_root / "proj_pending"
    failed_dir = project_root / "proj_failed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)
    editor.manager.jobs.clear()
    editor.manager.jobs["upload_pending"] = {
        "created_at": 1,
        "job_id": "upload_pending",
        "last_message": "Transkripsiyon başladı...",
        "progress": 25,
        "project_id": "proj_pending",
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
        "project_id": "proj_failed",
        "status": "error",
        "style": "PROJECT_TRANSCRIPT",
        "url": "",
    }

    pending_response = asyncio.run(editor.get_transcript(project_id="proj_pending", _=None))
    failed_response = asyncio.run(editor.get_transcript(project_id="proj_failed", _=None))

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
