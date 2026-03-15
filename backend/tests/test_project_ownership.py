from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import backend.config as config
from backend.services import ownership


def _project_id(subject: str, suffix: str) -> str:
    return ownership.build_owner_scoped_project_id("proj", subject, suffix)


def test_build_subject_hash_is_stable_and_32_chars(monkeypatch) -> None:
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")

    first = ownership.build_subject_hash("user_a")
    second = ownership.build_subject_hash("user_a")
    third = ownership.build_subject_hash("user_b")

    assert first == second
    assert first != third
    assert len(first) == 32


def test_manifest_round_trip_and_owner_access(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    project_id = _project_id("subject-a", "owner")

    manifest = ownership.create_project_manifest(
        project_id,
        owner_subject="subject-a",
        source="upload",
    )
    ownership.write_project_manifest(project_id, manifest)

    loaded = ownership.read_project_manifest(project_id)
    assert loaded is not None
    assert loaded.project_id == project_id
    assert loaded.status == "active"

    allowed, reason, resolved = ownership.resolve_project_access(project_id, "subject-a")
    assert allowed is True
    assert reason == "owner_match"
    assert resolved is not None and resolved.owner_subject_hash == manifest.owner_subject_hash


def test_missing_manifest_is_denied_and_treated_as_quarantine(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    project_id = _project_id("subject-a", "missing")
    config.get_project_dir(project_id)

    allowed, reason, manifest = ownership.resolve_project_access(project_id, "subject-a")

    assert allowed is False
    assert reason == "missing_manifest"
    assert manifest is None


def test_quarantined_manifest_is_not_accessible(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    project_id = _project_id("subject-a", "legacy")

    ownership.quarantine_project(project_id)

    allowed, reason, manifest = ownership.resolve_project_access(project_id, "subject-a")

    assert allowed is False
    assert reason == "status_quarantined"
    assert manifest is not None
    assert manifest.status == "quarantined"


def test_support_grant_allows_temporary_cross_subject_access(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    project_id = _project_id("owner-subject", "support")

    ownership.ensure_project_manifest(project_id, owner_subject="owner-subject", source="upload")
    ownership.grant_support_access(
        project_id,
        owner_subject="owner-subject",
        support_subject="support-subject",
        ttl_seconds=3600,
    )

    allowed, reason, _manifest = ownership.resolve_project_access(project_id, "support-subject")
    assert allowed is True
    assert reason == "support_grant"


def test_expired_support_grant_is_denied(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")
    project_id = _project_id("owner-subject", "support_expired")

    manifest = ownership.ensure_project_manifest(project_id, owner_subject="owner-subject", source="upload")
    manifest.support_grants = [
        ownership.SupportGrant(
            support_subject_hash=ownership.build_subject_hash("support-subject"),
            created_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            granted_by_subject_hash=ownership.build_subject_hash("owner-subject"),
        )
    ]
    ownership.write_project_manifest(project_id, manifest)

    allowed, reason, _manifest = ownership.resolve_project_access(project_id, "support-subject")
    assert allowed is False
    assert reason == "owner_mismatch"
