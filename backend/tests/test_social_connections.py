from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.routes import social
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest
from backend.services.social.repository import SocialRepository
from backend.services.social.store import SocialStore
import backend.config as config
from backend.tests.test_social_routes import _FakePostizClient, _build_app, _static_subject


@pytest.fixture()
def social_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SocialStore:
    store = SocialStore(tmp_path / "social_suite_test.db")
    monkeypatch.setattr("backend.services.social.store._store_instance", store)
    monkeypatch.setattr("backend.services.social.repository._repository_instance", SocialRepository(store))
    return store


@pytest.fixture(autouse=True)
def social_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "social-ownership-test-secret")
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "managed")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_ID", "postiz_client_123")
    monkeypatch.setenv("POSTIZ_OAUTH_CLIENT_SECRET", "postiz_secret_123")
    monkeypatch.setenv("SOCIAL_OAUTH_CALLBACK_URL", "http://localhost:8000/api/social/oauth/callback")
    monkeypatch.setenv("SOCIAL_OAUTH_RETURN_URL", "http://localhost:5173/")
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token:editor;viewer-token:viewer")


@pytest.fixture()
def auth_header() -> dict[str, str]:
    return {"Authorization": "Bearer editor-token"}


def _save_credential(store: SocialStore, subject: str) -> None:
    from backend.services.social.crypto import SocialCrypto

    store.save_credential(subject, "postiz", SocialCrypto().encrypt("oauth_access_token_123"), None)


def test_social_connections_start_returns_oauth_launch_when_subject_has_no_credential(
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    client = TestClient(_build_app())

    response = client.post("/api/social/connections/start", headers=auth_header, json={"platform": "youtube_shorts"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "oauth_required"
    assert payload["session_id"]
    assert "connection_session_id=" in payload["launch_url"]


def test_social_connections_sync_populates_cached_accounts(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    subject = _static_subject("editor-token")
    _save_credential(social_store, subject)

    def _resolve_client(_subject: str, **_kwargs):
        return (_FakePostizClient([{"id": "acc_1", "identifier": "youtube", "name": "YT Main"}]), {})

    monkeypatch.setattr(social, "get_postiz_client_for_subject", _resolve_client)
    monkeypatch.setattr("backend.services.social.service.get_postiz_client_for_subject", _resolve_client)

    client = TestClient(_build_app())
    response = client.post("/api/social/connections/sync", headers=auth_header)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "synced"
    assert payload["accounts"][0]["platform"] == "youtube_shorts"

    connections = client.get("/api/social/connections", headers=auth_header)
    assert connections.status_code == 200
    assert connections.json()["accounts"][0]["name"] == "YT Main"


def test_social_connection_delete_marks_account_disconnected(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    subject = _static_subject("editor-token")
    _save_credential(social_store, subject)
    social_store.replace_account_cache(
        subject,
        [{"id": "acc_1", "platform": "youtube_shorts", "provider": "youtube", "name": "YT Main"}],
    )

    class _DeletingClient(_FakePostizClient):
        def delete_integration(self, integration_id: str):
            assert integration_id == "acc_1"
            return {"status": "deleted"}

    def _resolve_client(_subject: str, **_kwargs):
        return (_DeletingClient([]), {})

    monkeypatch.setattr(social, "get_postiz_client_for_subject", _resolve_client)
    monkeypatch.setattr("backend.services.social.service.get_postiz_client_for_subject", _resolve_client)

    client = TestClient(_build_app())
    response = client.delete("/api/social/connections/acc_1", headers=auth_header)

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    cached = social_store.list_account_cache(subject, include_disabled=True)
    assert cached[0]["disabled"] is True


def test_social_calendar_patch_reschedules_existing_job(
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    subject = _static_subject("editor-token")
    project_id = build_owner_scoped_project_id("proj", subject, "social-cal")
    ensure_project_manifest(project_id, owner_subject=subject, source="social_test")
    clip_dir = config.get_project_path(project_id, "shorts")
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_1.mp4").write_bytes(b"video")

    created = social_store.create_publish_jobs(
        subject=subject,
        provider="postiz",
        project_id=project_id,
        clip_name="clip_1.mp4",
        mode="scheduled",
        timezone_name="UTC",
        scheduled_at="2026-03-24T10:00:00+00:00",
        approval_required=False,
        targets=[{"account_id": "acc_1", "platform": "youtube_shorts", "provider": "youtube"}],
        content_by_platform={"youtube_shorts": {"title": "Title", "text": "Body", "hashtags": []}},
    )

    client = TestClient(_build_app())
    response = client.patch(
        f"/api/social/calendar/{created[0]['id']}",
        headers=auth_header,
        json={"scheduled_at": "2026-03-24T15:30", "timezone": "UTC"},
    )

    assert response.status_code == 200
    assert response.json()["job"]["scheduled_at"] == "2026-03-24T15:30:00+00:00"


def test_social_analytics_endpoints_aggregate_jobs_and_accounts(
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    subject = _static_subject("editor-token")
    social_store.replace_account_cache(
        subject,
        [
            {"id": "acc_1", "platform": "youtube_shorts", "provider": "youtube", "name": "YT Main"},
            {"id": "acc_2", "platform": "linkedin", "provider": "linkedin", "name": "LinkedIn Main"},
        ],
    )
    jobs = social_store.create_publish_jobs(
        subject=subject,
        provider="postiz",
        project_id="proj_social",
        clip_name="clip_1.mp4",
        mode="now",
        timezone_name="UTC",
        scheduled_at=None,
        approval_required=False,
        targets=[
            {"account_id": "acc_1", "platform": "youtube_shorts", "provider": "youtube"},
            {"account_id": "acc_2", "platform": "linkedin", "provider": "linkedin"},
        ],
        content_by_platform={
            "youtube_shorts": {"title": "Title", "text": "Body", "hashtags": []},
            "linkedin": {"title": "Title", "text": "Body", "hashtags": []},
        },
    )
    social_store.update_publish_job(jobs[0]["id"], state="published", message="Published", delivery_status="published")
    social_store.update_publish_job(jobs[1]["id"], state="failed", message="Failed", delivery_status="failed")

    client = TestClient(_build_app())

    overview = client.get("/api/social/analytics/overview", headers=auth_header)
    accounts = client.get("/api/social/analytics/accounts", headers=auth_header)
    posts = client.get("/api/social/analytics/posts", headers=auth_header)

    assert overview.status_code == 200
    assert overview.json()["overview"]["total_jobs"] == 2
    assert overview.json()["overview"]["connected_accounts"] == 2
    assert accounts.status_code == 200
    assert len(accounts.json()["accounts"]) == 2
    assert posts.status_code == 200
    assert posts.json()["posts"][0]["clip_name"] == "clip_1.mp4"
