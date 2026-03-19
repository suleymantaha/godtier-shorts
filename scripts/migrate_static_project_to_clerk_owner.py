#!/usr/bin/env python3
"""Migrate an owner-scoped project from a static-token subject to a Clerk subject."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.config as config
from backend.services.ownership import (
    build_subject_hash,
    read_project_manifest,
    write_project_manifest,
)


def _resolve_project_root(project_id: str) -> Path:
    return config.get_project_path(project_id)


def _build_reassigned_project_id(project_id: str, new_owner_subject: str) -> str:
    safe_project_id = config.sanitize_project_name(project_id)
    old_hash = config.extract_subject_hash_from_project_id(safe_project_id)
    new_hash = build_subject_hash(new_owner_subject)
    if old_hash == new_hash:
        return safe_project_id
    return safe_project_id.replace(old_hash, new_hash, 1)


def _rewrite_clip_metadata_project_ids(shorts_dir: Path, new_project_id: str) -> int:
    updated_files = 0
    for metadata_path in sorted(shorts_dir.glob("*.json")):
        with open(metadata_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            continue

        render_metadata = payload.get("render_metadata")
        if not isinstance(render_metadata, dict):
            continue

        if render_metadata.get("project_id") == new_project_id:
            continue

        render_metadata["project_id"] = new_project_id
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=4)
        updated_files += 1

    return updated_files


def migrate_project_owner(old_project_id: str, new_owner_subject: str) -> dict[str, object]:
    safe_old_project_id = config.sanitize_project_name(old_project_id)
    old_root = _resolve_project_root(safe_old_project_id)
    if not old_root.exists() or not old_root.is_dir():
        raise FileNotFoundError(f"Project not found: {safe_old_project_id}")

    new_project_id = _build_reassigned_project_id(safe_old_project_id, new_owner_subject)
    if new_project_id == safe_old_project_id:
        raise ValueError("Project already belongs to the requested subject")

    new_root = _resolve_project_root(new_project_id)
    if new_root.exists():
        raise FileExistsError(f"Destination project already exists: {new_project_id}")

    new_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_root), str(new_root))

    manifest = read_project_manifest(new_project_id)
    if manifest is None:
        raise FileNotFoundError(f"Manifest missing after move: {new_project_id}")
    manifest.project_id = new_project_id
    manifest.owner_subject_hash = build_subject_hash(new_owner_subject)
    write_project_manifest(new_project_id, manifest)

    metadata_updated = _rewrite_clip_metadata_project_ids(new_root / "shorts", new_project_id)

    return {
        "metadata_files_updated": metadata_updated,
        "new_owner_subject_hash": manifest.owner_subject_hash,
        "new_project_id": new_project_id,
        "old_project_id": safe_old_project_id,
    }


def main(argv: list[str] | None = None) -> dict[str, object]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="existing owner-scoped project id")
    parser.add_argument("--new-owner-subject", required=True, help="target Clerk subject")
    parser.add_argument("--yes", action="store_true", help="apply the migration")
    args = parser.parse_args(argv)
    if not args.yes:
        raise SystemExit("Refusing to migrate project owner without --yes")

    summary = migrate_project_owner(args.project, args.new_owner_subject)
    for key, value in summary.items():
        print(f"{key}={value}")
    return summary


if __name__ == "__main__":
    main()
