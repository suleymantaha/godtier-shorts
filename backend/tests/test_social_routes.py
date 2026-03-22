import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

import backend.config as config
from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import social
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest
from backend.services.social.crypto import SocialCrypto
from backend.services.social.service import (
    build_signed_social_export_token,
    build_signed_social_oauth_state,
    build_signed_social_oauth_subject_token,
)
from backend.services.social.store import SocialStore


class _FakePostizClient:
    def __init__(self, accounts):
        self._accounts = accounts
        self.uploaded = False
        self.base_url = "http://postiz.test/public/v1"

    def list_integrations(self):
        return self._accounts

    def upload_media_direct(self, _clip_path):
        self.uploaded = True
        return {"id": "media_1", "path": "/uploads/media_1.mp4"}

    def upload_media_from_url(self, _url):
        self.uploaded = True
        return {"id": "media_2", "path": "/uploads/media_2.mp4"}


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(social.router)
    return app


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def _write_owned_social_project(project_root: Path, project_id: str, *, owner_token: str, clip_name: str) -> None:
    clip_dir = config.get_project_path(project_id, "shorts")
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / clip_name).write_bytes(b"video")
    (clip_dir / clip_name.replace(".mp4", ".json")).write_text(
        json.dumps({"transcript": [], "viral_metadata": {}}),
        encoding="utf-8",
    )
    ensure_project_manifest(project_id, owner_subject=_static_subject(owner_token), source="social_test")


@pytest.fixture()
def social_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SocialStore:
    store = SocialStore(tmp_path / "social_test.db")
    monkeypatch.setattr("backend.services.social.store._store_instance", store)
    return store


@pytest.fixture(autouse=True)
def social_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "social-ownership-test-secret")
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "manual_api_key")


@pytest.fixture(autouse=True)
def default_postiz_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def _resolve_client(_subject: str, **_kwargs):
        return (_FakePostizClient([{"id": "acc_1", "provider": "youtube", "name": "YT Main"}]), {})

    monkeypatch.setattr(social, "get_postiz_client_for_subject", _resolve_client)
    monkeypatch.setattr(
        "backend.services.social.service.get_postiz_client_for_subject",
        _resolve_client,
    )


@pytest.fixture()
def auth_header(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token:editor;viewer-token:viewer")
    return {"Authorization": "Bearer editor-token"}


def test_social_credentials_and_accounts_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "manual_api_key")
    accounts = [{"id": "acc_1", "provider": "youtube", "name": "YT Main"}]

    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [
        {
            "id": "acc_1",
            "name": "YT Main",
            "platform": "youtube_shorts",
            "provider": "youtube",
            "username": None,
            "avatar_url": None,
            "raw": accounts[0],
        }
    ])
    monkeypatch.setattr(social, "get_postiz_client_for_subject", lambda *_args, **_kwargs: (_FakePostizClient(accounts), {}))

    client = TestClient(_build_app())

    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200
    assert save.json()["status"] == "connected"

    list_resp = client.get("/api/social/accounts", headers=auth_header)
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["connected"] is True
    assert payload["connection_mode"] == "manual_api_key"
    assert payload["accounts"][0]["platform"] == "youtube_shorts"


def test_social_accounts_endpoint_reports_managed_mode(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "managed")
    monkeypatch.setenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_ID", "postiz_client_123")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_SECRET", "postiz_secret_123")
    monkeypatch.setenv("SOCIAL_OAUTH_CALLBACK_URL", "http://localhost:8000/api/social/oauth/callback")
    monkeypatch.setenv("SOCIAL_OAUTH_RETURN_URL", "http://localhost:5173/share")

    client = TestClient(_build_app())
    list_resp = client.get("/api/social/accounts", headers=auth_header)

    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["accounts"] == []
    assert payload["connected"] is False
    assert payload["connection_mode"] == "managed"
    assert payload["provider"] == "postiz"
    connect_url = str(payload["connect_url"])
    assert connect_url.startswith("/api/social/oauth/start?integration=youtube&subject_token=")


def test_social_credentials_endpoint_rejects_manual_api_key_in_managed_mode(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "managed")
    client = TestClient(_build_app())

    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )

    assert save.status_code == 403
    assert "manuel Postiz API key" in json.dumps(save.json(), ensure_ascii=False)


def test_social_oauth_start_redirects_to_postiz_authorize(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_ID", "postiz_client_123")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_SECRET", "postiz_secret_123")
    monkeypatch.setenv("SOCIAL_OAUTH_CALLBACK_URL", "http://localhost:8000/api/social/oauth/callback")
    monkeypatch.setenv("SOCIAL_OAUTH_RETURN_URL", "http://localhost:5173/share")
    subject_token = build_signed_social_oauth_subject_token(
        subject=_static_subject("editor-token"),
        integration="youtube",
    )

    client = TestClient(_build_app(), follow_redirects=False)
    response = client.get(
        "/api/social/oauth/start",
        params={"integration": "youtube", "subject_token": subject_token},
    )

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.path == "/oauth/authorize"
    assert query["client_id"] == ["postiz_client_123"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["http://localhost:8000/api/social/oauth/callback"]
    assert query["integration"] == ["youtube"]
    assert query["provider"] == ["youtube"]
    assert "state" in query and query["state"][0]


def test_social_oauth_callback_saves_subject_credential_and_redirects_success(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
):
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_ID", "postiz_client_123")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_SECRET", "postiz_secret_123")
    monkeypatch.setenv("SOCIAL_OAUTH_CALLBACK_URL", "http://localhost:8000/api/social/oauth/callback")
    monkeypatch.setenv("SOCIAL_OAUTH_RETURN_URL", "http://localhost:5173/share")
    monkeypatch.setattr(
        social,
        "exchange_postiz_oauth_code",
        lambda **_kwargs: {"access_token": "oauth_access_token_123"},
    )
    subject = _static_subject("editor-token")
    state = build_signed_social_oauth_state(subject=subject, integration="youtube")

    client = TestClient(_build_app(), follow_redirects=False)
    response = client.get(
        "/api/social/oauth/callback",
        params={"state": state, "code": "oauth_code_123"},
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:5173/share?social_oauth=success"
    credential = social_store.get_credential(subject, "postiz")
    assert credential is not None
    assert SocialCrypto().decrypt(str(credential["encrypted_api_key"])) == "oauth_access_token_123"


def test_social_oauth_callback_returns_error_for_invalid_or_expired_state(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_ID", "postiz_client_123")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_SECRET", "postiz_secret_123")
    monkeypatch.setenv("SOCIAL_OAUTH_CALLBACK_URL", "http://localhost:8000/api/social/oauth/callback")
    monkeypatch.setenv("SOCIAL_OAUTH_RETURN_URL", "http://localhost:5173/share")

    client = TestClient(_build_app(), follow_redirects=False)
    invalid_response = client.get(
        "/api/social/oauth/callback",
        params={"state": f"{'x' * 24}.{'y' * 24}", "code": "oauth_code_123"},
    )
    expired_state = build_signed_social_oauth_state(
        subject=_static_subject("editor-token"),
        integration="youtube",
        ttl_seconds=-1,
    )
    expired_response = client.get(
        "/api/social/oauth/callback",
        params={"state": expired_state, "code": "oauth_code_123"},
    )
    oauth_error_response = client.get(
        "/api/social/oauth/callback",
        params={
            "state": build_signed_social_oauth_state(
                subject=_static_subject("editor-token"),
                integration="youtube",
            ),
            "error": "access_denied",
        },
    )

    assert invalid_response.status_code == 307
    assert invalid_response.headers["location"] == "http://localhost:5173/share?social_oauth=error"
    assert expired_response.status_code == 307
    assert expired_response.headers["location"] == "http://localhost:5173/share?social_oauth=error"
    assert oauth_error_response.status_code == 307
    assert oauth_error_response.headers["location"] == "http://localhost:5173/share?social_oauth=error"


def test_social_prefill_drafts_and_publish(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
    tmp_path: Path,
):
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    # Inject isolated workspace projects dir for test clip metadata.
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "1")
    clip_dir = config.get_project_path(project_id, "shorts")
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_1.mp4").write_bytes(b"video")
    (clip_dir / "clip_1.json").write_text(
        json.dumps(
            {
                "transcript": [],
                "viral_metadata": {
                    "hook_text": "HOOK",
                    "ui_title": "TITLE",
                    "social_caption": "Caption #viral #test",
                    "viral_score": 90,
                },
                "render_metadata": {"start_time": 10, "end_time": 20},
            }
        ),
        encoding="utf-8",
    )
    ensure_project_manifest(project_id, owner_subject=_static_subject("editor-token"), source="social_test")

    # Save credential first.
    client = TestClient(_build_app())
    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200

    prefill = client.get(
        "/api/social/prefill",
        headers=auth_header,
        params={"project_id": project_id, "clip_name": "clip_1.mp4"},
    )
    assert prefill.status_code == 200
    prefill_payload = prefill.json()
    assert prefill_payload["platforms"]["youtube_shorts"]["title"] == "TITLE"

    draft = client.put(
        "/api/social/drafts",
        headers=auth_header,
        json={
            "project_id": project_id,
            "clip_name": "clip_1.mp4",
            "platforms": {
                "youtube_shorts": {
                    "title": "Custom Title",
                    "text": "Custom Text",
                    "hashtags": ["custom"],
                }
            },
        },
    )
    assert draft.status_code == 200

    prefill_with_draft = client.get(
        "/api/social/prefill",
        headers=auth_header,
        params={"project_id": project_id, "clip_name": "clip_1.mp4"},
    )
    assert prefill_with_draft.status_code == 200
    assert prefill_with_draft.json()["platforms"]["youtube_shorts"]["title"] == "Custom Title"

    delete_draft = client.delete(
        "/api/social/drafts",
        headers=auth_header,
        params={"project_id": project_id, "clip_name": "clip_1.mp4"},
    )
    assert delete_draft.status_code == 200
    assert delete_draft.json()["status"] == "deleted"

    prefill_after_reset = client.get(
        "/api/social/prefill",
        headers=auth_header,
        params={"project_id": project_id, "clip_name": "clip_1.mp4"},
    )
    assert prefill_after_reset.status_code == 200
    assert prefill_after_reset.json()["platforms"]["youtube_shorts"]["title"] == "TITLE"

    publish = client.post(
        "/api/social/publish",
        headers=auth_header,
        json={
            "project_id": project_id,
            "clip_name": "clip_1.mp4",
            "mode": "now",
            "approval_required": False,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Custom Title",
                    "text": "Custom Text",
                    "hashtags": ["custom"],
                }
            },
        },
    )
    assert publish.status_code == 200
    assert publish.json()["status"] == "queued"

    jobs = client.get(
        "/api/social/publish-jobs",
        headers=auth_header,
        params={"project_id": project_id, "clip_name": "clip_1.mp4"},
    )
    assert jobs.status_code == 200
    assert len(jobs.json()["jobs"]) == 1


def test_social_user_isolation(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    tmp_path: Path,
):
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token-a:editor;editor-token-b:editor")
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token-a", "2")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token-a", clip_name="clip_2.mp4")

    client = TestClient(_build_app())

    a_headers = {"Authorization": "Bearer editor-token-a"}
    b_headers = {"Authorization": "Bearer editor-token-b"}

    # user A setup
    client.post(
        "/api/social/credentials",
        headers=a_headers,
        json={"provider": "postiz", "api_key": "postiz_key_a"},
    )
    client.post(
        "/api/social/publish",
        headers=a_headers,
        json={
            "project_id": project_id,
            "clip_name": "clip_2.mp4",
            "mode": "now",
            "approval_required": False,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Title A",
                    "text": "Text A",
                    "hashtags": ["a"],
                }
            },
        },
    )

    jobs_a = client.get("/api/social/publish-jobs", headers=a_headers)
    jobs_b = client.get("/api/social/publish-jobs", headers=b_headers)

    assert jobs_a.status_code == 200 and len(jobs_a.json()["jobs"]) == 1
    assert jobs_b.status_code == 200 and len(jobs_b.json()["jobs"]) == 0


def test_social_accounts_and_publish_targets_are_isolated_per_subject(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token-a:editor;editor-token-b:editor")
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token-b", "2b")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token-b", clip_name="clip_2b.mp4")

    def fake_client_for_subject(subject: str, **_kwargs):
        if subject == _static_subject("editor-token-a"):
            return (_FakePostizClient([{"id": "acc_a", "provider": "youtube", "name": "YT A"}]), {})
        if subject == _static_subject("editor-token-b"):
            return (_FakePostizClient([{"id": "acc_b", "provider": "youtube", "name": "YT B"}]), {})
        raise AssertionError(f"unexpected subject: {subject}")

    monkeypatch.setattr(social, "get_postiz_client_for_subject", fake_client_for_subject)
    monkeypatch.setattr(
        "backend.services.social.service.get_postiz_client_for_subject",
        fake_client_for_subject,
    )

    client = TestClient(_build_app())
    a_headers = {"Authorization": "Bearer editor-token-a"}
    b_headers = {"Authorization": "Bearer editor-token-b"}

    assert client.post(
        "/api/social/credentials",
        headers=a_headers,
        json={"provider": "postiz", "api_key": "postiz_key_a_123"},
    ).status_code == 200
    assert client.post(
        "/api/social/credentials",
        headers=b_headers,
        json={"provider": "postiz", "api_key": "postiz_key_b_123"},
    ).status_code == 200

    accounts_a = client.get("/api/social/accounts", headers=a_headers)
    accounts_b = client.get("/api/social/accounts", headers=b_headers)

    assert accounts_a.status_code == 200
    assert accounts_b.status_code == 200
    assert [item["id"] for item in accounts_a.json()["accounts"]] == ["acc_a"]
    assert [item["id"] for item in accounts_b.json()["accounts"]] == ["acc_b"]

    foreign_publish = client.post(
        "/api/social/publish",
        headers=b_headers,
        json={
            "project_id": project_id,
            "clip_name": "clip_2b.mp4",
            "mode": "now",
            "approval_required": False,
            "targets": [{"account_id": "acc_a", "platform": "youtube_shorts", "provider": "youtube"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Foreign Title",
                    "text": "Foreign Text",
                    "hashtags": ["foreign"],
                }
            },
        },
    )

    assert foreign_publish.status_code == 400
    assert "bu kullanıcıya bağlı değil" in foreign_publish.text


def test_social_publish_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
    tmp_path: Path,
):
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "3")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token", clip_name="clip_3.mp4")

    fake_client = _FakePostizClient([{"id": "acc_1", "provider": "youtube", "name": "YT Main"}])
    monkeypatch.setattr(social, "get_postiz_client_for_subject", lambda *_args, **_kwargs: (fake_client, {}))
    monkeypatch.setattr(
        "backend.services.social.service.get_postiz_client_for_subject",
        lambda *_args, **_kwargs: (fake_client, {}),
    )

    client = TestClient(_build_app())
    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200

    dry_run = client.post(
        "/api/social/publish/dry-run",
        headers=auth_header,
        json={
            "project_id": project_id,
            "clip_name": "clip_3.mp4",
            "mode": "now",
            "probe_media_upload": True,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts", "provider": "youtube"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Dry Run Title",
                    "text": "Dry Run Text",
                    "hashtags": ["viral", "test"],
                }
            },
        },
    )
    assert dry_run.status_code == 200
    payload = dry_run.json()
    assert payload["status"] == "ok"
    assert payload["dry_run"]["targets"][0]["settings_type"] == "youtube"
    assert payload["dry_run"]["media_probe"]["attempted"] is True


def test_social_routes_reject_foreign_project_access(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token-a:editor;editor-token-b:editor")
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token-a", "4")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token-a", clip_name="clip_4.mp4")

    client = TestClient(_build_app())
    a_headers = {"Authorization": "Bearer editor-token-a"}
    b_headers = {"Authorization": "Bearer editor-token-b"}

    save = client.post(
        "/api/social/credentials",
        headers=a_headers,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200

    client.post(
        "/api/social/credentials",
        headers=b_headers,
        json={"provider": "postiz", "api_key": "postiz_test_key_456"},
    )

    assert client.get(
        "/api/social/prefill",
        headers=b_headers,
        params={"project_id": project_id, "clip_name": "clip_4.mp4"},
    ).status_code == 404

    assert client.put(
        "/api/social/drafts",
        headers=b_headers,
        json={
            "project_id": project_id,
            "clip_name": "clip_4.mp4",
            "platforms": {"youtube_shorts": {"title": "nope"}},
        },
    ).status_code == 404

    assert client.post(
        "/api/social/publish",
        headers=b_headers,
        json={
            "project_id": project_id,
            "clip_name": "clip_4.mp4",
            "mode": "now",
            "approval_required": False,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts"}],
            "content_by_platform": {"youtube_shorts": {"title": "x", "text": "y", "hashtags": []}},
        },
    ).status_code == 404

    assert client.post(
        "/api/social/publish/dry-run",
        headers=b_headers,
        json={
            "project_id": project_id,
            "clip_name": "clip_4.mp4",
            "mode": "now",
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts"}],
            "content_by_platform": {"youtube_shorts": {"title": "x", "text": "y", "hashtags": []}},
        },
    ).status_code == 404


def test_social_export_serves_clip_for_valid_signed_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "export")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token", clip_name="clip_export.mp4")

    token = build_signed_social_export_token(
        subject=_static_subject("editor-token"),
        project_id=project_id,
        clip_name="clip_export.mp4",
        publish_job_id="job-export",
        ttl_seconds=300,
    )

    client = TestClient(_build_app())
    response = client.get("/api/social/export", params={"token": token})

    assert response.status_code == 200
    assert response.content == b"video"


def test_social_export_rejects_invalid_or_expired_token_with_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "export")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token", clip_name="clip_export.mp4")

    expired_token = build_signed_social_export_token(
        subject=_static_subject("editor-token"),
        project_id=project_id,
        clip_name="clip_export.mp4",
        publish_job_id="job-export",
        ttl_seconds=-1,
    )
    invalid_token = f"{expired_token}tampered"

    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    try:
        client = TestClient(_build_app())
        expired_response = client.get("/api/social/export", params={"token": expired_token})
        invalid_response = client.get("/api/social/export", params={"token": invalid_token})
    finally:
        logger.remove(sink_id)

    assert expired_response.status_code == 404
    assert invalid_response.status_code == 404
    assert any("social_export_denied" in message for message in messages)


def test_social_accounts_uses_opt_in_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.setenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", "1")
    fake_client = _FakePostizClient([{"id": "acc_1", "provider": "youtube", "name": "YT Main"}])
    monkeypatch.setattr(social, "get_postiz_client_for_subject", lambda *_args, **_kwargs: (fake_client, {"source": "env"}))

    client = TestClient(_build_app())
    response = client.get("/api/social/accounts", headers=auth_header)

    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert payload["accounts"][0]["platform"] == "youtube_shorts"


def test_scheduled_publish_is_synced_to_postiz_immediately(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
    tmp_path: Path,
):
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "4")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token", clip_name="clip_4.mp4")

    def fake_schedule(job, *, store=None):
        assert store is not None
        store.update_publish_job(
            job["id"],
            state="scheduled",
            message="Postiz takvimine eklendi",
            provider_job_id="post_123",
        )
        return store.get_publish_job(job["id"])

    monkeypatch.setattr(social, "create_scheduled_post_now", fake_schedule)

    client = TestClient(_build_app())
    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200

    publish = client.post(
        "/api/social/publish",
        headers=auth_header,
        json={
            "project_id": project_id,
            "clip_name": "clip_4.mp4",
            "mode": "scheduled",
            "scheduled_at": "2026-03-16T03:02",
            "timezone": "Europe/Istanbul",
            "approval_required": False,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts", "provider": "youtube"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Scheduled Title",
                    "text": "Scheduled Text",
                    "hashtags": ["scheduled"],
                }
            },
        },
    )
    assert publish.status_code == 200
    payload = publish.json()
    assert payload["status"] == "scheduled"
    assert payload["jobs"][0]["state"] == "scheduled"

    jobs = client.get(
        "/api/social/publish-jobs",
        headers=auth_header,
        params={"project_id": project_id, "clip_name": "clip_4.mp4"},
    )
    assert jobs.status_code == 200
    assert jobs.json()["jobs"][0]["state"] == "scheduled"
    assert jobs.json()["jobs"][0]["provider_job_id"] == "post_123"


def test_approve_future_scheduled_job_creates_remote_schedule(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    tmp_path: Path,
):
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    monkeypatch.setenv("API_BEARER_TOKENS", "approver-token:admin,editor")
    auth_header = {"Authorization": "Bearer approver-token"}
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("approver-token", "5")
    _write_owned_social_project(project_root, project_id, owner_token="approver-token", clip_name="clip_5.mp4")

    def fake_schedule(job, *, store=None):
        assert store is not None
        store.update_publish_job(
            job["id"],
            state="scheduled",
            message="Postiz takvimine eklendi",
            provider_job_id="post_approved",
        )
        return store.get_publish_job(job["id"])

    monkeypatch.setattr(social, "create_scheduled_post_now", fake_schedule)

    client = TestClient(_build_app())
    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200

    publish = client.post(
        "/api/social/publish",
        headers=auth_header,
        json={
            "project_id": project_id,
            "clip_name": "clip_5.mp4",
            "mode": "scheduled",
            "scheduled_at": scheduled_at,
            "timezone": "Europe/Istanbul",
            "approval_required": True,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts", "provider": "youtube"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Approval Title",
                    "text": "Approval Text",
                    "hashtags": ["approval"],
                }
            },
        },
    )
    assert publish.status_code == 200
    job_id = publish.json()["jobs"][0]["id"]

    approve = client.post(f"/api/social/publish-jobs/{job_id}/approve", headers=auth_header)
    assert approve.status_code == 200
    assert approve.json()["status"] == "scheduled"

    job = social_store.get_publish_job(job_id)
    assert job is not None
    assert job["state"] == "scheduled"
    assert job["provider_job_id"] == "post_approved"


def test_cancel_scheduled_job_deletes_remote_post(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
    tmp_path: Path,
):
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])
    deleted: list[str] = []

    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    project_id = _owned_project_id("editor-token", "6")
    _write_owned_social_project(project_root, project_id, owner_token="editor-token", clip_name="clip_6.mp4")

    def fake_schedule(job, *, store=None):
        assert store is not None
        store.update_publish_job(
            job["id"],
            state="scheduled",
            message="Postiz takvimine eklendi",
            provider_job_id="post_remote_1",
        )
        return store.get_publish_job(job["id"])

    def fake_delete(job, *, store=None):
        deleted.append(str(job["provider_job_id"]))

    monkeypatch.setattr(social, "create_scheduled_post_now", fake_schedule)
    monkeypatch.setattr(social, "delete_scheduled_post_from_postiz", fake_delete)

    client = TestClient(_build_app())
    save = client.post(
        "/api/social/credentials",
        headers=auth_header,
        json={"provider": "postiz", "api_key": "postiz_test_key_123"},
    )
    assert save.status_code == 200

    publish = client.post(
        "/api/social/publish",
        headers=auth_header,
        json={
            "project_id": project_id,
            "clip_name": "clip_6.mp4",
            "mode": "scheduled",
            "scheduled_at": "2026-03-16T03:02",
            "timezone": "Europe/Istanbul",
            "approval_required": False,
            "targets": [{"account_id": "acc_1", "platform": "youtube_shorts", "provider": "youtube"}],
            "content_by_platform": {
                "youtube_shorts": {
                    "title": "Cancel Title",
                    "text": "Cancel Text",
                    "hashtags": ["cancel"],
                }
            },
        },
    )
    assert publish.status_code == 200
    job_id = publish.json()["jobs"][0]["id"]

    cancel = client.post(f"/api/social/publish-jobs/{job_id}/cancel", headers=auth_header)
    assert cancel.status_code == 200
    assert deleted == ["post_remote_1"]


def test_due_jobs_exclude_legacy_scheduled_drafts(social_store: SocialStore):
    social_store.create_publish_jobs(
        subject="static-token:test",
        provider="postiz",
        project_id="proj_legacy",
        clip_name="legacy.mp4",
        mode="scheduled",
        timezone_name="UTC",
        scheduled_at="2026-03-13T00:00:00+00:00",
        approval_required=False,
        targets=[{"account_id": "acc_1", "platform": "youtube_shorts"}],
        content_by_platform={"youtube_shorts": {"title": "T", "text": "X", "hashtags": []}},
    )
    social_store.create_publish_jobs(
        subject="static-token:test",
        provider="postiz",
        project_id="proj_now",
        clip_name="now.mp4",
        mode="now",
        timezone_name="UTC",
        scheduled_at=None,
        approval_required=False,
        targets=[{"account_id": "acc_2", "platform": "youtube_shorts"}],
        content_by_platform={"youtube_shorts": {"title": "T", "text": "X", "hashtags": []}},
    )

    due_jobs = social_store.list_due_jobs(limit=10)

    assert len(due_jobs) == 1
    assert due_jobs[0]["mode"] == "now"
