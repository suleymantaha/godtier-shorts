"""Repository layer for native social-suite data access."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .constants import PUBLISH_ACTIVE_STATES
from .providers import list_social_provider_descriptors
from .service import normalize_postiz_accounts, parse_iso
from .store import SocialStore, get_social_store


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialRepository:
    def __init__(self, store: SocialStore | None = None):
        self.store = store or get_social_store()

    def create_connection_session(
        self,
        *,
        subject: str,
        platform: str,
        return_url: str | None = None,
    ) -> dict[str, Any]:
        return self.store.create_connection_session(
            subject=subject,
            platform=platform,
            return_url=return_url,
        )

    def get_connection_session(self, session_id: str) -> dict[str, Any] | None:
        return self.store.get_connection_session(session_id)

    def update_connection_session(
        self,
        session_id: str,
        *,
        phase: str | None = None,
        status: str | None = None,
        launch_url: str | None = None,
        last_error: str | None = None,
    ) -> bool:
        return self.store.update_connection_session(
            session_id,
            phase=phase,
            status=status,
            launch_url=launch_url,
            last_error=last_error,
        )

    def sync_accounts_for_subject(
        self,
        subject: str,
        *,
        resolve_client_for_subject: Any,
    ) -> list[dict[str, Any]]:
        client, _credential = resolve_client_for_subject(subject, store=self.store)
        normalized = normalize_postiz_accounts(client.list_integrations())
        self.store.replace_account_cache(subject, normalized)
        self.store.touch_social_credential(subject, provider="postiz", synced_at=_utcnow_iso())
        return normalized

    def list_cached_accounts(self, subject: str) -> list[dict[str, Any]]:
        return self.store.list_account_cache(subject)

    def disconnect_account(
        self,
        *,
        subject: str,
        account_id: str,
        resolve_client_for_subject: Any,
    ) -> bool:
        client, _credential = resolve_client_for_subject(subject, store=self.store)
        client.delete_integration(account_id)
        self.store.mark_account_disconnected(subject, account_id)
        return True

    def list_provider_statuses(self, subject: str) -> list[dict[str, Any]]:
        accounts = self.list_cached_accounts(subject)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for account in accounts:
            grouped[str(account.get("platform") or "")].append(account)

        out: list[dict[str, Any]] = []
        for descriptor in list_social_provider_descriptors():
            provider_accounts = grouped.get(descriptor.platform, [])
            out.append(
                {
                    **descriptor.to_dict(),
                    "connected": any(not bool(item.get("disabled")) for item in provider_accounts),
                    "account_count": len(provider_accounts),
                    "accounts": provider_accounts,
                }
            )
        return out

    def list_calendar(
        self,
        *,
        subject: str,
        platform: str | None = None,
        include_past: bool = False,
    ) -> list[dict[str, Any]]:
        jobs = self.store.list_publish_jobs(subject, limit=300)
        now = datetime.now(timezone.utc)
        calendar_jobs: list[dict[str, Any]] = []
        for job in jobs:
            if job.get("mode") != "scheduled":
                continue
            if platform and job.get("platform") != platform:
                continue
            due = parse_iso(str(job.get("scheduled_at") or ""))
            if not include_past and due is not None and due < now and job.get("state") not in {"scheduled", "publishing"}:
                continue
            calendar_jobs.append(job)
        calendar_jobs.sort(key=lambda item: str(item.get("scheduled_at") or ""))
        return calendar_jobs

    def update_calendar_job(
        self,
        *,
        subject: str,
        job_id: str,
        scheduled_at: str,
        timezone_name: str | None,
    ) -> dict[str, Any] | None:
        job = self.store.get_publish_job(job_id)
        if job is None or str(job.get("subject")) != subject:
            return None
        self.store.reschedule_publish_job(job_id, scheduled_at=scheduled_at, timezone_name=timezone_name)
        return self.store.get_publish_job(job_id)

    def list_queue(
        self,
        *,
        subject: str,
        state: str | None = None,
        platform: str | None = None,
    ) -> list[dict[str, Any]]:
        jobs = self.store.list_publish_jobs(subject, limit=300)
        filtered: list[dict[str, Any]] = []
        for job in jobs:
            if state and job.get("state") != state:
                continue
            if platform and job.get("platform") != platform:
                continue
            filtered.append(job)
        return filtered

    def refresh_analytics(self, *, subject: str) -> dict[str, Any]:
        jobs = self.store.list_publish_jobs(subject, limit=500)
        accounts = self.list_cached_accounts(subject)
        account_names = {str(account.get("id")): str(account.get("name") or account.get("id")) for account in accounts}
        account_platforms = {str(account.get("id")): str(account.get("platform") or "") for account in accounts}

        totals = {
            "total_jobs": len(jobs),
            "published": 0,
            "failed": 0,
            "scheduled": 0,
            "active": 0,
            "approval_required": 0,
        }
        platform_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"platform": "", "total_jobs": 0, "published": 0, "failed": 0, "scheduled": 0, "active": 0}
        )
        account_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "account_id": "",
                "account_name": "",
                "platform": "",
                "total_jobs": 0,
                "published": 0,
                "failed": 0,
                "scheduled": 0,
                "active": 0,
            }
        )
        post_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "project_id": "",
                "clip_name": "",
                "platform": "",
                "account_id": "",
                "account_name": "",
                "total_jobs": 0,
                "published": 0,
                "failed": 0,
                "latest_state": "",
                "latest_at": "",
            }
        )

        for job in jobs:
            state = str(job.get("state") or "")
            platform = str(job.get("platform") or "")
            account_id = str(job.get("account_id") or "")
            totals["total_jobs"] += 0
            if state == "published":
                totals["published"] += 1
            if state == "failed":
                totals["failed"] += 1
            if state == "scheduled":
                totals["scheduled"] += 1
            if state in PUBLISH_ACTIVE_STATES:
                totals["active"] += 1
            if bool(job.get("approval_required")):
                totals["approval_required"] += 1

            platform_item = platform_metrics[platform]
            platform_item["platform"] = platform
            platform_item["total_jobs"] += 1
            if state == "published":
                platform_item["published"] += 1
            if state == "failed":
                platform_item["failed"] += 1
            if state == "scheduled":
                platform_item["scheduled"] += 1
            if state in PUBLISH_ACTIVE_STATES:
                platform_item["active"] += 1

            account_item = account_metrics[account_id]
            account_item["account_id"] = account_id
            account_item["account_name"] = account_names.get(account_id, account_id)
            account_item["platform"] = account_platforms.get(account_id, platform)
            account_item["total_jobs"] += 1
            if state == "published":
                account_item["published"] += 1
            if state == "failed":
                account_item["failed"] += 1
            if state == "scheduled":
                account_item["scheduled"] += 1
            if state in PUBLISH_ACTIVE_STATES:
                account_item["active"] += 1

            post_key = f"{job.get('project_id')}::{job.get('clip_name')}::{platform}::{account_id}"
            post_item = post_metrics[post_key]
            post_item["project_id"] = str(job.get("project_id") or "")
            post_item["clip_name"] = str(job.get("clip_name") or "")
            post_item["platform"] = platform
            post_item["account_id"] = account_id
            post_item["account_name"] = account_names.get(account_id, account_id)
            post_item["total_jobs"] += 1
            if state == "published":
                post_item["published"] += 1
            if state == "failed":
                post_item["failed"] += 1
            updated_at = str(job.get("updated_at") or "")
            if updated_at >= str(post_item.get("latest_at") or ""):
                post_item["latest_at"] = updated_at
                post_item["latest_state"] = state

        overview = {
            **totals,
            "connected_accounts": len([account for account in accounts if not account.get("disabled")]),
            "platforms_connected": len({account.get("platform") for account in accounts if not account.get("disabled")}),
            "generated_at": _utcnow_iso(),
        }
        payload = {
            "overview": overview,
            "accounts": sorted(account_metrics.values(), key=lambda item: (-int(item["published"]), item["account_name"])),
            "platforms": sorted(platform_metrics.values(), key=lambda item: item["platform"]),
            "posts": sorted(post_metrics.values(), key=lambda item: (-int(item["published"]), item["clip_name"])),
        }
        self.store.upsert_analytics_snapshot(subject, scope="overview", payload=overview)
        self.store.upsert_analytics_snapshot(subject, scope="accounts", payload={"accounts": payload["accounts"]})
        self.store.upsert_analytics_snapshot(subject, scope="posts", payload={"posts": payload["posts"]})
        self.store.upsert_dashboard_cache(subject, key="overview", payload=overview)
        return payload

    def read_analytics(self, *, subject: str) -> dict[str, Any]:
        overview = self.store.get_analytics_snapshot(subject, scope="overview") or self.store.get_dashboard_cache(subject, key="overview")
        accounts = self.store.get_analytics_snapshot(subject, scope="accounts")
        posts = self.store.get_analytics_snapshot(subject, scope="posts")
        if overview is None or accounts is None or posts is None:
            return self.refresh_analytics(subject=subject)
        return {
            "overview": overview,
            "accounts": list((accounts or {}).get("accounts") or []),
            "platforms": self.refresh_analytics(subject=subject)["platforms"],
            "posts": list((posts or {}).get("posts") or []),
        }


_repository_instance: SocialRepository | None = None


def get_social_repository() -> SocialRepository:
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = SocialRepository()
    return _repository_instance
