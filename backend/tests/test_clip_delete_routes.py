from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.config as config
from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import clips
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(clips.router)
    return app


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token:editor;producer-token:producer;viewer-token:viewer")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    return {
        "editor": {"Authorization": "Bearer editor-token"},
        "producer": {"Authorization": "Bearer producer-token"},
        "viewer": {"Authorization": "Bearer viewer-token"},
    }


def _static_subject(token: str) -> str:
    import hashlib

    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def test_delete_project_short_removes_managed_assets_and_preserves_project_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "1")
    project_dir = config.get_project_dir(project_id)
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    clip_path = shorts_dir / "clip_1.mp4"
    metadata_path = shorts_dir / "clip_1.json"
    raw_path = shorts_dir / "clip_1_raw.mp4"
    master_path = project_dir / "master.mp4"
    transcript_path = project_dir / "transcript.json"

    clip_path.write_bytes(b"video")
    metadata_path.write_text("{}", encoding="utf-8")
    raw_path.write_bytes(b"raw")
    master_path.write_bytes(b"master")
    transcript_path.write_text("[]", encoding="utf-8")

    invalidate_calls: list[str] = []
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "invalidate_clips_cache", lambda reason="unknown": invalidate_calls.append(reason))
    ensure_project_manifest(project_id, owner_subject=_static_subject("editor-token"), source="test")

    client = TestClient(_build_app())
    response = client.delete(f"/api/projects/{project_id}/shorts/clip_1.mp4", headers=auth_headers["editor"])

    assert response.status_code == 200
    assert response.json() == {
        "clip_name": "clip_1.mp4",
        "deleted": True,
        "project_id": project_id,
        "status": "deleted",
    }
    assert not clip_path.exists()
    assert not metadata_path.exists()
    assert not raw_path.exists()
    assert master_path.exists()
    assert transcript_path.exists()
    assert invalidate_calls == [f"clip_deleted:{project_id}/clip_1.mp4"]


def test_delete_project_short_handles_missing_optional_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("producer-token", "2")
    shorts_dir = config.get_project_path(project_id, "shorts")
    shorts_dir.mkdir(parents=True, exist_ok=True)
    clip_path = shorts_dir / "clip_2.mp4"
    clip_path.write_bytes(b"video")

    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    ensure_project_manifest(project_id, owner_subject=_static_subject("producer-token"), source="test")

    client = TestClient(_build_app())
    response = client.delete(f"/api/projects/{project_id}/shorts/clip_2.mp4", headers=auth_headers["producer"])

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert response.json()["deleted"] is True
    assert not clip_path.exists()


def test_delete_project_short_returns_not_found_without_invalidation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "3")
    shorts_dir = config.get_project_path(project_id, "shorts")
    shorts_dir.mkdir(parents=True, exist_ok=True)

    invalidate_calls: list[str] = []
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "invalidate_clips_cache", lambda reason="unknown": invalidate_calls.append(reason))
    ensure_project_manifest(project_id, owner_subject=_static_subject("editor-token"), source="test")

    client = TestClient(_build_app())
    response = client.delete(f"/api/projects/{project_id}/shorts/missing.mp4", headers=auth_headers["editor"])

    assert response.status_code == 200
    assert response.json() == {
        "clip_name": "missing.mp4",
        "deleted": False,
        "project_id": project_id,
        "status": "not_found",
    }
    assert invalidate_calls == []


def test_delete_project_short_requires_delete_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
):
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "4")
    shorts_dir = config.get_project_path(project_id, "shorts")
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (shorts_dir / "clip_4.mp4").write_bytes(b"video")

    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)

    client = TestClient(_build_app())
    response = client.delete(f"/api/projects/{project_id}/shorts/clip_4.mp4", headers=auth_headers["viewer"])

    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"]["code"] == "forbidden"
