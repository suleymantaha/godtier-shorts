from __future__ import annotations

import json
from pathlib import Path

import backend.config as config
from starlette.requests import Request

from backend.api.routes import editor
from backend.api.security import AuthContext
from backend.models.schemas import BatchJobRequest
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _build_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/api/process-batch", "headers": []})


def _build_auth() -> AuthContext:
    return AuthContext(subject="owner-subject", roles={"editor", "producer"}, token_type="bearer")


def _owned_project_id(suffix: str) -> str:
    return build_owner_scoped_project_id("proj", "owner-subject", suffix)


class _FakeOrchestrator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def run_batch_manual_clips(self, **kwargs):
        self.kwargs["run_kwargs"] = kwargs
        project_id = kwargs["project_id"]
        project_dir = config.get_project_dir(project_id)
        shorts_dir = project_dir / "shorts"
        shorts_dir.mkdir(parents=True, exist_ok=True)
        clip_paths = [
            shorts_dir / "batch_1.mp4",
            shorts_dir / "batch_2.mp4",
        ]
        for clip_path in clip_paths:
            clip_path.write_bytes(b"video")
            clip_path.with_suffix(".json").write_text(json.dumps({"viral_metadata": {"ui_title": clip_path.stem}}), encoding="utf-8")
        return [str(path) for path in clip_paths]

    async def run_batch_manual_clips_async(self, **kwargs):
        return self.run_batch_manual_clips(**kwargs)

    def cleanup_gpu(self) -> None:
        return None


async def _run_batch(request: BatchJobRequest) -> dict:
    response = await editor.process_batch_clips(_build_request(), request, auth=_build_auth())
    job_id = response["job_id"]
    await editor.manager.jobs[job_id]["task"]
    return response


def test_process_batch_clips_persists_output_artifacts(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "editor-batch-visibility-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(editor, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(editor, "GodTierShortsCreator", _FakeOrchestrator)
    editor.manager.jobs.clear()

    project_id = _owned_project_id("batch")
    project_dir = config.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    ensure_project_manifest(project_id, owner_subject="owner-subject", source="test")
    (project_dir / "transcript.json").write_text(json.dumps([]), encoding="utf-8")

    response = __import__("asyncio").run(
        _run_batch(
            BatchJobRequest(
                start_time=0,
                end_time=90,
                num_clips=2,
                project_id=project_id,
                duration_min=30,
                duration_max=45,
            )
        )
    )

    job = editor.manager.jobs[response["job_id"]]
    assert response["status"] == "started"
    assert job["status"] == "completed"
    assert job["num_clips"] == 2
    assert job["clip_name"] == "batch_1.mp4"
    assert job["output_url"] == f"/api/projects/{project_id}/shorts/batch_1.mp4"
    assert len(job["output_paths"]) == 2

    editor.manager.jobs.clear()
