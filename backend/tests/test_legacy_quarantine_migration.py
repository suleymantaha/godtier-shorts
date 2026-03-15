from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.config as config
from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import clips
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest, read_project_manifest
from scripts.quarantine_legacy_projects import main as quarantine_legacy_projects_main


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(clips.router)
    return app


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def _write_project(
    project_root: Path,
    project_id: str,
    *,
    clip_name: str,
    owner_token: str | None = None,
) -> None:
    project_dir = config.get_project_dir(project_id) if owner_token is not None else project_root / project_id
    shorts_dir = project_dir / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "master.mp4").write_bytes(b"master")
    (shorts_dir / clip_name).write_bytes(b"clip")
    (shorts_dir / clip_name.replace(".mp4", ".json")).write_text(
        json.dumps({"render_metadata": {"clip_name": clip_name, "project_id": project_id}}),
        encoding="utf-8",
    )
    if owner_token is not None:
        ensure_project_manifest(project_id, owner_subject=_static_subject(owner_token), source="migration_test")


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("API_BEARER_TOKENS", "token-a:viewer")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "migration-test-secret")
    return {"Authorization": "Bearer token-a"}


def test_quarantine_legacy_projects_script_marks_legacy_dirs_and_hides_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)

    owned_project_id = _owned_project_id("token-a", "owned")
    _write_project(project_root, owned_project_id, clip_name="owned.mp4", owner_token="token-a")
    _write_project(project_root, "proj_legacy", clip_name="legacy.mp4")
    clips.invalidate_clips_cache("legacy_migration_setup")

    quarantined = quarantine_legacy_projects_main()
    output = capsys.readouterr().out

    assert quarantined == ["proj_legacy"]
    assert "proj_legacy" in output

    manifest = read_project_manifest("proj_legacy")
    assert manifest is not None
    assert manifest.status == "quarantined"

    client = TestClient(_build_app())

    projects_response = client.get("/api/projects", headers=auth_headers)
    clips_response = client.get("/api/clips", headers=auth_headers)
    legacy_master_response = client.get("/api/projects/proj_legacy/master", headers=auth_headers)

    assert projects_response.status_code == 200
    assert [project["id"] for project in projects_response.json()["projects"]] == [owned_project_id]
    assert clips_response.status_code == 200
    assert [clip["project"] for clip in clips_response.json()["clips"]] == [owned_project_id]
    assert legacy_master_response.status_code == 404
