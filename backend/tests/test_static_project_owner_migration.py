from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.config as config
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest, read_project_manifest
from scripts import migrate_static_project_to_clerk_owner as migration_script


def _static_subject(token: str) -> str:
    return f"static-token:{token}"


def test_migrate_project_owner_moves_project_and_rewrites_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "projects"
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "migration-script-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", project_root)
    monkeypatch.setattr(migration_script.config, "PROJECTS_DIR", project_root)

    old_project_id = build_owner_scoped_project_id("yt", _static_subject("legacy-token"), "video123")
    old_project_root = config.get_project_path(old_project_id)
    shorts_dir = old_project_root / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (shorts_dir / "clip.mp4").write_bytes(b"video")
    (shorts_dir / "clip.json").write_text(
        json.dumps({"render_metadata": {"project_id": old_project_id}}, ensure_ascii=False),
        encoding="utf-8",
    )
    ensure_project_manifest(old_project_id, owner_subject=_static_subject("legacy-token"), source="migration_test")

    summary = migration_script.migrate_project_owner(old_project_id, "clerk-user-123")

    new_project_id = str(summary["new_project_id"])
    new_project_root = config.get_project_path(new_project_id)
    assert not old_project_root.exists()
    assert new_project_root.exists()

    manifest = read_project_manifest(new_project_id)
    assert manifest is not None
    assert manifest.project_id == new_project_id
    assert manifest.owner_subject_hash == str(summary["new_owner_subject_hash"])

    payload = json.loads((new_project_root / "shorts" / "clip.json").read_text(encoding="utf-8"))
    assert payload["render_metadata"]["project_id"] == new_project_id
    assert summary["metadata_files_updated"] == 1
