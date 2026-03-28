"""Repository layer for native social-suite data access."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from .constants import PUBLISH_ACTIVE_STATES, SOCIAL_PROVIDER_POSTIZ
from .providers import list_social_provider_descriptors
from .service import get_postiz_client_for_subject, has_postiz_credential_configured, normalize_postiz_accounts, parse_iso
from .store import SocialStore, get_social_store


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


POSTIZ_SUCCESS_STATES = {"SUCCESS", "POSTED", "PUBLISHED", "DONE", "COMPLETED"}
POSTIZ_FAILURE_STATES = {"ERROR", "FAILED", "REJECTED"}
POSTIZ_SYNC_MIN_INTERVAL_SECONDS = 15
POSTIZ_STALLED_MINUTES = 15


def _normalize_postiz_state(value: Any) -> str:
    return str(value or "").strip().replace("-", "_").replace(" ", "_").upper()


def _extract_postiz_post_state(post: dict[str, Any]) -> str:
    for key in ("state", "status", "postStatus"):
        normalized = _normalize_postiz_state(post.get(key))
        if normalized:
            return normalized
    return ""


def _extract_postiz_post_published_at(post: dict[str, Any]) -> str | None:
    for key in ("publishedAt", "releaseDate", "releasedAt", "updatedAt", "publishDate", "createdAt"):
        value = str(post.get(key) or "").strip()
        if value:
            return value
    return None


def _extract_postiz_post_error(post: dict[str, Any]) -> str | None:
    for key in ("error", "errorMessage", "failureReason", "statusMessage", "message", "lastError"):
        value = str(post.get(key) or "").strip()
        if value:
            return value
    return None


def _job_anchor_datetime(job: dict[str, Any]) -> datetime:
    for key in ("scheduled_at", "published_at", "created_at"):
        value = parse_iso(str(job.get(key) or ""))
        if value is not None:
            return value
    return datetime.now(timezone.utc)


def _is_stalled_provider_job(job: dict[str, Any], *, now: datetime, publish_date: datetime | None) -> bool:
    due = publish_date
    if due is None:
        due = parse_iso(str(job.get("scheduled_at") or ""))
    if due is None and str(job.get("mode") or "") == "now":
        due = parse_iso(str(job.get("created_at") or ""))
    if due is None:
        return False
    return now - due >= timedelta(minutes=POSTIZ_STALLED_MINUTES)


def _build_sync_message(state: str, delivery_status: str, *, stale: bool = False) -> str:
    if state == "published":
        return "Provider yayını tamamladı"
    if state == "failed":
        return "Provider yayını başarısız oldu"
    if state == "scheduled":
        return "Postiz takviminde bekliyor"
    if stale or delivery_status == "stalled":
        return "Provider kuyruğunda uzun süredir bekliyor"
    return "Provider kuyruğunda işleniyor"


class SocialRepository:
    def __init__(self, store: SocialStore | None = None):
        self.store = store or get_social_store()
        self._last_provider_sync_by_subject: dict[str, datetime] = {}

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
        reset_account_health: bool = False,
    ) -> list[dict[str, Any]]:
        client, _credential = resolve_client_for_subject(subject, store=self.store)
        normalized = normalize_postiz_accounts(client.list_integrations())
        self.store.replace_account_cache(subject, normalized, reset_health=reset_account_health)
        self.store.touch_social_credential(subject, provider="postiz", synced_at=_utcnow_iso())
        return self.list_cached_accounts(subject)

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

    def _should_skip_provider_sync(self, subject: str, *, force: bool) -> bool:
        if force:
            return False
        last_sync = self._last_provider_sync_by_subject.get(subject)
        if last_sync is None:
            return False
        return (datetime.now(timezone.utc) - last_sync).total_seconds() < POSTIZ_SYNC_MIN_INTERVAL_SECONDS

    def _list_provider_posts_for_jobs(self, subject: str, jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        if not jobs or not has_postiz_credential_configured(subject, store=self.store):
            return {}

        anchors = [_job_anchor_datetime(job) for job in jobs]
        start_date = (min(anchors) - timedelta(days=7)).date().isoformat()
        end_date = (max(anchors) + timedelta(days=7)).date().isoformat()

        client, _credential = get_postiz_client_for_subject(subject, store=self.store)
        posts = client.list_posts(start_date=start_date, end_date=end_date)
        return {str(post.get("id") or "").strip(): post for post in posts if str(post.get("id") or "").strip()}

    def sync_provider_jobs_for_subject(self, subject: str, *, force: bool = False) -> list[dict[str, Any]]:
        if self._should_skip_provider_sync(subject, force=force):
            return []

        jobs = self.store.list_publish_jobs(subject, limit=300)
        tracked_jobs = [
            job for job in jobs
            if str(job.get("provider") or "") == SOCIAL_PROVIDER_POSTIZ
            and str(job.get("provider_job_id") or "").strip()
            and str(job.get("state") or "") != "cancelled"
        ]
        if not tracked_jobs:
            self._last_provider_sync_by_subject[subject] = datetime.now(timezone.utc)
            return []

        try:
            posts_by_id = self._list_provider_posts_for_jobs(subject, tracked_jobs)
        except Exception as exc:
            logger.warning("social.provider.sync_failed subject={} reason={}", subject, str(exc))
            return []
        now = datetime.now(timezone.utc)
        sync_mark = now.isoformat()
        updated_jobs: list[dict[str, Any]] = []

        for job in tracked_jobs:
            provider_job_id = str(job.get("provider_job_id") or "").strip()
            post = posts_by_id.get(provider_job_id)
            if post is None:
                continue

            provider_state = _extract_postiz_post_state(post)
            release_present = bool(post.get("releaseURL") or post.get("releaseId"))
            published_at: str | None = None
            provider_published_at = _extract_postiz_post_published_at(post)
            provider_error = _extract_postiz_post_error(post)
            publish_date = parse_iso(str(post.get("publishDate") or ""))

            next_state = str(job.get("state") or "publishing")
            delivery_status = str(job.get("delivery_status") or "pending") or "pending"
            last_error = str(job.get("last_error") or "").strip() or None
            stale = False

            if release_present or provider_state in POSTIZ_SUCCESS_STATES:
                next_state = "published"
                delivery_status = "published"
                last_error = None
                published_at = provider_published_at or sync_mark
            elif provider_state in POSTIZ_FAILURE_STATES:
                next_state = "failed"
                delivery_status = "failed"
                last_error = provider_error or "Provider yayını başarısız oldu. Hesabı yeniden bağlayın."
                self.store.mark_account_reconnect_required(
                    subject,
                    str(job.get("account_id") or ""),
                    error=last_error,
                )
            else:
                is_future = publish_date is not None and publish_date > now
                stale = _is_stalled_provider_job(job, now=now, publish_date=publish_date)
                if str(job.get("mode") or "") == "scheduled" and is_future:
                    next_state = "scheduled"
                    delivery_status = "scheduled"
                else:
                    next_state = "publishing"
                    delivery_status = "stalled" if stale else "pending"

            changed = any(
                [
                    next_state != str(job.get("state") or ""),
                    delivery_status != str(job.get("delivery_status") or ""),
                    (published_at or None) != (str(job.get("published_at") or "").strip() or None),
                    last_error != (str(job.get("last_error") or "").strip() or None),
                ]
            )

            self.store.update_publish_job(
                str(job["id"]),
                state=next_state,
                message=_build_sync_message(next_state, delivery_status, stale=stale),
                delivery_status=delivery_status,
                published_at=published_at,
                last_provider_sync_at=sync_mark,
                last_error=last_error,
                result=post,
                append_timeline=changed,
            )
            refreshed = self.store.get_publish_job(str(job["id"]))
            if refreshed is not None:
                updated_jobs.append(refreshed)

        self._last_provider_sync_by_subject[subject] = now
        return updated_jobs

    def list_calendar(
        self,
        *,
        subject: str,
        platform: str | None = None,
        include_past: bool = False,
    ) -> list[dict[str, Any]]:
        self.sync_provider_jobs_for_subject(subject)
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
        self.sync_provider_jobs_for_subject(subject)
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
        self.sync_provider_jobs_for_subject(subject, force=True)
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
        self.sync_provider_jobs_for_subject(subject)
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
