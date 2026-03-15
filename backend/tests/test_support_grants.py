from __future__ import annotations

import hashlib
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


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def _write_owned_project(project_root: Path, project_id: str, *, owner_token: str) -> None:
    project_dir = config.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "master.mp4").write_bytes(b"master")
    ensure_project_manifest(project_id, owner_subject=_static_subject(owner_token), source="support_test")


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    monkeypatch.setenv(
        "API_BEARER_TOKENS",
        "owner-token:viewer;support-token:viewer;other-token:viewer",
    )
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "support-grant-test-secret")
    monkeypatch.setenv("SUPPORT_SUBJECT_ALLOWLIST", _static_subject("support-token"))
    return {
        "owner": {"Authorization": "Bearer owner-token"},
        "support": {"Authorization": "Bearer support-token"},
        "other": {"Authorization": "Bearer other-token"},
    }


def test_owner_can_grant_and_revoke_support_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("owner-token", "owner")
    _write_owned_project(project_root, project_id, owner_token="owner-token")

    client = TestClient(_build_app())

    grant = client.post(
        f"/api/projects/{project_id}/support-grants",
        headers=auth_headers["owner"],
        json={"support_subject": _static_subject("support-token"), "ttl_seconds": 3600},
    )
    assert grant.status_code == 200
    assert grant.json()["status"] == "granted"

    support_access = client.get(f"/api/projects/{project_id}/master", headers=auth_headers["support"])
    assert support_access.status_code == 200

    revoke = client.delete(
        f"/api/projects/{project_id}/support-grants",
        headers=auth_headers["owner"],
        params={"support_subject": _static_subject("support-token")},
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    support_denied = client.get(f"/api/projects/{project_id}/master", headers=auth_headers["support"])
    assert support_denied.status_code == 404


def test_non_owner_cannot_manage_support_grants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("owner-token", "owner")
    _write_owned_project(project_root, project_id, owner_token="owner-token")

    client = TestClient(_build_app())

    response = client.post(
        f"/api/projects/{project_id}/support-grants",
        headers=auth_headers["other"],
        json={"support_subject": _static_subject("support-token"), "ttl_seconds": 3600},
    )

    assert response.status_code == 404


def test_support_subject_must_be_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(clips, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("owner-token", "owner")
    _write_owned_project(project_root, project_id, owner_token="owner-token")

    client = TestClient(_build_app())
    response = client.post(
        f"/api/projects/{project_id}/support-grants",
        headers=auth_headers["owner"],
        json={"support_subject": _static_subject("other-token"), "ttl_seconds": 3600},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"
