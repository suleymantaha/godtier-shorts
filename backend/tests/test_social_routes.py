import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import social
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


@pytest.fixture()
def social_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SocialStore:
    store = SocialStore(tmp_path / "social_test.db")
    monkeypatch.setattr("backend.services.social.store._store_instance", store)
    return store


@pytest.fixture(autouse=True)
def social_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")


@pytest.fixture()
def auth_header(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("API_BEARER_TOKENS", "editor-token:editor;viewer-token:viewer")
    return {"Authorization": "Bearer editor-token"}


def test_social_credentials_and_accounts_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
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
    assert payload["accounts"][0]["platform"] == "youtube_shorts"


def test_social_prefill_drafts_and_publish(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
    tmp_path: Path,
):
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    # Inject isolated workspace projects dir for test clip metadata.
    project_root = tmp_path / "projects"
    clip_dir = project_root / "proj_1" / "shorts"
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

    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

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
        params={"project_id": "proj_1", "clip_name": "clip_1.mp4"},
    )
    assert prefill.status_code == 200
    prefill_payload = prefill.json()
    assert prefill_payload["platforms"]["youtube_shorts"]["title"] == "TITLE"

    draft = client.put(
        "/api/social/drafts",
        headers=auth_header,
        json={
            "project_id": "proj_1",
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
        params={"project_id": "proj_1", "clip_name": "clip_1.mp4"},
    )
    assert prefill_with_draft.status_code == 200
    assert prefill_with_draft.json()["platforms"]["youtube_shorts"]["title"] == "Custom Title"

    delete_draft = client.delete(
        "/api/social/drafts",
        headers=auth_header,
        params={"project_id": "proj_1", "clip_name": "clip_1.mp4"},
    )
    assert delete_draft.status_code == 200
    assert delete_draft.json()["status"] == "deleted"

    prefill_after_reset = client.get(
        "/api/social/prefill",
        headers=auth_header,
        params={"project_id": "proj_1", "clip_name": "clip_1.mp4"},
    )
    assert prefill_after_reset.status_code == 200
    assert prefill_after_reset.json()["platforms"]["youtube_shorts"]["title"] == "TITLE"

    publish = client.post(
        "/api/social/publish",
        headers=auth_header,
        json={
            "project_id": "proj_1",
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
        params={"project_id": "proj_1", "clip_name": "clip_1.mp4"},
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
    clip_dir = project_root / "proj_2" / "shorts"
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_2.mp4").write_bytes(b"video")
    (clip_dir / "clip_2.json").write_text(json.dumps({"transcript": [], "viral_metadata": {}}), encoding="utf-8")
    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

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
            "project_id": "proj_2",
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


def test_social_publish_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
    tmp_path: Path,
):
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    clip_dir = project_root / "proj_3" / "shorts"
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_3.mp4").write_bytes(b"video")
    (clip_dir / "clip_3.json").write_text(
        json.dumps({"transcript": [], "viral_metadata": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

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
            "project_id": "proj_3",
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
    assert fake_client.uploaded is True


def test_social_accounts_uses_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    auth_header: dict[str, str],
):
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
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
    clip_dir = project_root / "proj_4" / "shorts"
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_4.mp4").write_bytes(b"video")
    (clip_dir / "clip_4.json").write_text(json.dumps({"transcript": [], "viral_metadata": {}}), encoding="utf-8")
    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

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
            "project_id": "proj_4",
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
        params={"project_id": "proj_4", "clip_name": "clip_4.mp4"},
    )
    assert jobs.status_code == 200
    assert jobs.json()["jobs"][0]["state"] == "scheduled"
    assert jobs.json()["jobs"][0]["provider_job_id"] == "post_123"


def test_approve_future_scheduled_job_creates_remote_schedule(
    monkeypatch: pytest.MonkeyPatch,
    social_store: SocialStore,
    tmp_path: Path,
):
    monkeypatch.setenv("API_BEARER_TOKENS", "approver-token:admin,editor")
    auth_header = {"Authorization": "Bearer approver-token"}
    monkeypatch.setattr(social, "validate_postiz_credential", lambda *_args, **_kwargs: [])

    project_root = tmp_path / "projects"
    clip_dir = project_root / "proj_5" / "shorts"
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_5.mp4").write_bytes(b"video")
    (clip_dir / "clip_5.json").write_text(json.dumps({"transcript": [], "viral_metadata": {}}), encoding="utf-8")
    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

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
            "project_id": "proj_5",
            "clip_name": "clip_5.mp4",
            "mode": "scheduled",
            "scheduled_at": "2026-03-16T03:02",
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
    clip_dir = project_root / "proj_6" / "shorts"
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip_6.mp4").write_bytes(b"video")
    (clip_dir / "clip_6.json").write_text(json.dumps({"transcript": [], "viral_metadata": {}}), encoding="utf-8")
    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)

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
            "project_id": "proj_6",
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
