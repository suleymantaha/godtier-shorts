import asyncio
import json
from pathlib import Path

import backend.config as config
from starlette.requests import Request

from backend.api.routes import editor
from backend.api.security import AuthContext
from backend.models.schemas import ClipTranscriptRecoveryRequest, ProjectTranscriptRecoveryRequest
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _build_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/api/clip-transcript/recover", "headers": []})


def _build_auth() -> AuthContext:
    return AuthContext(subject="owner-subject", roles={"editor", "producer"}, token_type="bearer")


def _owned_project_id(suffix: str) -> str:
    return build_owner_scoped_project_id("proj", "owner-subject", suffix)


async def _run_recovery(request: ClipTranscriptRecoveryRequest) -> dict:
    response = await editor.recover_clip_transcript(_build_request(), request, auth=_build_auth())
    if response.get("job_id") and response["job_id"] in editor.manager.jobs:
        await editor.manager.jobs[response["job_id"]]["task"]
    return response


def _build_project_transcript() -> list[dict]:
    return [
        {
            "text": "first",
            "start": 8.0,
            "end": 12.0,
            "speaker": "A",
            "words": [
                {"word": "first", "start": 8.0, "end": 9.0, "score": 0.9},
                {"word": "clip", "start": 9.0, "end": 10.5, "score": 0.9},
            ],
        },
        {
            "text": "second",
            "start": 12.5,
            "end": 17.0,
            "speaker": "A",
            "words": [
                {"word": "second", "start": 12.5, "end": 14.0, "score": 0.9},
                {"word": "line", "start": 14.0, "end": 15.5, "score": 0.9},
            ],
        },
    ]


def test_recover_clip_transcript_from_project_slice(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("1")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clip-recovery-test-secret")
    monkeypatch.setattr(editor, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    editor.manager.jobs.clear()

    (project_dir / "transcript.json").write_text(json.dumps(_build_project_transcript()), encoding="utf-8")
    (shorts_dir / "clip_1.mp4").write_bytes(b"video")
    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")
    (shorts_dir / "clip_1.json").write_text(json.dumps({
        "transcript": [],
        "viral_metadata": {"ui_title": "Keep me"},
        "render_metadata": {
            "clip_name": "clip_1.mp4",
            "end_time": 16.0,
            "project_id": project_id,
            "start_time": 9.0,
        },
    }), encoding="utf-8")

    response = asyncio.run(_run_recovery(ClipTranscriptRecoveryRequest(
        clip_name="clip_1.mp4",
        project_id=project_id,
        strategy="project_slice",
    )))

    saved_payload = json.loads((shorts_dir / "clip_1.json").read_text(encoding="utf-8"))
    assert response["status"] == "started"
    assert editor.manager.jobs[response["job_id"]]["status"] == "completed"
    assert saved_payload["viral_metadata"] == {"ui_title": "Keep me"}
    assert saved_payload["render_metadata"]["start_time"] == 9.0
    assert [segment["text"] for segment in saved_payload["transcript"]] == ["clip", "second line"]
    assert saved_payload["transcript"][0]["start"] == 0
    assert saved_payload["transcript"][0]["words"][0]["start"] == 0
    editor.manager.jobs.clear()


def test_recover_clip_transcript_prefers_raw_video_source(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("1")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clip-recovery-test-secret")
    monkeypatch.setattr(editor, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(editor, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    editor.manager.jobs.clear()

    (shorts_dir / "clip_1.mp4").write_bytes(b"video")
    (shorts_dir / "clip_1_raw.mp4").write_bytes(b"raw-video")
    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")
    (shorts_dir / "clip_1.json").write_text(json.dumps({
        "transcript": [],
        "viral_metadata": {"ui_title": "Keep me"},
        "render_metadata": {"clip_name": "clip_1.mp4", "project_id": project_id},
    }), encoding="utf-8")

    used_source: dict[str, str] = {}

    def _fake_extract_audio(video_path: Path, audio_path: Path) -> None:
        used_source["path"] = str(video_path)
        audio_path.write_bytes(b"wav")

    def _fake_run_transcription(audio_file: str, output_json: str | None = None, **_kwargs) -> str:
        assert audio_file.endswith(".wav")
        Path(output_json or "").write_text(json.dumps([
            {"text": "Recovered", "start": 0.0, "end": 1.0, "speaker": "A", "words": []},
        ]), encoding="utf-8")
        return str(output_json)

    monkeypatch.setattr(editor, "_extract_audio_from_video", _fake_extract_audio)
    monkeypatch.setattr(editor, "run_transcription", _fake_run_transcription)

    response = asyncio.run(_run_recovery(ClipTranscriptRecoveryRequest(
        clip_name="clip_1.mp4",
        project_id=project_id,
        strategy="transcribe_source",
    )))

    saved_payload = json.loads((shorts_dir / "clip_1.json").read_text(encoding="utf-8"))
    assert response["status"] == "started"
    assert editor.manager.jobs[response["job_id"]]["status"] == "completed"
    assert used_source["path"].endswith("clip_1_raw.mp4")
    assert saved_payload["transcript"][0]["text"] == "Recovered"
    assert saved_payload["viral_metadata"] == {"ui_title": "Keep me"}
    editor.manager.jobs.clear()


def test_recover_clip_transcript_auto_falls_back_to_source_when_project_slice_is_empty(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("1")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clip-recovery-test-secret")
    monkeypatch.setattr(editor, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(editor, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    editor.manager.jobs.clear()

    (project_dir / "transcript.json").write_text(json.dumps([]), encoding="utf-8")
    (shorts_dir / "clip_1.mp4").write_bytes(b"video")
    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")
    (shorts_dir / "clip_1.json").write_text(json.dumps({
        "transcript": [],
        "render_metadata": {
            "clip_name": "clip_1.mp4",
            "end_time": 5.0,
            "project_id": project_id,
            "start_time": 1.0,
        },
    }), encoding="utf-8")

    used_source: dict[str, str] = {}

    def _fake_extract_audio(video_path: Path, audio_path: Path) -> None:
        used_source["path"] = str(video_path)
        audio_path.write_bytes(b"wav")

    def _fake_run_transcription(audio_file: str, output_json: str | None = None, **_kwargs) -> str:
        Path(output_json or "").write_text(json.dumps([
            {"text": "Recovered fallback", "start": 0.0, "end": 1.0, "speaker": "A", "words": []},
        ]), encoding="utf-8")
        return str(output_json)

    monkeypatch.setattr(editor, "_extract_audio_from_video", _fake_extract_audio)
    monkeypatch.setattr(editor, "run_transcription", _fake_run_transcription)

    response = asyncio.run(_run_recovery(ClipTranscriptRecoveryRequest(
        clip_name="clip_1.mp4",
        project_id=project_id,
        strategy="auto",
    )))

    saved_payload = json.loads((shorts_dir / "clip_1.json").read_text(encoding="utf-8"))
    assert response["status"] == "started"
    assert editor.manager.jobs[response["job_id"]]["status"] == "completed"
    assert editor.manager.jobs[response["job_id"]]["recovery_strategy"] == "transcribe_source"
    assert used_source["path"].endswith("clip_1.mp4")
    assert saved_payload["transcript"][0]["text"] == "Recovered fallback"
    editor.manager.jobs.clear()


def test_recover_clip_transcript_dedupes_active_jobs(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("1")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clip-recovery-test-secret")
    editor.manager.jobs.clear()
    editor.manager.jobs["cliprecover_existing"] = {
        "clip_name": "clip_1.mp4",
        "created_at": 1,
        "job_id": "cliprecover_existing",
        "last_message": "Working...",
        "progress": 10,
        "project_id": project_id,
        "recovery_strategy": "project_slice",
        "status": "processing",
        "style": "TRANSCRIPT_RECOVERY",
        "url": "clip_1.mp4",
    }

    (project_dir / "transcript.json").write_text(json.dumps(_build_project_transcript()), encoding="utf-8")
    (shorts_dir / "clip_1.mp4").write_bytes(b"video")
    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")
    (shorts_dir / "clip_1.json").write_text(json.dumps({
        "transcript": [],
        "render_metadata": {
            "clip_name": "clip_1.mp4",
            "end_time": 16.0,
            "project_id": project_id,
            "start_time": 9.0,
        },
    }), encoding="utf-8")

    response = asyncio.run(editor.recover_clip_transcript(
        _build_request(),
        ClipTranscriptRecoveryRequest(
            clip_name="clip_1.mp4",
            project_id=project_id,
            strategy="auto",
        ),
        auth=_build_auth(),
    ))

    assert response == {"status": "started", "job_id": "cliprecover_existing"}
    editor.manager.jobs.clear()


def test_recover_project_transcript_reuses_existing_job(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("1")
    project_dir = config.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "master.mp4").write_bytes(b"video")

    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clip-recovery-test-secret")
    editor.manager.jobs.clear()
    editor.manager.jobs["projecttranscript_existing"] = {
        "created_at": 1,
        "job_id": "projecttranscript_existing",
        "last_message": "Working...",
        "progress": 20,
        "project_id": project_id,
        "status": "processing",
        "style": "PROJECT_TRANSCRIPT",
        "url": "",
    }
    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")

    response = asyncio.run(editor.recover_project_transcript(
        _build_request(),
        ProjectTranscriptRecoveryRequest(project_id=project_id),
        auth=_build_auth(),
    ))

    assert response == {"status": "started", "job_id": "projecttranscript_existing"}
    editor.manager.jobs.clear()
