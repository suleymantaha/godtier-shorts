"""Ownership manifests and per-subject project access helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import backend.config as config


PROJECT_MANIFEST_SCHEMA_VERSION = 1
PROJECT_MANIFEST_FILENAME = "project_manifest.json"
DEFAULT_SUPPORT_GRANT_TTL_SECONDS = 24 * 60 * 60


@dataclass(slots=True)
class SupportGrant:
    support_subject_hash: str
    created_at: str
    expires_at: str
    granted_by_subject_hash: str


@dataclass(slots=True)
class ProjectOwnershipManifest:
    schema_version: int
    project_id: str
    owner_subject_hash: str
    status: str
    created_at: str
    source: str
    support_grants: list[SupportGrant] = field(default_factory=list)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subject_namespace_secret() -> str:
    return os.getenv("SUBJECT_NAMESPACE_SECRET", "godtier-shorts-dev-namespace")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_subject_hash(subject: str) -> str:
    normalized = subject.strip()
    if not normalized:
        raise ValueError("subject boş olamaz")

    digest = hmac.new(
        _subject_namespace_secret().encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def build_owner_scoped_project_id(prefix: str, subject: str, suffix: str) -> str:
    safe_prefix = config.sanitize_project_name(prefix)
    safe_suffix = config.sanitize_project_name(suffix)
    return f"{safe_prefix}_{build_subject_hash(subject)}_{safe_suffix}"


def is_support_subject_allowed(subject: str) -> bool:
    allowlist_raw = os.getenv("SUPPORT_SUBJECT_ALLOWLIST", "").strip()
    if not allowlist_raw:
        return False
    allowed_subjects = {item.strip() for item in allowlist_raw.split(",") if item.strip()}
    return subject in allowed_subjects


def project_manifest_path(project_id: str) -> Path:
    safe_project_id = config.sanitize_project_name(project_id)
    try:
        return config.get_project_path(safe_project_id, PROJECT_MANIFEST_FILENAME)
    except ValueError:
        return config.PROJECTS_DIR / safe_project_id / PROJECT_MANIFEST_FILENAME


def _grant_from_payload(payload: object) -> SupportGrant | None:
    if not isinstance(payload, dict):
        return None
    support_subject_hash = str(payload.get("support_subject_hash") or "").strip()
    created_at = str(payload.get("created_at") or "").strip()
    expires_at = str(payload.get("expires_at") or "").strip()
    granted_by_subject_hash = str(payload.get("granted_by_subject_hash") or "").strip()
    if not (support_subject_hash and created_at and expires_at and granted_by_subject_hash):
        return None
    return SupportGrant(
        support_subject_hash=support_subject_hash,
        created_at=created_at,
        expires_at=expires_at,
        granted_by_subject_hash=granted_by_subject_hash,
    )


def read_project_manifest(project_id: str) -> ProjectOwnershipManifest | None:
    path = project_manifest_path(project_id)
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as manifest_file:
        payload = json.load(manifest_file)

    if not isinstance(payload, dict):
        return None

    support_grants = [
        grant
        for grant_payload in payload.get("support_grants", [])
        if (grant := _grant_from_payload(grant_payload)) is not None
    ]
    try:
        return ProjectOwnershipManifest(
            schema_version=int(payload.get("schema_version") or PROJECT_MANIFEST_SCHEMA_VERSION),
            project_id=config.sanitize_project_name(str(payload.get("project_id") or project_id)),
            owner_subject_hash=str(payload.get("owner_subject_hash") or "").strip(),
            status=str(payload.get("status") or "").strip() or "quarantined",
            created_at=str(payload.get("created_at") or "").strip() or _utcnow_iso(),
            source=str(payload.get("source") or "").strip() or "unknown",
            support_grants=support_grants,
        )
    except ValueError:
        return None


def write_project_manifest(project_id: str, manifest: ProjectOwnershipManifest) -> ProjectOwnershipManifest:
    path = project_manifest_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as manifest_file:
        json.dump(
            {
                **asdict(manifest),
                "support_grants": [asdict(grant) for grant in manifest.support_grants],
            },
            manifest_file,
            ensure_ascii=False,
            indent=2,
        )
    return manifest


def create_project_manifest(
    project_id: str,
    *,
    owner_subject: str,
    source: str,
    status: str = "active",
) -> ProjectOwnershipManifest:
    safe_project_id = config.sanitize_project_name(project_id)
    return ProjectOwnershipManifest(
        schema_version=PROJECT_MANIFEST_SCHEMA_VERSION,
        project_id=safe_project_id,
        owner_subject_hash=build_subject_hash(owner_subject),
        status=status,
        created_at=_utcnow_iso(),
        source=source,
        support_grants=[],
    )


def ensure_project_manifest(
    project_id: str,
    *,
    owner_subject: str,
    source: str,
    status: str = "active",
) -> ProjectOwnershipManifest:
    existing = read_project_manifest(project_id)
    if existing is not None:
        return existing
    manifest = create_project_manifest(project_id, owner_subject=owner_subject, source=source, status=status)
    return write_project_manifest(project_id, manifest)


def quarantine_project(project_id: str, *, source: str = "legacy_quarantine") -> ProjectOwnershipManifest:
    manifest = ProjectOwnershipManifest(
        schema_version=PROJECT_MANIFEST_SCHEMA_VERSION,
        project_id=config.sanitize_project_name(project_id),
        owner_subject_hash="",
        status="quarantined",
        created_at=_utcnow_iso(),
        source=source,
        support_grants=[],
    )
    return write_project_manifest(project_id, manifest)


def resolve_project_access(project_id: str, subject: str, *, now: datetime | None = None) -> tuple[bool, str, ProjectOwnershipManifest | None]:
    manifest = read_project_manifest(project_id)
    if manifest is None:
        return False, "missing_manifest", None
    if manifest.status != "active":
        return False, f"status_{manifest.status}", manifest

    subject_hash = build_subject_hash(subject)
    if manifest.owner_subject_hash == subject_hash:
        return True, "owner_match", manifest

    current_time = now or datetime.now(timezone.utc)
    for grant in manifest.support_grants:
        expires_at = _parse_iso(grant.expires_at)
        if grant.support_subject_hash == subject_hash and expires_at and expires_at > current_time:
            return True, "support_grant", manifest

    return False, "owner_mismatch", manifest


def grant_support_access(
    project_id: str,
    *,
    owner_subject: str,
    support_subject: str,
    ttl_seconds: int = DEFAULT_SUPPORT_GRANT_TTL_SECONDS,
) -> ProjectOwnershipManifest:
    manifest = read_project_manifest(project_id)
    if manifest is None or manifest.status != "active":
        raise ValueError("Support grant için aktif manifest gerekli")

    owner_hash = build_subject_hash(owner_subject)
    if manifest.owner_subject_hash != owner_hash:
        raise PermissionError("Sadece içerik sahibi support grant verebilir")

    created_at = datetime.now(timezone.utc)
    normalized_grant = SupportGrant(
        support_subject_hash=build_subject_hash(support_subject),
        created_at=created_at.isoformat(),
        expires_at=datetime.fromtimestamp(
            created_at.timestamp() + max(1, ttl_seconds),
            tz=timezone.utc,
        ).isoformat(),
        granted_by_subject_hash=owner_hash,
    )
    remaining = [
        existing
        for existing in manifest.support_grants
        if existing.support_subject_hash != normalized_grant.support_subject_hash
    ]
    manifest.support_grants = [*remaining, normalized_grant]
    return write_project_manifest(project_id, manifest)


def revoke_support_access(project_id: str, *, owner_subject: str, support_subject: str) -> ProjectOwnershipManifest:
    manifest = read_project_manifest(project_id)
    if manifest is None:
        raise ValueError("Manifest bulunamadı")

    owner_hash = build_subject_hash(owner_subject)
    if manifest.owner_subject_hash != owner_hash:
        raise PermissionError("Sadece içerik sahibi support grant kaldırabilir")

    support_hash = build_subject_hash(support_subject)
    manifest.support_grants = [
        grant
        for grant in manifest.support_grants
        if grant.support_subject_hash != support_hash
    ]
    return write_project_manifest(project_id, manifest)


def scrub_support_grants_for_subject(subject: str) -> int:
    subject_hash = build_subject_hash(subject)
    scrubbed = 0
    for project_dir in config.iter_project_dirs():
        manifest = read_project_manifest(project_dir.name)
        if manifest is None or not manifest.support_grants:
            continue
        remaining = [
            grant
            for grant in manifest.support_grants
            if grant.support_subject_hash != subject_hash
        ]
        removed = len(manifest.support_grants) - len(remaining)
        if removed <= 0:
            continue
        manifest.support_grants = remaining
        write_project_manifest(project_dir.name, manifest)
        scrubbed += removed
    return scrubbed


def list_accessible_project_ids(subject: str, *, include_quarantined: bool = False) -> list[str]:
    if not config.PROJECTS_DIR.exists():
        return []

    project_ids: list[str] = []
    for project_dir in config.iter_project_dirs():
        allowed, reason, _manifest = resolve_project_access(project_dir.name, subject)
        if allowed or (include_quarantined and reason.startswith("status_")):
            project_ids.append(project_dir.name)
    return project_ids


def quarantine_legacy_projects() -> list[str]:
    if not config.PROJECTS_DIR.exists():
        return []

    quarantined: list[str] = []
    for project_dir in sorted(config.PROJECTS_DIR.iterdir(), key=lambda path: path.name):
        if not project_dir.is_dir():
            continue
        try:
            config.sanitize_subject_hash(project_dir.name)
        except ValueError:
            if read_project_manifest(project_dir.name) is not None:
                continue
            quarantine_project(project_dir.name)
            quarantined.append(project_dir.name)
    return quarantined
