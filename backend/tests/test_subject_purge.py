from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path

import pytest

import backend.config as config
from backend.api.websocket import ConnectionManager, manager
from backend.services.account_purge import purge_subject_data
from backend.services.ownership import (
    build_owner_scoped_project_id,
    ensure_project_manifest,
    grant_support_access,
    read_project_manifest,
)
from backend.services.social.store import SocialStore


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


class DummyWebSocket:
    def __init__(self) -> None:
        self.closed = False

    async def accept(self, subprotocol: str | None = None) -> None:
        return None

    async def close(self, code: int = 1000) -> None:
        self.closed = True


def _owned_project_id(token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(token), suffix)


@pytest.fixture()
def isolated_social_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SocialStore:
    store = SocialStore(tmp_path / "social.db")
    monkeypatch.setattr("backend.services.social.store._store_instance", store)
    return store


@pytest.fixture(autouse=True)
def reset_manager_state():
    manager.jobs.clear()
    manager.active_connections.clear()
    yield
    manager.jobs.clear()
    manager.active_connections.clear()


def test_purge_subject_data_removes_owned_projects_social_rows_jobs_websockets_and_grants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_social_store: SocialStore,
) -> None:
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "subject-purge-test-secret")
    project_root = tmp_path / "projects"
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)

    subject_token = "token-a"
    subject = _static_subject(subject_token)
    project_id = _owned_project_id(subject_token, "owned")
    project_dir = config.get_project_dir(project_id)
    (project_dir / "master.mp4").write_bytes(b"master")
    ensure_project_manifest(project_id, owner_subject=subject, source="purge_test")

    foreign_project_id = _owned_project_id("token-b", "foreign")
    foreign_project_dir = config.get_project_dir(foreign_project_id)
    foreign_project_dir.mkdir(parents=True, exist_ok=True)
    ensure_project_manifest(foreign_project_id, owner_subject=_static_subject("token-b"), source="purge_test")
    grant_support_access(
        foreign_project_id,
        owner_subject=_static_subject("token-b"),
        support_subject=subject,
        ttl_seconds=3600,
    )

    isolated_social_store.save_credential(subject, "postiz", "encrypted", None)
    isolated_social_store.upsert_drafts(subject, project_id, "clip.mp4", {"youtube_shorts": {"title": "T"}})
    isolated_social_store.create_publish_jobs(
        subject=subject,
        provider="postiz",
        project_id=project_id,
        clip_name="clip.mp4",
        mode="now",
        timezone_name="UTC",
        scheduled_at=None,
        approval_required=False,
        targets=[{"account_id": "acc_1", "platform": "youtube_shorts"}],
        content_by_platform={"youtube_shorts": {"title": "T", "text": "X", "hashtags": []}},
    )

    ws = DummyWebSocket()
    asyncio.run(manager.connect(ws, subject=subject))
    cancel_event = threading.Event()
    manager.jobs["job-a"] = {
        "job_id": "job-a",
        "status": "processing",
        "progress": 10,
        "last_message": "running",
        "subject": subject,
        "cancel_event": cancel_event,
    }
    manager.jobs["job-b"] = {
        "job_id": "job-b",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "subject": _static_subject("token-b"),
    }

    summary = asyncio.run(purge_subject_data(subject))

    assert summary == {
        "deleted_projects": 1,
        "deleted_social_rows": 3,
        "cancelled_jobs": 1,
        "closed_websockets": 1,
        "scrubbed_grants": 1,
    }
    assert not project_dir.exists()
    assert foreign_project_dir.exists()
    assert isolated_social_store.get_credential(subject, "postiz") is None
    assert isolated_social_store.get_drafts(subject, project_id, "clip.mp4") == {}
    assert isolated_social_store.list_publish_jobs(subject) == []
    assert cancel_event.is_set() is True
    assert "job-a" not in manager.jobs
    assert "job-b" in manager.jobs
    assert ws.closed is True
    assert read_project_manifest(foreign_project_id) is not None
    assert read_project_manifest(foreign_project_id).support_grants == []
    assert subject not in manager.active_connections.values()


def test_purge_subject_data_is_noop_for_unknown_subject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_social_store: SocialStore,
) -> None:
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "subject-purge-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")

    summary = asyncio.run(purge_subject_data(_static_subject("missing")))

    assert summary == {
        "deleted_projects": 0,
        "deleted_social_rows": 0,
        "cancelled_jobs": 0,
        "closed_websockets": 0,
        "scrubbed_grants": 0,
    }
    assert isinstance(manager, ConnectionManager)
