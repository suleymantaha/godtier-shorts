from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.config as config
from backend.api import security
from backend.api.routes import auth as auth_routes
from backend.api.websocket import manager
from backend.services.job_state import JobStateRepository
from backend.services.ownership import (
    build_owner_scoped_project_id,
    build_subject_hash,
    ensure_project_manifest,
    read_project_manifest,
)


def _create_project(project_id: str) -> None:
    project_root = config.get_project_path(project_id)
    shorts_dir = project_root / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (shorts_dir / "clip.mp4").write_bytes(b"video")
    (shorts_dir / "clip.json").write_text(
        json.dumps({"render_metadata": {"project_id": project_id}}, ensure_ascii=False),
        encoding="utf-8",
    )


def _build_client(subject: str, roles: set[str]) -> TestClient:
    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[security.authenticate_request] = lambda: security.AuthContext(
        subject=subject,
        roles=roles,
        token_type="jwt",
        auth_mode="clerk_jwt",
    )
    return TestClient(app)


def test_ownership_diagnostics_lists_projects_owned_by_other_subjects(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-recovery-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(manager, "jobs", JobStateRepository(tmp_path / "jobs.json"))

    current_subject = "clerk-user-1"
    foreign_project = build_owner_scoped_project_id("yt", "legacy-subject", "video123")
    _create_project(foreign_project)
    ensure_project_manifest(foreign_project, owner_subject="legacy-subject", source="youtube")

    owned_project = build_owner_scoped_project_id("yt", current_subject, "video999")
    _create_project(owned_project)
    ensure_project_manifest(owned_project, owner_subject=current_subject, source="youtube")

    client = _build_client(current_subject, {"viewer"})

    response = client.get("/api/auth/ownership-diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["auth_mode"] == "clerk_jwt"
    assert body["current_subject_hash"] == build_subject_hash(current_subject)
    assert body["visible_project_count"] == 1
    assert body["reclaimable_projects"] == [
        {
            "clip_count": 1,
            "created_at": body["reclaimable_projects"][0]["created_at"],
            "latest_clip_name": "clip.mp4",
            "owner_subject_hash": build_subject_hash("legacy-subject"),
            "project_id": foreign_project,
            "source": "youtube",
            "status": "active",
        }
    ]


def test_claim_project_ownership_moves_project_and_updates_job_references(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-recovery-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(manager, "jobs", JobStateRepository(tmp_path / "jobs.json"))

    current_subject = "clerk-user-1"
    old_project_id = build_owner_scoped_project_id("yt", "legacy-subject", "video123")
    _create_project(old_project_id)
    ensure_project_manifest(old_project_id, owner_subject="legacy-subject", source="youtube")
    old_output_url = f"/api/projects/{old_project_id}/shorts/clip.mp4"
    manager.jobs["completed-job"] = {
        "job_id": "completed-job",
        "project_id": old_project_id,
        "status": "completed",
        "output_url": old_output_url,
    }

    client = _build_client(current_subject, {"viewer"})

    response = client.post("/api/auth/claim-project-ownership", json={"project_id": old_project_id})

    assert response.status_code == 200
    body = response.json()
    new_project_id = body["new_project_id"]
    assert body["status"] == "claimed"
    assert body["old_project_id"] == old_project_id
    assert body["current_subject_hash"] == build_subject_hash(current_subject)
    assert not config.get_project_path(old_project_id).exists()
    assert config.get_project_path(new_project_id).exists()
    manifest = read_project_manifest(new_project_id)
    assert manifest is not None
    assert manifest.owner_subject_hash == build_subject_hash(current_subject)
    metadata_payload = json.loads((config.get_project_path(new_project_id, "shorts", "clip.json")).read_text(encoding="utf-8"))
    assert metadata_payload["render_metadata"]["project_id"] == new_project_id
    assert manager.jobs["completed-job"]["project_id"] == new_project_id
    assert manager.jobs["completed-job"]["output_url"] == old_output_url.replace(old_project_id, new_project_id)


def test_claim_project_ownership_rejects_active_project_jobs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-recovery-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(manager, "jobs", JobStateRepository(tmp_path / "jobs.json"))

    old_project_id = build_owner_scoped_project_id("yt", "legacy-subject", "video123")
    _create_project(old_project_id)
    ensure_project_manifest(old_project_id, owner_subject="legacy-subject", source="youtube")
    manager.jobs["processing-job"] = {
        "job_id": "processing-job",
        "project_id": old_project_id,
        "status": "processing",
    }

    client = _build_client("clerk-user-1", {"viewer"})

    response = client.post("/api/auth/claim-project-ownership", json={"project_id": old_project_id})

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "project_has_active_jobs"
