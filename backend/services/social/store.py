"""SQLite-backed persistence for social credentials, drafts, and publish jobs."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import METADATA_DIR

from .constants import PUBLISH_FINAL_STATES


DB_PATH = METADATA_DIR / "social_publish.db"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SocialStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS social_credentials (
                    subject TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    workspace_id TEXT,
                    token_source TEXT,
                    token_obtained_at TEXT,
                    last_validated_at TEXT,
                    last_synced_at TEXT,
                    revoked_at TEXT,
                    scopes_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (subject, provider)
                );

                CREATE TABLE IF NOT EXISTS social_drafts (
                    subject TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    clip_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (subject, project_id, clip_name, platform)
                );

                CREATE TABLE IF NOT EXISTS social_publish_jobs (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    clip_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    timezone TEXT,
                    scheduled_at TEXT,
                    approval_required INTEGER NOT NULL,
                    approved_at TEXT,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    provider_job_id TEXT,
                    delivery_status TEXT,
                    published_at TEXT,
                    last_provider_sync_at TEXT,
                    analytics_refreshed_at TEXT,
                    calendar_bucket TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    timeline_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS social_connection_sessions (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    return_url TEXT,
                    launch_url TEXT,
                    last_error TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS social_account_cache (
                    subject TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    provider TEXT,
                    name TEXT NOT NULL,
                    username TEXT,
                    avatar_url TEXT,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    health_status TEXT,
                    health_error TEXT,
                    health_updated_at TEXT,
                    raw_json TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    disconnected_at TEXT,
                    PRIMARY KEY (subject, account_id)
                );

                CREATE TABLE IF NOT EXISTS social_analytics_snapshots (
                    subject TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (subject, scope)
                );

                CREATE TABLE IF NOT EXISTS social_dashboard_cache (
                    subject TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (subject, cache_key)
                );

                CREATE INDEX IF NOT EXISTS idx_social_publish_jobs_subject
                    ON social_publish_jobs(subject, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_social_publish_jobs_state
                    ON social_publish_jobs(state, next_attempt_at);

                CREATE INDEX IF NOT EXISTS idx_social_account_cache_subject_platform
                    ON social_account_cache(subject, platform, disabled);

                CREATE INDEX IF NOT EXISTS idx_social_connection_sessions_subject
                    ON social_connection_sessions(subject, created_at DESC);
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(social_publish_jobs)").fetchall()
            }
            credential_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(social_credentials)").fetchall()
            }
            account_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(social_account_cache)").fetchall()
            }
            if "provider_job_id" not in columns:
                conn.execute("ALTER TABLE social_publish_jobs ADD COLUMN provider_job_id TEXT")
                columns.add("provider_job_id")
            if "delivery_status" not in columns:
                conn.execute("ALTER TABLE social_publish_jobs ADD COLUMN delivery_status TEXT")
                columns.add("delivery_status")
            if "published_at" not in columns:
                conn.execute("ALTER TABLE social_publish_jobs ADD COLUMN published_at TEXT")
                columns.add("published_at")
            if "last_provider_sync_at" not in columns:
                conn.execute("ALTER TABLE social_publish_jobs ADD COLUMN last_provider_sync_at TEXT")
                columns.add("last_provider_sync_at")
            if "analytics_refreshed_at" not in columns:
                conn.execute("ALTER TABLE social_publish_jobs ADD COLUMN analytics_refreshed_at TEXT")
                columns.add("analytics_refreshed_at")
            if "calendar_bucket" not in columns:
                conn.execute("ALTER TABLE social_publish_jobs ADD COLUMN calendar_bucket TEXT")
                columns.add("calendar_bucket")
            if "publer_job_id" in columns:
                conn.execute(
                    """
                    UPDATE social_publish_jobs
                    SET provider_job_id = COALESCE(provider_job_id, publer_job_id)
                    WHERE provider_job_id IS NULL
                    """
                )
            for column_name, ddl in (
                ("token_source", "ALTER TABLE social_credentials ADD COLUMN token_source TEXT"),
                ("token_obtained_at", "ALTER TABLE social_credentials ADD COLUMN token_obtained_at TEXT"),
                ("last_validated_at", "ALTER TABLE social_credentials ADD COLUMN last_validated_at TEXT"),
                ("last_synced_at", "ALTER TABLE social_credentials ADD COLUMN last_synced_at TEXT"),
                ("revoked_at", "ALTER TABLE social_credentials ADD COLUMN revoked_at TEXT"),
                ("scopes_json", "ALTER TABLE social_credentials ADD COLUMN scopes_json TEXT"),
            ):
                if column_name not in credential_columns:
                    conn.execute(ddl)
                    credential_columns.add(column_name)
            for column_name, ddl in (
                ("health_status", "ALTER TABLE social_account_cache ADD COLUMN health_status TEXT"),
                ("health_error", "ALTER TABLE social_account_cache ADD COLUMN health_error TEXT"),
                ("health_updated_at", "ALTER TABLE social_account_cache ADD COLUMN health_updated_at TEXT"),
            ):
                if column_name not in account_columns:
                    conn.execute(ddl)
                    account_columns.add(column_name)
            conn.commit()

    def save_credential(self, subject: str, provider: str, encrypted_api_key: str, workspace_id: str | None) -> None:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO social_credentials(
                    subject, provider, encrypted_api_key, workspace_id, token_source, token_obtained_at,
                    last_validated_at, last_synced_at, revoked_at, scopes_json, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject, provider)
                DO UPDATE SET
                    encrypted_api_key=excluded.encrypted_api_key,
                    workspace_id=excluded.workspace_id,
                    token_source=excluded.token_source,
                    token_obtained_at=excluded.token_obtained_at,
                    last_validated_at=excluded.last_validated_at,
                    revoked_at=excluded.revoked_at,
                    updated_at=excluded.updated_at
                """,
                (
                    subject,
                    provider,
                    encrypted_api_key,
                    workspace_id,
                    "oauth_or_api_key",
                    now,
                    now,
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()

    def get_credential(self, subject: str, provider: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM social_credentials WHERE subject = ? AND provider = ?",
                (subject, provider),
            ).fetchone()
        return dict(row) if row else None

    def delete_credential(self, subject: str, provider: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM social_credentials WHERE subject = ? AND provider = ?",
                (subject, provider),
            )
            conn.commit()
            return cur.rowcount > 0

    def touch_social_credential(
        self,
        subject: str,
        *,
        provider: str,
        validated_at: str | None = None,
        synced_at: str | None = None,
        revoked_at: str | None = None,
    ) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE social_credentials
                SET last_validated_at = COALESCE(?, last_validated_at),
                    last_synced_at = COALESCE(?, last_synced_at),
                    revoked_at = ?,
                    updated_at = ?
                WHERE subject = ? AND provider = ?
                """,
                (validated_at, synced_at, revoked_at, utcnow_iso(), subject, provider),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_drafts(self, subject: str, project_id: str, clip_name: str) -> dict[str, dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT platform, payload_json FROM social_drafts
                WHERE subject = ? AND project_id = ? AND clip_name = ?
                """,
                (subject, project_id, clip_name),
            ).fetchall()

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                out[row["platform"]] = json.loads(row["payload_json"])
            except ValueError:
                out[row["platform"]] = {}
        return out

    def upsert_drafts(
        self,
        subject: str,
        project_id: str,
        clip_name: str,
        drafts: dict[str, dict[str, Any]],
    ) -> None:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            for platform, payload in drafts.items():
                conn.execute(
                    """
                    INSERT INTO social_drafts(subject, project_id, clip_name, platform, payload_json, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(subject, project_id, clip_name, platform)
                    DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
                    """,
                    (subject, project_id, clip_name, platform, json.dumps(payload, ensure_ascii=False), now),
                )
            conn.commit()

    def delete_drafts(self, subject: str, project_id: str, clip_name: str) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM social_drafts
                WHERE subject = ? AND project_id = ? AND clip_name = ?
                """,
                (subject, project_id, clip_name),
            )
            conn.commit()
            return int(cur.rowcount or 0)

    def create_publish_jobs(
        self,
        *,
        subject: str,
        provider: str,
        project_id: str,
        clip_name: str,
        mode: str,
        timezone_name: str | None,
        scheduled_at: str | None,
        approval_required: bool,
        targets: list[dict[str, Any]],
        content_by_platform: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = utcnow_iso()
        next_attempt = scheduled_at or now
        state = "pending_approval" if approval_required else ("draft" if mode == "scheduled" else "queued")

        created: list[dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            for target in targets:
                job_id = uuid.uuid4().hex
                payload = {
                    "target": target,
                    "content": content_by_platform.get(target.get("platform", ""), {}),
                }
                timeline = [
                    {
                        "state": state,
                        "message": "Job oluşturuldu",
                        "at": now,
                    }
                ]
                row = {
                    "id": job_id,
                    "subject": subject,
                    "provider": provider,
                    "project_id": project_id,
                    "clip_name": clip_name,
                    "platform": str(target.get("platform") or ""),
                    "account_id": str(target.get("account_id") or ""),
                    "mode": mode,
                    "timezone": timezone_name,
                    "scheduled_at": scheduled_at,
                    "approval_required": 1 if approval_required else 0,
                    "approved_at": None,
                    "state": state,
                    "attempts": 0,
                    "next_attempt_at": next_attempt,
                    "idempotency_key": job_id,
                    "payload_json": json.dumps(payload, ensure_ascii=False),
                    "result_json": None,
                    "provider_job_id": None,
                    "delivery_status": "pending",
                    "published_at": None,
                    "last_provider_sync_at": None,
                    "analytics_refreshed_at": None,
                    "calendar_bucket": scheduled_at[:10] if scheduled_at else None,
                    "last_error": None,
                    "created_at": now,
                    "updated_at": now,
                    "timeline_json": json.dumps(timeline, ensure_ascii=False),
                }
                conn.execute(
                    """
                    INSERT INTO social_publish_jobs(
                        id, subject, provider, project_id, clip_name, platform, account_id, mode,
                        timezone, scheduled_at, approval_required, approved_at, state, attempts,
                        next_attempt_at, idempotency_key, payload_json, result_json, provider_job_id,
                        delivery_status, published_at, last_provider_sync_at, analytics_refreshed_at,
                        calendar_bucket, last_error, created_at, updated_at, timeline_json
                    ) VALUES (
                        :id, :subject, :provider, :project_id, :clip_name, :platform, :account_id, :mode,
                        :timezone, :scheduled_at, :approval_required, :approved_at, :state, :attempts,
                        :next_attempt_at, :idempotency_key, :payload_json, :result_json, :provider_job_id,
                        :delivery_status, :published_at, :last_provider_sync_at, :analytics_refreshed_at,
                        :calendar_bucket, :last_error, :created_at, :updated_at, :timeline_json
                    )
                    """,
                    row,
                )
                created.append(row)
            conn.commit()
        return created

    def _decode_job_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for field in ("payload_json", "result_json", "timeline_json"):
            raw = data.get(field)
            if raw:
                try:
                    data[field.replace("_json", "")] = json.loads(raw)
                except ValueError:
                    data[field.replace("_json", "")] = None
            else:
                data[field.replace("_json", "")] = None
            data.pop(field, None)
        data["approval_required"] = bool(data.get("approval_required"))
        if not data.get("provider_job_id") and data.get("publer_job_id"):
            data["provider_job_id"] = data.get("publer_job_id")
        return data

    def list_publish_jobs(
        self,
        subject: str,
        *,
        project_id: str | None = None,
        clip_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM social_publish_jobs WHERE subject = ?"
        args: list[Any] = [subject]
        if project_id:
            query += " AND project_id = ?"
            args.append(project_id)
        if clip_name:
            query += " AND clip_name = ?"
            args.append(clip_name)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, tuple(args)).fetchall()
        return [self._decode_job_row(row) for row in rows]

    def get_publish_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM social_publish_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._decode_job_row(row) if row else None

    def update_publish_job(
        self,
        job_id: str,
        *,
        state: str,
        message: str,
        next_attempt_at: str | None = None,
        last_error: str | None = None,
        provider_job_id: str | None = None,
        result: dict[str, Any] | None = None,
        delivery_status: str | None = None,
        published_at: str | None = None,
        last_provider_sync_at: str | None = None,
        analytics_refreshed_at: str | None = None,
        calendar_bucket: str | None = None,
        increment_attempt: bool = False,
        append_timeline: bool = True,
    ) -> bool:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT attempts, timeline_json FROM social_publish_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False

            attempts = int(row["attempts"] or 0)
            if increment_attempt:
                attempts += 1

            try:
                timeline = json.loads(row["timeline_json"] or "[]")
            except ValueError:
                timeline = []
            if append_timeline:
                timeline.append({"state": state, "message": message, "at": now})

            conn.execute(
                """
                UPDATE social_publish_jobs
                SET state = ?,
                    attempts = ?,
                    next_attempt_at = COALESCE(?, next_attempt_at),
                    last_error = ?,
                    provider_job_id = COALESCE(?, provider_job_id),
                    result_json = COALESCE(?, result_json),
                    delivery_status = COALESCE(?, delivery_status),
                    published_at = COALESCE(?, published_at),
                    last_provider_sync_at = COALESCE(?, last_provider_sync_at),
                    analytics_refreshed_at = COALESCE(?, analytics_refreshed_at),
                    calendar_bucket = COALESCE(?, calendar_bucket),
                    timeline_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    state,
                    attempts,
                    next_attempt_at,
                    last_error,
                    provider_job_id,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    delivery_status,
                    published_at,
                    last_provider_sync_at,
                    analytics_refreshed_at,
                    calendar_bucket,
                    json.dumps(timeline, ensure_ascii=False),
                    now,
                    job_id,
                ),
            )
            conn.commit()
            return True

    def reschedule_publish_job(self, job_id: str, *, scheduled_at: str, timezone_name: str | None) -> bool:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT timeline_json FROM social_publish_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False
            try:
                timeline = json.loads(row["timeline_json"] or "[]")
            except ValueError:
                timeline = []
            timeline.append({"state": "scheduled", "message": "Takvim zamanı güncellendi", "at": now})
            conn.execute(
                """
                UPDATE social_publish_jobs
                SET scheduled_at = ?,
                    timezone = ?,
                    state = CASE WHEN state = 'cancelled' THEN state ELSE 'scheduled' END,
                    next_attempt_at = ?,
                    calendar_bucket = ?,
                    timeline_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    scheduled_at,
                    timezone_name,
                    scheduled_at,
                    scheduled_at[:10],
                    json.dumps(timeline, ensure_ascii=False),
                    now,
                    job_id,
                ),
            )
            conn.commit()
            return True

    def list_due_jobs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM social_publish_jobs
                WHERE state IN ('queued', 'retrying')
                  AND next_attempt_at <= ?
                  AND (approval_required = 0 OR approved_at IS NOT NULL)
                ORDER BY next_attempt_at ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [self._decode_job_row(row) for row in rows]

    def approve_job(self, job_id: str, *, approver: str, force_queue: bool = False) -> bool:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT state, next_attempt_at, timeline_json FROM social_publish_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False
            if row["state"] in PUBLISH_FINAL_STATES:
                return False

            next_attempt = row["next_attempt_at"] or now
            due = parse_iso(next_attempt)
            is_due = due is None or due <= datetime.now(timezone.utc)
            next_state = "queued" if (force_queue or is_due) else "draft"

            try:
                timeline = json.loads(row["timeline_json"] or "[]")
            except ValueError:
                timeline = []
            timeline.append({"state": next_state, "message": f"Onaylandı: {approver}", "at": now})
            conn.execute(
                """
                UPDATE social_publish_jobs
                SET approved_at = ?,
                    state = ?,
                    timeline_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, next_state, json.dumps(timeline, ensure_ascii=False), now, job_id),
            )
            conn.commit()
            return True

    def cancel_job(self, job_id: str, *, subject: str) -> bool:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT state, timeline_json FROM social_publish_jobs WHERE id = ? AND subject = ?",
                (job_id, subject),
            ).fetchone()
            if row is None:
                return False
            if row["state"] in PUBLISH_FINAL_STATES or row["state"] == "publishing":
                return False

            try:
                timeline = json.loads(row["timeline_json"] or "[]")
            except ValueError:
                timeline = []
            timeline.append({"state": "cancelled", "message": "Kullanıcı tarafından iptal edildi", "at": now})

            conn.execute(
                """
                UPDATE social_publish_jobs
                SET state = 'cancelled',
                    updated_at = ?,
                    timeline_json = ?
                WHERE id = ? AND subject = ?
                """,
                (now, json.dumps(timeline, ensure_ascii=False), job_id, subject),
            )
            conn.commit()
            return True

    def purge_subject_data(self, subject: str) -> int:
        with self._lock, self._connect() as conn:
            credential_rows = conn.execute(
                "DELETE FROM social_credentials WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            draft_rows = conn.execute(
                "DELETE FROM social_drafts WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            publish_job_rows = conn.execute(
                "DELETE FROM social_publish_jobs WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            session_rows = conn.execute(
                "DELETE FROM social_connection_sessions WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            account_rows = conn.execute(
                "DELETE FROM social_account_cache WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            analytics_rows = conn.execute(
                "DELETE FROM social_analytics_snapshots WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            dashboard_rows = conn.execute(
                "DELETE FROM social_dashboard_cache WHERE subject = ?",
                (subject,),
            ).rowcount or 0
            conn.commit()
        return int(credential_rows + draft_rows + publish_job_rows + session_rows + account_rows + analytics_rows + dashboard_rows)

    def create_connection_session(
        self,
        *,
        subject: str,
        platform: str,
        return_url: str | None,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        payload = {
            "id": uuid.uuid4().hex,
            "subject": subject,
            "platform": platform,
            "phase": "created",
            "status": "pending",
            "return_url": return_url,
            "launch_url": None,
            "last_error": None,
            "expires_at": (now.timestamp() + ttl_seconds),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO social_connection_sessions(
                    id, subject, platform, phase, status, return_url, launch_url, last_error, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["subject"],
                    payload["platform"],
                    payload["phase"],
                    payload["status"],
                    payload["return_url"],
                    payload["launch_url"],
                    payload["last_error"],
                    str(payload["expires_at"]),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            conn.commit()
        return payload

    def get_connection_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM social_connection_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_connection_session(
        self,
        session_id: str,
        *,
        phase: str | None = None,
        status: str | None = None,
        launch_url: str | None = None,
        last_error: str | None = None,
    ) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE social_connection_sessions
                SET phase = COALESCE(?, phase),
                    status = COALESCE(?, status),
                    launch_url = COALESCE(?, launch_url),
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    phase,
                    status,
                    launch_url,
                    last_error,
                    utcnow_iso(),
                    session_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0

    def replace_account_cache(
        self,
        subject: str,
        accounts: list[dict[str, Any]],
        *,
        reset_health: bool = False,
    ) -> None:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            existing_ids = {
                row["account_id"]
                for row in conn.execute(
                    "SELECT account_id FROM social_account_cache WHERE subject = ?",
                    (subject,),
                ).fetchall()
            }
            seen_ids: set[str] = set()
            for account in accounts:
                account_id = str(account.get("id") or "").strip()
                if not account_id:
                    continue
                seen_ids.add(account_id)
                conn.execute(
                    (
                        """
                        INSERT INTO social_account_cache(
                            subject, account_id, platform, provider, name, username, avatar_url,
                            disabled, health_status, health_error, health_updated_at,
                            raw_json, last_seen_at, disconnected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(subject, account_id)
                        DO UPDATE SET
                            platform=excluded.platform,
                            provider=excluded.provider,
                            name=excluded.name,
                            username=excluded.username,
                            avatar_url=excluded.avatar_url,
                            disabled=excluded.disabled,
                            health_status='healthy',
                            health_error=NULL,
                            health_updated_at=excluded.last_seen_at,
                            raw_json=excluded.raw_json,
                            last_seen_at=excluded.last_seen_at,
                            disconnected_at=NULL
                        """
                        if reset_health
                        else
                        """
                        INSERT INTO social_account_cache(
                            subject, account_id, platform, provider, name, username, avatar_url,
                            disabled, health_status, health_error, health_updated_at,
                            raw_json, last_seen_at, disconnected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(subject, account_id)
                        DO UPDATE SET
                            platform=excluded.platform,
                            provider=excluded.provider,
                            name=excluded.name,
                            username=excluded.username,
                            avatar_url=excluded.avatar_url,
                            disabled=excluded.disabled,
                            health_status=COALESCE(social_account_cache.health_status, 'healthy'),
                            health_error=CASE
                                WHEN social_account_cache.health_status = 'reconnect_required'
                                THEN social_account_cache.health_error
                                ELSE NULL
                            END,
                            health_updated_at=CASE
                                WHEN social_account_cache.health_status = 'reconnect_required'
                                THEN COALESCE(social_account_cache.health_updated_at, excluded.last_seen_at)
                                ELSE NULL
                            END,
                            raw_json=excluded.raw_json,
                            last_seen_at=excluded.last_seen_at,
                            disconnected_at=NULL
                        """
                    ),
                    (
                        subject,
                        account_id,
                        str(account.get("platform") or ""),
                        str(account.get("provider") or "") or None,
                        str(account.get("name") or account_id),
                        account.get("username"),
                        account.get("avatar_url"),
                        1 if bool(account.get("disabled")) else 0,
                        "healthy",
                        None,
                        now,
                        json.dumps(account, ensure_ascii=False),
                        now,
                        None,
                    ),
                )
            stale_ids = existing_ids - seen_ids
            for account_id in stale_ids:
                conn.execute(
                    """
                    UPDATE social_account_cache
                    SET disabled = 1,
                        disconnected_at = COALESCE(disconnected_at, ?)
                    WHERE subject = ? AND account_id = ?
                    """,
                    (now, subject, account_id),
                )
            conn.commit()

    def list_account_cache(self, subject: str, *, include_disabled: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM social_account_cache WHERE subject = ?"
        params: list[Any] = [subject]
        if not include_disabled:
            query += " AND disabled = 0"
        query += " ORDER BY platform ASC, name ASC"
        with self._lock, self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["raw"] = json.loads(item.get("raw_json") or "{}")
            except ValueError:
                item["raw"] = {}
            item["id"] = item["account_id"]
            item["disabled"] = bool(item.get("disabled"))
            item["health_status"] = str(item.get("health_status") or "healthy")
            item["requires_reconnect"] = item["health_status"] == "reconnect_required"
            item.pop("raw_json", None)
            out.append(item)
        return out

    def mark_account_disconnected(self, subject: str, account_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE social_account_cache
                SET disabled = 1,
                    disconnected_at = COALESCE(disconnected_at, ?)
                WHERE subject = ? AND account_id = ?
                """,
                (utcnow_iso(), subject, account_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def mark_account_reconnect_required(
        self,
        subject: str,
        account_id: str,
        *,
        error: str | None = None,
    ) -> bool:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE social_account_cache
                SET health_status = 'reconnect_required',
                    health_error = ?,
                    health_updated_at = ?
                WHERE subject = ? AND account_id = ?
                """,
                (
                    error,
                    now,
                    subject,
                    account_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0

    def upsert_analytics_snapshot(self, subject: str, *, scope: str, payload: dict[str, Any]) -> None:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO social_analytics_snapshots(subject, scope, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subject, scope)
                DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
                """,
                (subject, scope, json.dumps(payload, ensure_ascii=False), now, now),
            )
            conn.commit()

    def get_analytics_snapshot(self, subject: str, *, scope: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM social_analytics_snapshots WHERE subject = ? AND scope = ?",
                (subject, scope),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["payload_json"] or "{}")
        except ValueError:
            return None

    def upsert_dashboard_cache(self, subject: str, *, key: str, payload: dict[str, Any]) -> None:
        now = utcnow_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO social_dashboard_cache(subject, cache_key, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(subject, cache_key)
                DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at
                """,
                (subject, key, json.dumps(payload, ensure_ascii=False), now),
            )
            conn.commit()

    def get_dashboard_cache(self, subject: str, *, key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM social_dashboard_cache WHERE subject = ? AND cache_key = ?",
                (subject, key),
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["payload_json"] or "{}")
        except ValueError:
            return None


_store_instance: SocialStore | None = None


def get_social_store() -> SocialStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = SocialStore()
    return _store_instance
