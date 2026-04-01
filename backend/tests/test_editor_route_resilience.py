from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path

import backend.config as config
from fastapi import UploadFile
from starlette.requests import Request

from backend.api.routes import clips, editor
from backend.api.security import AuthContext
from backend.models.schemas import ManualJobRequest
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _build_request(path: str) -> Request:
    return Request({"type": "http", "method": "POST", "path": path, "headers": []})


def _build_auth() -> AuthContext:
    return AuthContext(subject="owner-subject", roles={"editor", "producer"}, token_type="bearer")


def _owned_project_id(suffix: str) -> str:
    return build_owner_scoped_project_id("proj", "owner-subject", suffix)


def test_process_manual_clip_marks_job_error_on_unexpected_exception(monkeypatch) -> None:
    class _FailingOrchestrator:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def run_manual_clip_async(self, **kwargs):
            raise TypeError("float() argument must be a string or a real number, not 'NoneType'")

        def cleanup_gpu(self) -> None:
            return None

    async def _run() -> dict:
        response = await editor.process_manual_clip(
            _build_request("/api/process-manual"),
            ManualJobRequest(
                start_time=0,
                end_time=10,
                transcript=[
                    {
                        "text": "hello world",
                        "start": 0,
                        "end": 10,
                        "words": [
                            {"word": "hello", "start": 0, "end": 5, "score": None},
                            {"word": "world", "start": 5, "end": 10, "score": 0.9},
                        ],
                    }
                ],
            ),
            auth=_build_auth(),
        )
        await editor.manager.jobs[response["job_id"]]["task"]
        return response

    monkeypatch.setattr(editor, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(clips, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(editor, "GodTierShortsCreator", _FailingOrchestrator)
    editor.manager.jobs.clear()

    response = asyncio.run(_run())

    job = editor.manager.jobs[response["job_id"]]
    assert response["status"] == "started"
    assert job["status"] == "error"
    assert "HATA:" in job["last_message"]
    assert "Manuel render başarısız" in job["last_message"]

    editor.manager.jobs.clear()


def test_manual_cut_upload_single_clip_uses_transcript_and_defers_output_fields(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "projects"
    project_id = _owned_project_id("manual-single")
    transcript_payload = [
        {
            "text": "hello world",
            "start": 0.0,
            "end": 1.5,
            "words": [
                {"word": "hello", "start": 0.0, "end": 0.7, "score": None},
                {"word": "world", "start": 0.7, "end": 1.5, "score": 0.8},
            ],
        }
    ]

    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "editor-route-resilience-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)

    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")
    project = config.ProjectPaths(project_id)
    project.root.mkdir(parents=True, exist_ok=True)
    project.outputs.mkdir(parents=True, exist_ok=True)
    project.master_video.write_bytes(b"video")
    project.transcript.write_text(json.dumps(transcript_payload), encoding="utf-8")

    class _FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def run_manual_clip_async(self, **kwargs):
            assert kwargs["transcript_data"] == transcript_payload
            output_path = project.outputs / str(kwargs["output_name"])
            output_path.write_bytes(b"clip")
            return str(output_path)

        def cleanup_gpu(self) -> None:
            return None

    async def _run() -> dict:
        response = await editor.manual_cut_upload(
            _build_request("/api/manual-cut-upload"),
            file=UploadFile(filename="sample.mp4", file=BytesIO(b"video")),
            start_time=0,
            end_time=1.5,
            style_name="HORMOZI",
            animation_type="default",
            skip_subtitles=False,
            num_clips=1,
            cut_points=None,
            cut_as_short=True,
            layout="auto",
            duration_min=None,
            duration_max=None,
            auth=_build_auth(),
        )
        assert response["clip_name"] is None
        assert response["output_url"] is None
        await editor.manager.jobs[response["job_id"]]["task"]
        return response

    monkeypatch.setattr(editor, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(clips, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(editor, "GodTierShortsCreator", _FakeOrchestrator)
    monkeypatch.setattr(editor, "prepare_uploaded_project", lambda file, owner_subject=None: (project, project_id, False))
    editor.manager.jobs.clear()

    response = asyncio.run(_run())

    job = editor.manager.jobs[response["job_id"]]
    assert response["status"] == "started"
    assert job["status"] == "completed"
    assert job["clip_name"] == f"manual_{response['job_id']}.mp4"
    assert job["output_url"] == f"/api/projects/{project_id}/shorts/manual_{response['job_id']}.mp4"
    assert Path(job["output_path"]).exists()

    editor.manager.jobs.clear()
