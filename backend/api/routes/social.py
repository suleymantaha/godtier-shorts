"""Social publishing endpoints (Postiz integration + scheduling)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.api.security import AuthContext, ensure_project_access, require_policy
from backend.config import get_project_path, sanitize_clip_name, sanitize_project_name
from backend.core.exceptions import InvalidInputError
from backend.services.social.constants import SOCIAL_PROVIDER_POSTIZ, SUPPORTED_SOCIAL_PLATFORMS
from backend.services.social.crypto import SocialCrypto, get_social_connection_mode
from backend.services.social.postiz import build_postiz_oauth_authorize_url, exchange_postiz_oauth_code
from backend.services.social.providers import get_primary_postiz_integration
from backend.services.social.repository import get_social_repository
from backend.services.social.scheduler import get_social_scheduler
from backend.services.social.service import (
    build_signed_social_oauth_state,
    build_signed_social_oauth_subject_token,
    build_clip_prefill,
    create_scheduled_post_now,
    delete_scheduled_post_from_postiz,
    dry_run_publish_via_postiz,
    get_postiz_client_for_subject,
    has_postiz_credential_configured,
    _is_future_scheduled_job,
    normalize_postiz_accounts,
    normalize_social_oauth_integration,
    resolve_signed_social_oauth_state,
    resolve_signed_social_oauth_subject_token,
    resolve_signed_social_export_token,
    validate_publish_targets_for_subject,
    validate_postiz_credential,
)
from backend.services.social.store import get_social_store

router = APIRouter(prefix="/api/social", tags=["social"])


class SocialCredentialRequest(BaseModel):
    provider: Literal["postiz"] = SOCIAL_PROVIDER_POSTIZ
    api_key: str = Field(..., min_length=8)


class SocialDraftRequest(BaseModel):
    project_id: str
    clip_name: str
    platforms: dict[str, dict[str, Any]]

    @field_validator("project_id")
    @classmethod
    def validate_project(cls, value: str) -> str:
        return sanitize_project_name(value)

    @field_validator("clip_name")
    @classmethod
    def validate_clip(cls, value: str) -> str:
        return sanitize_clip_name(value)


class SocialPublishTarget(BaseModel):
    account_id: str = Field(..., min_length=1)
    platform: str
    provider: str | None = None

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        if value not in SUPPORTED_SOCIAL_PLATFORMS:
            raise ValueError("Desteklenmeyen platform")
        return value


class SocialPublishRequest(BaseModel):
    project_id: str
    clip_name: str
    mode: Literal["now", "scheduled"] = "now"
    scheduled_at: str | None = None
    timezone: str | None = None
    approval_required: bool = False
    targets: list[SocialPublishTarget]
    content_by_platform: dict[str, dict[str, Any]]

    @field_validator("project_id")
    @classmethod
    def validate_project(cls, value: str) -> str:
        return sanitize_project_name(value)

    @field_validator("clip_name")
    @classmethod
    def validate_clip(cls, value: str) -> str:
        return sanitize_clip_name(value)

    @model_validator(mode="after")
    def validate_scheduling(self) -> "SocialPublishRequest":
        if self.mode == "scheduled" and not self.scheduled_at:
            raise ValueError("scheduled_at zorunlu")
        if not self.targets:
            raise ValueError("En az bir hedef hesap gerekli")
        return self


class SocialPublishDryRunRequest(SocialPublishRequest):
    probe_media_upload: bool = False


class JobActionResponse(BaseModel):
    status: str
    job_id: str


class SocialConnectionStartRequest(BaseModel):
    platform: str
    return_url: str | None = None

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        if value not in SUPPORTED_SOCIAL_PLATFORMS:
            raise ValueError("Desteklenmeyen platform")
        return value


class SocialCalendarUpdateRequest(BaseModel):
    scheduled_at: str
    timezone: str | None = None


# --- Helpers -----------------------------------------------------------------


def _parse_scheduled_at_utc(raw: str | None, timezone_name: str | None) -> str | None:
    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidInputError("Geçersiz scheduled_at formatı") from exc

    if dt.tzinfo is None:
        tz_name = timezone_name or "UTC"
        try:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        except Exception as exc:
            raise InvalidInputError("Geçersiz timezone") from exc

    return dt.astimezone(timezone.utc).isoformat()


def _serialize_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for account in accounts:
        compact.append(
            {
                "id": account.get("id"),
                "name": account.get("name"),
                "platform": account.get("platform"),
                "provider": account.get("provider"),
                "username": account.get("username"),
                "avatar_url": account.get("avatar_url"),
                "health_status": account.get("health_status"),
                "health_error": account.get("health_error"),
                "requires_reconnect": bool(account.get("requires_reconnect")),
            }
        )
    return compact


def _read_social_oauth_config() -> dict[str, str]:
    client_id = os.getenv("POSTIZ_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("POSTIZ_OAUTH_CLIENT_SECRET", "").strip()
    callback_url = os.getenv("SOCIAL_OAUTH_CALLBACK_URL", "").strip()
    return_url = os.getenv("SOCIAL_OAUTH_RETURN_URL", "").strip()
    if not return_url:
        return_url = os.getenv("FRONTEND_URL", "").strip()

    if not client_id or not client_secret or not callback_url or not return_url:
        raise ValueError(
            "POSTIZ_OAUTH_CLIENT_ID, POSTIZ_OAUTH_CLIENT_SECRET, "
            "SOCIAL_OAUTH_CALLBACK_URL ve SOCIAL_OAUTH_RETURN_URL zorunlu"
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "callback_url": callback_url,
        "return_url": return_url,
    }


def _append_return_query(url: str, **params: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _build_social_oauth_return_url(status: Literal["success", "error"]) -> str:
    config = _read_social_oauth_config()
    return _append_return_query(config["return_url"], social_oauth=status)


def _build_social_suite_return_url(
    status: Literal["success", "error", "pending"],
    *,
    base_url: str | None = None,
    platform: str | None = None,
    session_id: str | None = None,
) -> str:
    if base_url is None:
        config = _read_social_oauth_config()
        base_url = config["return_url"]
    return _append_return_query(
        base_url,
        social_connect=status,
        platform=platform or "",
        session_id=session_id or "",
    )


def _resolve_connection_session_return_url(session_id: str | None) -> str | None:
    if not session_id:
        return None
    repository = get_social_repository()
    session = repository.get_connection_session(session_id)
    if session is None:
        return None
    return str(session.get("return_url") or "").strip() or None


def _resolve_postiz_connect_url(subject: str) -> str | None:
    try:
        _read_social_oauth_config()
        token = build_signed_social_oauth_subject_token(subject=subject, integration="youtube")
    except Exception:
        return None
    return f"/api/social/oauth/start?integration=youtube&subject_token={token}"


def _build_social_oauth_start_url(
    request: Request,
    *,
    integration: str,
    subject_token: str,
    platform: str | None = None,
    connection_session_id: str | None = None,
) -> str:
    params = {
        "integration": integration,
        "subject_token": subject_token,
    }
    if platform:
        params["platform"] = platform
    if connection_session_id:
        params["connection_session_id"] = connection_session_id
    return str(request.url_for("start_social_oauth").include_query_params(**params))


# --- Endpoints ---------------------------------------------------------------


@router.post("/credentials")
async def save_social_credentials(
    payload: SocialCredentialRequest,
    auth: AuthContext = Depends(require_policy("social_connect")),
) -> dict:
    if get_social_connection_mode() != "manual_api_key":
        raise HTTPException(
            status_code=403,
            detail="Bu ortamda manuel Postiz API key baglantisi kapali",
        )

    try:
        accounts = await asyncio.to_thread(
            validate_postiz_credential,
            payload.api_key,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Postiz doğrulaması başarısız: {exc}") from exc

    store = get_social_store()
    crypto = SocialCrypto()
    store.save_credential(
        auth.subject,
        payload.provider,
        crypto.encrypt(payload.api_key),
        None,
    )

    return {
        "status": "connected",
        "provider": payload.provider,
        "accounts": _serialize_accounts(accounts),
    }


@router.delete("/credentials")
async def delete_social_credentials(
    provider: Literal["postiz"] = Query(default=SOCIAL_PROVIDER_POSTIZ),
    auth: AuthContext = Depends(require_policy("social_connect")),
) -> dict:
    store = get_social_store()
    removed = store.delete_credential(auth.subject, provider)
    return {
        "status": "deleted" if removed else "not_found",
        "provider": provider,
    }


@router.get("/oauth/start")
async def start_social_oauth(
    integration: str = Query(default="youtube"),
    subject_token: str = Query(..., min_length=24),
    platform: str | None = Query(default=None),
    connection_session_id: str | None = Query(default=None),
) -> RedirectResponse:
    try:
        config = _read_social_oauth_config()
        normalized_integration = normalize_social_oauth_integration(integration)
        subject_payload = resolve_signed_social_oauth_subject_token(subject_token)
        if subject_payload["integration"] != normalized_integration:
            raise ValueError("OAuth integration uyuşmazlığı")
        state = build_signed_social_oauth_state(
            subject=subject_payload["subject"],
            integration=normalized_integration,
            target_platform=platform,
            connection_session_id=connection_session_id,
        )
        authorize_url = build_postiz_oauth_authorize_url(
            client_id=config["client_id"],
            redirect_uri=config["callback_url"],
            integration=normalized_integration,
            state=state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OAuth başlatılamadı: {exc}") from exc

    return RedirectResponse(url=authorize_url, status_code=307)


@router.get("/oauth/callback")
async def social_oauth_callback(
    state: str = Query(..., min_length=24),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    try:
        config = _read_social_oauth_config()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    error_redirect = _build_social_oauth_return_url("error")

    try:
        state_payload = resolve_signed_social_oauth_state(state)
    except ValueError:
        return RedirectResponse(url=error_redirect, status_code=307)

    if error or not code:
        logger.warning(
            "social_oauth_callback_failed integration={} error={} description={}",
            state_payload["integration"],
            error,
            error_description,
        )
        return RedirectResponse(url=error_redirect, status_code=307)

    try:
        token_payload = await asyncio.to_thread(
            exchange_postiz_oauth_code,
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            code=code,
            redirect_uri=config["callback_url"],
        )
        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Postiz access_token boş döndü")
        crypto = SocialCrypto()
        store = get_social_store()
        store.save_credential(
            state_payload["subject"],
            SOCIAL_PROVIDER_POSTIZ,
            crypto.encrypt(access_token),
            None,
        )
        repository = get_social_repository()
        session_id = str(state_payload.get("connection_session_id") or "").strip() or None
        target_platform = str(state_payload.get("target_platform") or "").strip() or None
        session_return_url = _resolve_connection_session_return_url(session_id)
        if session_id:
            repository.update_connection_session(
                session_id,
                phase="token_ready",
                status="pending_platform",
                last_error=None,
            )
        if session_id and target_platform:
            try:
                integration_key = get_primary_postiz_integration(target_platform)
                client, _ = get_postiz_client_for_subject(state_payload["subject"], store=store)
                launch_url = await asyncio.to_thread(client.get_connect_channel_url, integration_key)
                repository.update_connection_session(
                    session_id,
                    phase="launch_ready",
                    status="awaiting_user",
                    launch_url=launch_url,
                    last_error=None,
                )
                return RedirectResponse(url=launch_url, status_code=307)
            except Exception as exc:
                logger.warning(
                    "social.connection.callback launch_url_failed subject={} platform={} reason={}",
                    state_payload["subject"],
                    target_platform,
                    str(exc),
                )
                repository.update_connection_session(
                    session_id,
                    phase="launch_failed",
                    status="error",
                    last_error=str(exc),
                )
                return RedirectResponse(
                    url=_build_social_suite_return_url(
                        "error",
                        base_url=session_return_url,
                        platform=target_platform,
                        session_id=session_id,
                    ),
                    status_code=307,
                )
    except Exception as exc:
        logger.warning("social_oauth_callback_exchange_failed reason={}", str(exc))
        session_id = str(state_payload.get("connection_session_id") or "").strip() or None
        session_return_url = _resolve_connection_session_return_url(session_id)
        if session_id:
            return RedirectResponse(
                url=_build_social_suite_return_url(
                    "error",
                    base_url=session_return_url,
                    platform=str(state_payload.get("target_platform") or "").strip() or None,
                    session_id=session_id,
                ),
                status_code=307,
            )
        return RedirectResponse(url=error_redirect, status_code=307)

    success_redirect = _build_social_oauth_return_url("success")
    if session_id:
        return RedirectResponse(
            url=_build_social_suite_return_url(
                "success",
                base_url=session_return_url,
                platform=target_platform,
                session_id=session_id,
            ),
            status_code=307,
        )
    return RedirectResponse(url=success_redirect, status_code=307)


@router.get("/accounts")
async def list_connected_accounts(
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    connection_mode = get_social_connection_mode()
    connect_url = _resolve_postiz_connect_url(auth.subject) if connection_mode == "managed" else None
    repository = get_social_repository()
    store = get_social_store()
    if not has_postiz_credential_configured(auth.subject, store=store):
        return {
            "connected": False,
            "connection_mode": connection_mode,
            "connect_url": connect_url,
            "provider": SOCIAL_PROVIDER_POSTIZ,
            "accounts": [],
    }

    accounts = repository.list_cached_accounts(auth.subject)
    if not accounts:
        try:
            accounts = await asyncio.to_thread(
                repository.sync_accounts_for_subject,
                auth.subject,
                resolve_client_for_subject=get_postiz_client_for_subject,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Postiz hesapları alınamadı: {exc}") from exc

    return {
        "connected": bool(accounts),
        "connection_mode": connection_mode,
        "connect_url": connect_url,
        "provider": SOCIAL_PROVIDER_POSTIZ,
        "accounts": _serialize_accounts(accounts),
    }


@router.get("/prefill")
async def get_social_prefill(
    request: Request,
    project_id: str,
    clip_name: str,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> dict:
    try:
        safe_project = sanitize_project_name(project_id)
        safe_clip = sanitize_clip_name(clip_name)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc

    ensure_project_access(request, auth, safe_project, clip_name=safe_clip)
    payload = build_clip_prefill(subject=auth.subject, project_id=safe_project, clip_name=safe_clip)
    return payload


@router.put("/drafts")
async def save_social_drafts(
    request: Request,
    payload: SocialDraftRequest,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> dict:
    for platform in payload.platforms.keys():
        if platform not in SUPPORTED_SOCIAL_PLATFORMS:
            raise InvalidInputError(f"Desteklenmeyen platform: {platform}")

    ensure_project_access(request, auth, payload.project_id, clip_name=payload.clip_name)
    store = get_social_store()
    store.upsert_drafts(
        auth.subject,
        payload.project_id,
        payload.clip_name,
        payload.platforms,
    )
    return {"status": "saved"}


@router.delete("/drafts")
async def delete_social_drafts(
    request: Request,
    project_id: str,
    clip_name: str,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> dict:
    try:
        safe_project = sanitize_project_name(project_id)
        safe_clip = sanitize_clip_name(clip_name)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc

    ensure_project_access(request, auth, safe_project, clip_name=safe_clip)
    store = get_social_store()
    deleted = store.delete_drafts(auth.subject, safe_project, safe_clip)
    return {
        "status": "deleted" if deleted else "not_found",
        "deleted": deleted,
    }


@router.post("/publish")
async def create_publish_jobs(
    request: Request,
    payload: SocialPublishRequest,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> dict:
    store = get_social_store()
    if not has_postiz_credential_configured(auth.subject, store=store):
        raise HTTPException(status_code=400, detail="Önce Postiz hesabını bağlamalısın")

    ensure_project_access(request, auth, payload.project_id, clip_name=payload.clip_name)
    scheduled_utc = _parse_scheduled_at_utc(payload.scheduled_at, payload.timezone)
    if payload.mode == "scheduled" and scheduled_utc is None:
        raise InvalidInputError("scheduled_at zorunlu")

    try:
        targets = await asyncio.to_thread(
            validate_publish_targets_for_subject,
            subject=auth.subject,
            targets=[target.model_dump() for target in payload.targets],
            store=store,
            resolve_client_for_subject=get_postiz_client_for_subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    created = store.create_publish_jobs(
        subject=auth.subject,
        provider=SOCIAL_PROVIDER_POSTIZ,
        project_id=payload.project_id,
        clip_name=payload.clip_name,
        mode=payload.mode,
        timezone_name=payload.timezone,
        scheduled_at=scheduled_utc,
        approval_required=payload.approval_required,
        targets=targets,
        content_by_platform=payload.content_by_platform,
    )

    errors: list[dict[str, str]] = []
    jobs = created

    if payload.mode == "scheduled" and not payload.approval_required:
        jobs = []
        for item in created:
            latest_job = store.get_publish_job(item["id"])
            if latest_job is None:
                continue
            try:
                await asyncio.to_thread(create_scheduled_post_now, latest_job, store=store)
            except Exception as exc:
                errors.append({"job_id": str(item["id"]), "error": str(exc)})
            refreshed = store.get_publish_job(str(item["id"]))
            if refreshed is not None:
                jobs.append(refreshed)

    # Fast feedback: process immediate jobs without waiting next scheduler cycle.
    if payload.mode == "now" and not payload.approval_required:
        scheduler = get_social_scheduler()
        asyncio.create_task(scheduler.tick())

    return {
        "status": "partial_failure" if errors else ("scheduled" if payload.mode == "scheduled" and not payload.approval_required else "queued"),
        "jobs": [
            {
                "id": item["id"],
                "platform": item["platform"],
                "account_id": item["account_id"],
                "state": item["state"],
                "scheduled_at": item["scheduled_at"],
            }
            for item in jobs
        ],
        "errors": errors,
    }


@router.post("/publish/dry-run")
async def dry_run_publish(
    request: Request,
    payload: SocialPublishDryRunRequest,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> dict:
    store = get_social_store()
    if not has_postiz_credential_configured(auth.subject, store=store):
        raise HTTPException(status_code=400, detail="Önce Postiz hesabını bağlamalısın")

    ensure_project_access(request, auth, payload.project_id, clip_name=payload.clip_name)
    scheduled_utc = _parse_scheduled_at_utc(payload.scheduled_at, payload.timezone)
    if payload.mode == "scheduled" and scheduled_utc is None:
        raise InvalidInputError("scheduled_at zorunlu")

    try:
        preview = await asyncio.to_thread(
            dry_run_publish_via_postiz,
            subject=auth.subject,
            project_id=payload.project_id,
            clip_name=payload.clip_name,
            mode=payload.mode,
            scheduled_at=scheduled_utc,
            targets=[target.model_dump() for target in payload.targets],
            content_by_platform=payload.content_by_platform,
            probe_media_upload=payload.probe_media_upload,
            store=store,
            resolve_client_for_subject=get_postiz_client_for_subject,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Dry-run başarısız: {exc}") from exc

    return {
        "status": "ok",
        "dry_run": preview,
    }


@router.get("/export")
async def export_social_media(token: str = Query(..., min_length=8)) -> FileResponse:
    try:
        payload = resolve_signed_social_export_token(token)
        project_id = sanitize_project_name(str(payload["project_id"]))
        clip_name = sanitize_clip_name(str(payload["clip_name"]))
    except ValueError as exc:
        logger.warning("🔐 Security event=social_export_denied reason='{}' path=/api/social/export", str(exc))
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı") from exc

    clip_path = get_project_path(project_id, "shorts", clip_name)
    if not clip_path.exists():
        logger.warning(
            "🔐 Security event=social_export_denied reason='clip_missing' path=/api/social/export project_id={} clip_name={}",
            project_id,
            clip_name,
        )
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı")

    return FileResponse(path=str(clip_path), media_type="video/mp4", filename=clip_name)


@router.get("/publish-jobs")
async def list_publish_jobs(
    project_id: str | None = None,
    clip_name: str | None = None,
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    try:
        safe_project = sanitize_project_name(project_id) if project_id else None
        safe_clip = sanitize_clip_name(clip_name) if clip_name else None
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc
    repository = get_social_repository()
    await asyncio.to_thread(repository.sync_provider_jobs_for_subject, auth.subject)
    store = get_social_store()
    jobs = store.list_publish_jobs(auth.subject, project_id=safe_project, clip_name=safe_clip)
    return {"jobs": jobs}


@router.post("/publish-jobs/{job_id}/approve", response_model=JobActionResponse)
async def approve_publish_job(
    job_id: str,
    auth: AuthContext = Depends(require_policy("social_approve")),
) -> JobActionResponse:
    store = get_social_store()
    job = store.get_publish_job(job_id)
    if job is None or job.get("subject") != auth.subject:
        raise HTTPException(status_code=404, detail="Job bulunamadı")

    ok = store.approve_job(job_id, approver=auth.subject)
    if not ok:
        raise HTTPException(status_code=400, detail="Job onaylanamadı")

    approved_job = store.get_publish_job(job_id)
    if approved_job and _is_future_scheduled_job(approved_job):
        try:
            await asyncio.to_thread(create_scheduled_post_now, approved_job, store=store)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Postiz takvimine eklenemedi: {exc}") from exc
        return JobActionResponse(status="scheduled", job_id=job_id)

    scheduler = get_social_scheduler()
    asyncio.create_task(scheduler.tick())
    return JobActionResponse(status="approved", job_id=job_id)


@router.post("/publish-jobs/{job_id}/cancel", response_model=JobActionResponse)
async def cancel_publish_job(
    job_id: str,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> JobActionResponse:
    store = get_social_store()
    job = store.get_publish_job(job_id)
    if job is None or job.get("subject") != auth.subject:
        raise HTTPException(status_code=404, detail="Job bulunamadı")

    if job.get("state") == "scheduled" and job.get("provider_job_id"):
        try:
            await asyncio.to_thread(delete_scheduled_post_from_postiz, job, store=store)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Postiz takvimindeki yayın silinemedi: {exc}") from exc

    ok = store.cancel_job(job_id, subject=auth.subject)
    if not ok:
        raise HTTPException(status_code=400, detail="Job iptal edilemedi")
    return JobActionResponse(status="cancelled", job_id=job_id)


@router.get("/providers")
async def list_social_providers(
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    store = get_social_store()
    if has_postiz_credential_configured(auth.subject, store=store) and not repository.list_cached_accounts(auth.subject):
        try:
            await asyncio.to_thread(
                repository.sync_accounts_for_subject,
                auth.subject,
                resolve_client_for_subject=get_postiz_client_for_subject,
            )
        except Exception as exc:
            logger.warning("social.connection.sync initial_provider_sync_failed subject={} reason={}", auth.subject, str(exc))
    return {
        "providers": repository.list_provider_statuses(auth.subject),
        "connection_mode": get_social_connection_mode(),
    }


@router.get("/connections")
async def list_social_connections(
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    store = get_social_store()
    if has_postiz_credential_configured(auth.subject, store=store) and not repository.list_cached_accounts(auth.subject):
        try:
            accounts = await asyncio.to_thread(
                repository.sync_accounts_for_subject,
                auth.subject,
                resolve_client_for_subject=get_postiz_client_for_subject,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Bağlı hesaplar alınamadı: {exc}") from exc
    else:
        accounts = repository.list_cached_accounts(auth.subject)
    return {
        "accounts": _serialize_accounts(accounts),
        "providers": repository.list_provider_statuses(auth.subject),
        "connected": bool(accounts),
    }


@router.post("/connections/start")
async def start_social_connection(
    request: Request,
    payload: SocialConnectionStartRequest,
    auth: AuthContext = Depends(require_policy("social_connect")),
) -> dict:
    repository = get_social_repository()
    store = get_social_store()
    session = repository.create_connection_session(
        subject=auth.subject,
        platform=payload.platform,
        return_url=payload.return_url,
    )
    session_id = str(session["id"])
    launch_url: str

    if not has_postiz_credential_configured(auth.subject, store=store):
        subject_token = build_signed_social_oauth_subject_token(subject=auth.subject, integration="youtube")
        launch_url = _build_social_oauth_start_url(
            request,
            integration="youtube",
            subject_token=subject_token,
            platform=payload.platform,
            connection_session_id=session_id,
        )
        repository.update_connection_session(
            session_id,
            phase="oauth_required",
            status="pending",
            launch_url=launch_url,
            last_error=None,
        )
        logger.info("social.connection.start subject={} platform={} phase=oauth_required", auth.subject, payload.platform)
        return {
            "status": "oauth_required",
            "session_id": session_id,
            "launch_url": launch_url,
        }

    try:
        client, _ = get_postiz_client_for_subject(auth.subject, store=store)
        launch_url = await asyncio.to_thread(client.get_connect_channel_url, get_primary_postiz_integration(payload.platform))
    except Exception as exc:
        repository.update_connection_session(
            session_id,
            phase="launch_failed",
            status="error",
            last_error=str(exc),
        )
        raise HTTPException(status_code=502, detail=f"Bağlantı akışı başlatılamadı: {exc}") from exc

    repository.update_connection_session(
        session_id,
        phase="launch_ready",
        status="awaiting_user",
        launch_url=launch_url,
        last_error=None,
    )
    logger.info("social.connection.start subject={} platform={} phase=launch_ready", auth.subject, payload.platform)
    return {
        "status": "launch_ready",
        "session_id": session_id,
        "launch_url": launch_url,
    }


@router.get("/connections/callback")
async def social_connections_callback(
    session_id: str = Query(..., min_length=8),
    status: Literal["success", "error", "pending"] = Query(default="success"),
) -> RedirectResponse:
    repository = get_social_repository()
    session = repository.get_connection_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Connection session bulunamadı")
    repository.update_connection_session(
        session_id,
        phase="completed" if status == "success" else "callback",
        status=status,
        last_error=None if status != "error" else "Provider callback error",
    )
    return_url = str(session.get("return_url") or "").strip() or None
    return RedirectResponse(
        url=_build_social_suite_return_url(
            status,
            base_url=return_url,
            platform=str(session.get("platform") or ""),
            session_id=session_id,
        ),
        status_code=307,
    )


@router.post("/connections/sync")
async def sync_social_connections(
    auth: AuthContext = Depends(require_policy("social_connect")),
) -> dict:
    repository = get_social_repository()
    store = get_social_store()
    if not has_postiz_credential_configured(auth.subject, store=store):
        return {"status": "not_connected", "accounts": [], "providers": repository.list_provider_statuses(auth.subject)}
    try:
        accounts = await asyncio.to_thread(
            repository.sync_accounts_for_subject,
            auth.subject,
            resolve_client_for_subject=get_postiz_client_for_subject,
            reset_account_health=True,
        )
    except Exception as exc:
        logger.warning("social.connection.sync subject={} reason={}", auth.subject, str(exc))
        raise HTTPException(status_code=502, detail=f"Hesaplar senkronize edilemedi: {exc}") from exc
    logger.info("social.connection.sync subject={} account_count={}", auth.subject, len(accounts))
    return {
        "status": "synced",
        "accounts": _serialize_accounts(accounts),
        "providers": repository.list_provider_statuses(auth.subject),
    }


@router.delete("/connections/{account_id}")
async def delete_social_connection(
    account_id: str,
    auth: AuthContext = Depends(require_policy("social_connect")),
) -> dict:
    repository = get_social_repository()
    try:
        await asyncio.to_thread(
            repository.disconnect_account,
            subject=auth.subject,
            account_id=account_id,
            resolve_client_for_subject=get_postiz_client_for_subject,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Hesap bağlantısı kaldırılamadı: {exc}") from exc
    logger.info("social.connection.disconnect subject={} account_id={}", auth.subject, account_id)
    return {"status": "deleted", "account_id": account_id}


@router.get("/queue")
async def list_social_queue(
    state: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    return {"jobs": repository.list_queue(subject=auth.subject, state=state, platform=platform)}


@router.get("/calendar")
async def list_social_calendar(
    platform: str | None = Query(default=None),
    include_past: bool = Query(default=False),
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    return {
        "items": repository.list_calendar(subject=auth.subject, platform=platform, include_past=include_past)
    }


@router.patch("/calendar/{job_id}")
async def update_social_calendar_item(
    job_id: str,
    payload: SocialCalendarUpdateRequest,
    auth: AuthContext = Depends(require_policy("social_publish")),
) -> dict:
    repository = get_social_repository()
    scheduled_utc = _parse_scheduled_at_utc(payload.scheduled_at, payload.timezone)
    if scheduled_utc is None:
        raise InvalidInputError("scheduled_at zorunlu")
    updated = repository.update_calendar_job(
        subject=auth.subject,
        job_id=job_id,
        scheduled_at=scheduled_utc,
        timezone_name=payload.timezone,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Takvim öğesi bulunamadı")
    logger.info("social.calendar.update subject={} job_id={} scheduled_at={}", auth.subject, job_id, scheduled_utc)
    return {"status": "updated", "job": updated}


@router.get("/analytics/overview")
async def social_analytics_overview(
    refresh: bool = Query(default=False),
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    payload = await asyncio.to_thread(repository.refresh_analytics if refresh else repository.read_analytics, subject=auth.subject)
    logger.info("social.analytics.refresh subject={} refresh={}", auth.subject, refresh)
    return {"overview": payload["overview"], "platforms": payload["platforms"]}


@router.get("/analytics/accounts")
async def social_analytics_accounts(
    refresh: bool = Query(default=False),
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    payload = await asyncio.to_thread(repository.refresh_analytics if refresh else repository.read_analytics, subject=auth.subject)
    return {"accounts": payload["accounts"]}


@router.get("/analytics/posts")
async def social_analytics_posts(
    refresh: bool = Query(default=False),
    auth: AuthContext = Depends(require_policy("social_view_jobs")),
) -> dict:
    repository = get_social_repository()
    payload = await asyncio.to_thread(repository.refresh_analytics if refresh else repository.read_analytics, subject=auth.subject)
    return {"posts": payload["posts"]}
