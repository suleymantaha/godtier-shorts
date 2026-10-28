from __future__ import annotations

import hashlib
import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

import backend.config as config
from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import account
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest
from backend.services.social.store import SocialStore
from backend.db.models import UserRole, UserStatus


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(account.router)
    return app


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


@pytest.fixture(autouse=True)
def social_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SocialStore:
    store = SocialStore(tmp_path / "social.db")
    monkeypatch.setattr("backend.services.social.store._store_instance", store)
    return store


@pytest.fixture()
def auth_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    monkeypatch.setenv("API_BEARER_TOKENS", "token-a:viewer;token-b:viewer")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "account-delete-test-secret")
    return {
        "a": {"Authorization": "Bearer token-a"},
        "b": {"Authorization": "Bearer token-b"},
    }


def test_account_deletion_requires_typed_confirmation(
    auth_headers: dict[str, dict[str, str]],
) -> None:
    client = TestClient(_build_app())

    response = client.request(
        "DELETE",
        "/api/account/me/data",
        headers=auth_headers["a"],
        json={"confirm": "NOPE"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


def test_account_deletion_purges_only_callers_subject_data_and_logs_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    social_store: SocialStore,
    auth_headers: dict[str, dict[str, str]],
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)

    project_a = _owned_project_id("token-a", "owned")
    project_b = _owned_project_id("token-b", "foreign")
    config.get_project_dir(project_a).mkdir(parents=True, exist_ok=True)
    config.get_project_dir(project_b).mkdir(parents=True, exist_ok=True)
    ensure_project_manifest(project_a, owner_subject=_static_subject("token-a"), source="account_delete_test")
    ensure_project_manifest(project_b, owner_subject=_static_subject("token-b"), source="account_delete_test")

    social_store.save_credential(_static_subject("token-a"), "postiz", "encrypted-a", None)
    social_store.save_credential(_static_subject("token-b"), "postiz", "encrypted-b", None)

    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    try:
        client = TestClient(_build_app())
        response = client.request(
            "DELETE",
            "/api/account/me/data",
            headers=auth_headers["a"],
            json={"confirm": "DELETE"},
        )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    assert response.json()["status"] == "purged"
    assert response.json()["summary"]["deleted_projects"] == 1
    assert not config.get_project_path(project_a).exists()
    assert config.get_project_path(project_b).exists()
    assert social_store.get_credential(_static_subject("token-a"), "postiz") is None
    assert social_store.get_credential(_static_subject("token-b"), "postiz") is not None
    assert any("account_data_purged" in message for message in messages)


def test_production_unconfigured_deletion_never_reports_purged(monkeypatch, auth_headers):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = TestClient(_build_app()).request(
        "DELETE", "/api/account/me/data", headers=auth_headers["a"], json={"confirm": "DELETE"})
    assert response.status_code == 202
    assert response.json()["status"] == "deletion_pending"


@pytest.mark.parametrize("method,path,user_status,allowed", [
    ("DELETE", "/api/account/me/data", UserStatus.DELETED, True),
    ("DELETE", "/api/account/me/data", UserStatus.SUSPENDED, False),
    ("POST", "/api/account/me/data", UserStatus.DELETED, False),
    ("POST", "/api/start-job", UserStatus.DELETED, False),
    ("GET", "/api/uploads/private", UserStatus.DELETED, False),
])
def test_tombstoned_identity_can_only_retry_own_deletion(monkeypatch, method, path, user_status, allowed):
    from fastapi import HTTPException, Request
    from fastapi.security import HTTPAuthorizationCredentials
    from backend.api import security

    monkeypatch.setenv("DATABASE_URL", "configured")
    auth = security.AuthContext(subject="owner", roles={"member"}, token_type="jwt", auth_mode="clerk_jwt")
    monkeypatch.setattr(security, "_authenticate_token", lambda *args, **kwargs: auth)

    async def identity(*args, **kwargs):
        return SimpleNamespace(id=uuid4(), status=user_status, role=UserRole.USER)

    monkeypatch.setattr(security, "get_or_create_user", identity)
    request = Request({"type": "http", "method": method, "path": path, "headers": []})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="verified-test-token")
    if allowed:
        assert asyncio.run(security.authenticate_request(request, credentials)).subject == "owner"
    else:
        with pytest.raises(HTTPException) as failure:
            asyncio.run(security.authenticate_request(request, credentials))
        assert failure.value.status_code == 403
