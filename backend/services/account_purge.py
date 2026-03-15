"""Delete subject-owned runtime data while preserving security/audit logs."""

from __future__ import annotations

import shutil
from pathlib import Path

import backend.config as config
from backend.api.websocket import manager
from backend.services.ownership import build_subject_hash, scrub_support_grants_for_subject
from backend.services.social.store import get_social_store


def _delete_subject_projects(subject_hash: str) -> int:
    subject_dir = config.get_subject_projects_dir(subject_hash)
    if not subject_dir.exists():
        return 0

    deleted_projects = sum(1 for child in subject_dir.iterdir() if child.is_dir())
    shutil.rmtree(subject_dir)
    config.get_subject_projects_dir(subject_hash)
    return deleted_projects


async def purge_subject_data(subject: str) -> dict[str, int]:
    normalized_subject = (subject or "").strip()
    if not normalized_subject:
        raise ValueError("subject boş olamaz")

    subject_hash = build_subject_hash(normalized_subject)
    deleted_projects = _delete_subject_projects(subject_hash)
    deleted_social_rows = get_social_store().purge_subject_data(normalized_subject)
    cancelled_jobs = manager.purge_subject_jobs(normalized_subject)
    closed_websockets = await manager.close_subject_connections(normalized_subject)
    scrubbed_grants = scrub_support_grants_for_subject(normalized_subject)

    return {
        "deleted_projects": deleted_projects,
        "deleted_social_rows": deleted_social_rows,
        "cancelled_jobs": cancelled_jobs,
        "closed_websockets": closed_websockets,
        "scrubbed_grants": scrubbed_grants,
    }
