from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

import backend.config as config
from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import clips, editor
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(clips.router)
    app.include_router(editor.router)
    return app


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def _write_owned_project(project_root: Path, project_id: str, *, owner_token: str, clip_name: str) -> None:
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "master.mp4").write_bytes(b"master")
    (project_dir / "transcript.json").write_text(json.dumps([]), encoding="utf-8")
    (shorts_dir / clip_name).write_bytes(b"video")
    (shorts_dir / clip_name.replace(".mp4", ".json")).write_text(
        json.dumps(
            {
                "transcript": [],
                "render_metadata": {
                    "clip_name": clip_name,
                    "project_id": project_id,
                    "start_time": 1.0,
                    "end_time": 2.0,
                },
            }
        ),
        encoding="utf-8",
    )
    ensure_project_manifest(project_id, owner_subject=_static_subject(owner_token), source="test")


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    monkeypatch.setenv(
        "API_BEARER_TOKENS",
        "token-a:editor,producer,viewer;token-b:editor,producer,viewer",
    )
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    return {
        "a": {"Authorization": "Bearer token-a"},
        "b": {"Authorization": "Bearer token-b"},
    }


def test_projects_and_clips_are_filtered_by_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)

    project_a = _owned_project_id("token-a", "a")
    project_b = _owned_project_id("token-b", "b")
    _write_owned_project(project_root, project_a, owner_token="token-a", clip_name="clip_a.mp4")
    _write_owned_project(project_root, project_b, owner_token="token-b", clip_name="clip_b.mp4")
    clips.invalidate_clips_cache("ownership_test")

    client = TestClient(_build_app())
    projects_response = client.get("/api/projects", headers=auth_headers["a"])
    clips_response = client.get("/api/clips", headers=auth_headers["a"])

    assert projects_response.status_code == 200
    assert [project["id"] for project in projects_response.json()["projects"]] == [project_a]
    assert clips_response.status_code == 200
    assert [clip["project"] for clip in clips_response.json()["clips"]] == [project_a]
    assert [clip["name"] for clip in clips_response.json()["clips"]] == ["clip_a.mp4"]


def test_foreign_project_assets_and_transcript_return_not_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(editor, "VIDEO_METADATA", tmp_path / "legacy.json")

    project_a = _owned_project_id("token-a", "a")
    project_b = _owned_project_id("token-b", "b")
    _write_owned_project(project_root, project_a, owner_token="token-a", clip_name="clip_a.mp4")
    _write_owned_project(project_root, project_b, owner_token="token-b", clip_name="clip_b.mp4")

    client = TestClient(_build_app())

    assert client.get(f"/api/projects/{project_b}/master", headers=auth_headers["a"]).status_code == 404
    assert client.get(f"/api/projects/{project_b}/shorts/clip_b.mp4", headers=auth_headers["a"]).status_code == 404
    assert client.get(
        "/api/clip-transcript/clip_b.mp4",
        headers=auth_headers["a"],
        params={"project_id": project_b},
    ).status_code == 404
    assert client.get("/api/transcript", headers=auth_headers["a"], params={"project_id": project_b}).status_code == 404
    assert client.post(
        "/api/transcript",
        headers=auth_headers["a"],
        params={"project_id": project_b},
        json=[],
    ).status_code == 404


def test_foreign_project_denial_is_security_logged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)

    project_b = _owned_project_id("token-b", "b")
    _write_owned_project(project_root, project_b, owner_token="token-b", clip_name="clip_b.mp4")

    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    try:
        client = TestClient(_build_app())
        response = client.get(f"/api/projects/{project_b}/master", headers=auth_headers["a"])
    finally:
        logger.remove(sink_id)

    assert response.status_code == 404
    assert any("ownership_denied" in message and project_b in message for message in messages)
