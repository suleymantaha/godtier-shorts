"""High-level social publishing orchestration helpers."""

from __future__ import annotations

import json
import os
import hmac
import hashlib
import base64
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from backend.config import get_project_path
from backend.services.ownership import build_subject_hash, read_project_manifest

from .constants import (
    MAX_DIRECT_UPLOAD_BYTES,
    PLATFORM_TO_POSTIZ,
    POSTIZ_TO_PLATFORM,
    SOCIAL_PROVIDER_POSTIZ,
    SUPPORTED_SOCIAL_PLATFORMS,
)
from .content import build_platform_prefill, resolve_clip_metadata_paths, resolve_viral_metadata
from .crypto import (
    SocialCrypto,
    get_social_encryption_secret,
    is_env_postiz_api_key_fallback_enabled,
)
from .postiz import PostizApiError, PostizClient
from .store import SocialStore, get_social_store, parse_iso


RETRY_BACKOFF_MINUTES = [1, 2, 4, 8, 16]
SUPPORTED_SOCIAL_OAUTH_INTEGRATIONS: set[str] = {"youtube"}


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge_prefill_with_drafts(
    prefill: dict[str, dict[str, Any]],
    drafts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for platform in SUPPORTED_SOCIAL_PLATFORMS:
        base = prefill.get(platform, {}).copy()
        patch = drafts.get(platform, {})
        if isinstance(patch, dict):
            base.update({k: v for k, v in patch.items() if v is not None})
        merged[platform] = base
    return merged


def build_clip_prefill(
    *,
    subject: str,
    project_id: str,
    clip_name: str,
    store: SocialStore | None = None,
) -> dict[str, Any]:
    db = store or get_social_store()
    clip_path, clip_meta_path = resolve_clip_metadata_paths(project_id, clip_name)
    clip_meta = _safe_read_json(clip_meta_path)

    viral_meta = resolve_viral_metadata(project_id, clip_name, clip_meta)
    platform_prefill = build_platform_prefill(viral_meta)

    drafts = db.get_drafts(subject, project_id, clip_name)
    merged = _merge_prefill_with_drafts(platform_prefill, drafts)

    return {
        "project_id": project_id,
        "clip_name": clip_name,
        "clip_exists": clip_path.exists(),
        "source": {
            "viral_metadata": viral_meta,
            "has_clip_metadata": bool(clip_meta),
            "has_drafts": bool(drafts),
        },
        "platforms": merged,
    }


def normalize_postiz_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for account in accounts:
        raw_provider = str(account.get("identifier") or account.get("provider") or account.get("type") or "").lower()
        platform = POSTIZ_TO_PLATFORM.get(raw_provider)
        if platform is None:
            continue

        account_id_raw = account.get("id")
        if account_id_raw is None:
            continue
        account_id = str(account_id_raw).strip()
        if not account_id:
            continue

        normalized.append(
            {
                "id": account_id,
                "name": str(account.get("name") or account.get("username") or account_id),
                "platform": platform,
                "provider": raw_provider,
                "username": account.get("username"),
                "avatar_url": account.get("picture") or account.get("avatar"),
                "raw": account,
            }
        )

    return normalized


def resolve_postiz_accounts_for_subject(
    subject: str,
    *,
    store: SocialStore | None = None,
    resolve_client_for_subject: Any | None = None,
) -> list[dict[str, Any]]:
    db = store or get_social_store()
    client_resolver = resolve_client_for_subject or get_postiz_client_for_subject
    client, _credential = client_resolver(subject, store=db)
    raw_accounts = client.list_integrations()
    return normalize_postiz_accounts(raw_accounts)


def validate_publish_targets_for_subject(
    *,
    subject: str,
    targets: list[dict[str, Any]],
    store: SocialStore | None = None,
    resolve_client_for_subject: Any | None = None,
) -> list[dict[str, Any]]:
    accounts = resolve_postiz_accounts_for_subject(
        subject,
        store=store,
        resolve_client_for_subject=resolve_client_for_subject,
    )
    accounts_by_id = {str(account["id"]): account for account in accounts}

    validated_targets: list[dict[str, Any]] = []
    for target in targets:
        account_id = str(target.get("account_id") or "").strip()
        platform = str(target.get("platform") or "").strip()
        provider = str(target.get("provider") or "").strip() or None
        if not account_id or not platform:
            raise ValueError("Hedef hesap bilgisi eksik")

        account = accounts_by_id.get(account_id)
        if account is None:
            raise ValueError(f"Hedef hesap bu kullanıcıya bağlı değil: {account_id}")

        account_platform = str(account.get("platform") or "").strip()
        if account_platform != platform:
            raise ValueError(
                f"Hedef hesap platformu uyuşmuyor: hesap={account_platform} istek={platform}"
            )

        account_provider = str(account.get("provider") or "").strip() or None
        if provider is not None and account_provider is not None and account_provider != provider:
            raise ValueError(
                f"Hedef hesap provider bilgisi uyuşmuyor: hesap={account_provider} istek={provider}"
            )

        validated_targets.append(
            {
                "account_id": account_id,
                "platform": account_platform,
                "provider": account_provider,
            }
        )

    return validated_targets


def get_postiz_api_key_from_env() -> str | None:
    if not is_env_postiz_api_key_fallback_enabled():
        return None
    value = os.getenv("POSTIZ_API_KEY", "").strip()
    return value or None


def has_postiz_credential_configured(subject: str, *, store: SocialStore | None = None) -> bool:
    db = store or get_social_store()
    return db.get_credential(subject, SOCIAL_PROVIDER_POSTIZ) is not None or get_postiz_api_key_from_env() is not None


def get_postiz_client_for_subject(subject: str, *, store: SocialStore | None = None, crypto: SocialCrypto | None = None) -> tuple[PostizClient, dict[str, Any]]:
    db = store or get_social_store()
    c = crypto or SocialCrypto()

    credential = db.get_credential(subject, SOCIAL_PROVIDER_POSTIZ)
    if credential is not None:
        api_key = c.decrypt(str(credential["encrypted_api_key"]))
        return PostizClient(api_key=api_key), credential

    env_api_key = get_postiz_api_key_from_env()
    if env_api_key:
        return (
            PostizClient(api_key=env_api_key),
            {
                "subject": subject,
                "provider": SOCIAL_PROVIDER_POSTIZ,
                "workspace_id": None,
                "source": "env",
            },
        )

    raise ValueError("Postiz credential bulunamadı")


def validate_postiz_credential(api_key: str) -> list[dict[str, Any]]:
    client = PostizClient(api_key=api_key)
    integrations = client.validate_connection()
    return normalize_postiz_accounts(integrations)


def compute_retry_eta(attempt: int) -> str:
    idx = max(0, min(attempt - 1, len(RETRY_BACKOFF_MINUTES) - 1))
    eta = datetime.now(timezone.utc) + timedelta(minutes=RETRY_BACKOFF_MINUTES[idx])
    return eta.isoformat()


def _build_media_url(project_id: str, clip_name: str) -> str:
    public_base = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    if not public_base:
        raise ValueError("PUBLIC_APP_URL tanımlı olmadığı için URL import kullanılamıyor")
    raise ValueError("Legacy public media URL kullanımı devre dışı")


def _get_social_export_ttl_seconds() -> int:
    raw = os.getenv("SOCIAL_EXPORT_TTL_SECONDS", "").strip()
    if not raw:
        return 900
    try:
        value = int(raw)
    except ValueError:
        return 900
    return value if value > 0 else 900


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _build_social_export_signature(payload_segment: str) -> str:
    secret = get_social_encryption_secret().encode("utf-8")
    digest = hmac.new(secret, payload_segment.encode("utf-8"), hashlib.sha256).digest()
    return _urlsafe_b64encode(digest)


def _sign_social_payload(payload: dict[str, Any]) -> str:
    payload_segment = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _build_social_export_signature(payload_segment)
    return f"{payload_segment}.{signature}"


def _resolve_signed_social_payload(token: str, *, expected_kind: str) -> dict[str, Any]:
    try:
        payload_segment, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Geçersiz signed token formatı") from exc

    expected_signature = _build_social_export_signature(payload_segment)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Geçersiz signed token imzası")

    try:
        payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Geçersiz signed token içeriği") from exc

    if not isinstance(payload, dict):
        raise ValueError("Geçersiz signed token içeriği")

    kind = str(payload.get("kind") or "").strip()
    if kind != expected_kind:
        raise ValueError("Geçersiz signed token tipi")

    exp = int(payload.get("exp") or 0)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if exp <= now_ts:
        raise ValueError("Signed token süresi doldu")

    return payload


def _get_social_oauth_state_ttl_seconds() -> int:
    raw = os.getenv("SOCIAL_OAUTH_STATE_TTL_SECONDS", "").strip()
    if not raw:
        return 600
    try:
        value = int(raw)
    except ValueError:
        return 600
    return value if value > 0 else 600


def normalize_social_oauth_integration(value: str) -> Literal["youtube"]:
    integration = str(value or "").strip().lower()
    if integration not in SUPPORTED_SOCIAL_OAUTH_INTEGRATIONS:
        raise ValueError("Desteklenmeyen social oauth integration")
    return "youtube"


def build_signed_social_oauth_subject_token(
    *,
    subject: str,
    integration: str,
    ttl_seconds: int | None = None,
) -> str:
    normalized_integration = normalize_social_oauth_integration(integration)
    expires_in = _get_social_oauth_state_ttl_seconds() if ttl_seconds is None else ttl_seconds
    payload = {
        "kind": "social_oauth_subject",
        "sub": str(subject),
        "integration": normalized_integration,
        "exp": int(datetime.now(timezone.utc).timestamp()) + expires_in,
    }
    return _sign_social_payload(payload)


def resolve_signed_social_oauth_subject_token(token: str) -> dict[str, str]:
    payload = _resolve_signed_social_payload(token, expected_kind="social_oauth_subject")
    subject = str(payload.get("sub") or "").strip()
    integration = normalize_social_oauth_integration(str(payload.get("integration") or ""))
    if not subject:
        raise ValueError("Social OAuth subject token alanları eksik")
    return {"subject": subject, "integration": integration}


def build_signed_social_oauth_state(
    *,
    subject: str,
    integration: str,
    ttl_seconds: int | None = None,
) -> str:
    normalized_integration = normalize_social_oauth_integration(integration)
    expires_in = _get_social_oauth_state_ttl_seconds() if ttl_seconds is None else ttl_seconds
    payload = {
        "kind": "social_oauth_state",
        "sub": str(subject),
        "integration": normalized_integration,
        "nonce": secrets.token_urlsafe(12),
        "exp": int(datetime.now(timezone.utc).timestamp()) + expires_in,
    }
    return _sign_social_payload(payload)


def resolve_signed_social_oauth_state(token: str) -> dict[str, str]:
    payload = _resolve_signed_social_payload(token, expected_kind="social_oauth_state")
    subject = str(payload.get("sub") or "").strip()
    integration = normalize_social_oauth_integration(str(payload.get("integration") or ""))
    if not subject:
        raise ValueError("Social OAuth state alanları eksik")
    return {"subject": subject, "integration": integration}


def build_signed_social_export_token(
    *,
    subject: str,
    project_id: str,
    clip_name: str,
    publish_job_id: str,
    ttl_seconds: int | None = None,
) -> str:
    expires_in = _get_social_export_ttl_seconds() if ttl_seconds is None else ttl_seconds
    payload = {
        "project_id": project_id,
        "clip_name": clip_name,
        "job_id": publish_job_id,
        "subject_hash": build_subject_hash(subject),
        "exp": int(datetime.now(timezone.utc).timestamp()) + expires_in,
    }
    payload_segment = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _build_social_export_signature(payload_segment)
    return f"{payload_segment}.{signature}"


def resolve_signed_social_export_token(token: str) -> dict[str, Any]:
    try:
        payload_segment, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Geçersiz social export token formatı") from exc

    expected_signature = _build_social_export_signature(payload_segment)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Geçersiz social export token imzası")

    try:
        payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Geçersiz social export token içeriği") from exc

    if not isinstance(payload, dict):
        raise ValueError("Geçersiz social export token içeriği")

    exp = int(payload.get("exp") or 0)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if exp <= now_ts:
        raise ValueError("Social export token süresi doldu")

    project_id = str(payload.get("project_id") or "").strip()
    clip_name = str(payload.get("clip_name") or "").strip()
    job_id = str(payload.get("job_id") or "").strip()
    subject_hash = str(payload.get("subject_hash") or "").strip()
    if not project_id or not clip_name or not job_id or not subject_hash:
        raise ValueError("Social export token alanları eksik")

    manifest = read_project_manifest(project_id)
    if manifest is None or manifest.status != "active":
        raise ValueError("Social export kaynağı kullanılamıyor")
    if manifest.owner_subject_hash != subject_hash:
        raise ValueError("Social export sahibi eşleşmiyor")

    return payload


def build_signed_social_export_url(
    *,
    subject: str,
    project_id: str,
    clip_name: str,
    publish_job_id: str,
    ttl_seconds: int | None = None,
) -> str:
    public_base = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    if not public_base:
        raise ValueError("PUBLIC_APP_URL tanımlı olmadığı için URL import kullanılamıyor")
    token = build_signed_social_export_token(
        subject=subject,
        project_id=project_id,
        clip_name=clip_name,
        publish_job_id=publish_job_id,
        ttl_seconds=ttl_seconds,
    )
    return f"{public_base}/api/social/export?token={token}"


def _resolve_media(
    client: PostizClient,
    clip_path: Path,
    *,
    subject: str,
    project_id: str,
    clip_name: str,
    publish_job_id: str,
) -> dict[str, Any]:
    file_size = clip_path.stat().st_size
    if file_size <= MAX_DIRECT_UPLOAD_BYTES:
        return client.upload_media_direct(clip_path)
    return client.upload_media_from_url(
        build_signed_social_export_url(
            subject=subject,
            project_id=project_id,
            clip_name=clip_name,
            publish_job_id=publish_job_id,
        )
    )


def _build_post_settings(
    *,
    platform: str,
    provider: str | None,
    title: str,
    hashtags: list[str],
) -> tuple[str, dict[str, Any]]:
    effective_provider = (provider or "").strip().lower()

    if platform == "youtube_shorts":
        return (
            "youtube",
            {
                "title": (title or "Short video").strip()[:100],
                "type": "public",
                "selfDeclaredMadeForKids": "no",
                "tags": hashtags[:20],
            },
        )

    if platform == "tiktok":
        return (
            "tiktok",
            {
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "duet": False,
                "comment": True,
                "stitch": False,
                "content_posting_method": "DIRECT_POST",
                "brand_content_toggle": False,
                "brand_organic_toggle": False,
                "autoAddMusic": False,
            },
        )

    if platform == "instagram_reels":
        settings_type = "instagram-standalone" if effective_provider == "instagram-standalone" else "instagram"
        return (
            settings_type,
            {
                "post_type": "post",
            },
        )

    if platform == "facebook_reels":
        return ("facebook", {})

    if platform == "x":
        return (
            "x",
            {
                "who_can_reply_post": "everyone",
            },
        )

    if platform == "linkedin":
        settings_type = "linkedin-page" if effective_provider == "linkedin-page" else "linkedin"
        return (
            settings_type,
            {
                "post_as_images_carousel": False,
            },
        )

    fallback = PLATFORM_TO_POSTIZ.get(platform)
    if not fallback:
        raise ValueError(f"Desteklenmeyen platform: {platform}")
    return (fallback, {})


def _extract_provider_post_id(result: Any) -> str | None:
    if isinstance(result, dict):
        for key in ("id", "postId", "post_id"):
            val = result.get(key)
            if val is not None:
                return str(val)
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            for key in ("id", "postId", "post_id"):
                val = first.get(key)
                if val is not None:
                    return str(val)
    return None


def _is_future_scheduled_job(job: dict[str, Any]) -> bool:
    if str(job.get("mode") or "") != "scheduled":
        return False
    scheduled_raw = str(job.get("scheduled_at") or "").strip()
    if not scheduled_raw:
        return False
    scheduled_dt = parse_iso(scheduled_raw)
    if scheduled_dt is None:
        return False
    return scheduled_dt > datetime.now(timezone.utc)


def publish_job_via_postiz(job: dict[str, Any], *, store: SocialStore | None = None) -> dict[str, Any]:
    db = store or get_social_store()
    subject = str(job["subject"])
    client, _credential = get_postiz_client_for_subject(subject, store=db)

    project_id = str(job["project_id"])
    clip_name = str(job["clip_name"])
    platform = str(job["platform"])
    account_id = str(job["account_id"])

    clip_path = get_project_path(project_id, "shorts", clip_name)
    if not clip_path.exists():
        raise FileNotFoundError(f"Klip bulunamadı: {clip_path}")

    payload = job.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    target = payload.get("target")
    target_provider = target.get("provider") if isinstance(target, dict) else None

    content = payload.get("content")
    if not isinstance(content, dict):
        content = {}

    text = str(content.get("text") or "").strip()
    title = str(content.get("title") or "").strip()
    hashtags = [str(tag).strip().replace("#", "") for tag in content.get("hashtags", []) if str(tag).strip()]

    settings_type, settings = _build_post_settings(
        platform=platform,
        provider=str(target_provider or ""),
        title=title,
        hashtags=hashtags,
    )

    media = _resolve_media(
        client,
        clip_path,
        subject=subject,
        project_id=project_id,
        clip_name=clip_name,
        publish_job_id=str(job["id"]),
    )

    mode = "scheduled" if str(job.get("mode")) == "scheduled" else "now"
    scheduled_at = str(job.get("scheduled_at") or "") or None
    if mode == "scheduled":
        due = parse_iso(scheduled_at)
        if due is None or due <= datetime.now(timezone.utc):
            mode = "now"
            scheduled_at = None

    result = client.create_post(
        integration_id=account_id,
        settings_type=settings_type,
        content_text=text,
        media=media,
        settings=settings,
        mode=mode,
        scheduled_at=scheduled_at,
        hashtags=hashtags,
    )

    return {
        "provider_post_id": _extract_provider_post_id(result),
        "media_id": str(media.get("id") or ""),
        "result": result,
    }


def create_scheduled_post_now(job: dict[str, Any], *, store: SocialStore | None = None) -> dict[str, Any]:
    db = store or get_social_store()
    job_id = str(job["id"])

    db.update_publish_job(
        job_id,
        state="publishing",
        message="Postiz takvimine ekleniyor",
        last_error=None,
    )

    try:
        result = publish_job_via_postiz(job, store=db)
    except (PostizApiError, FileNotFoundError, ValueError, OSError) as exc:
        latest = db.get_publish_job(job_id)
        attempt = int((latest or {}).get("attempts") or 0) + 1
        if attempt <= len(RETRY_BACKOFF_MINUTES):
            eta = compute_retry_eta(attempt)
            db.update_publish_job(
                job_id,
                state="retrying",
                message=f"Postiz takvimine ekleme başarısız, yeniden denenecek ({attempt}/{len(RETRY_BACKOFF_MINUTES)})",
                next_attempt_at=eta,
                last_error=str(exc),
                increment_attempt=True,
            )
        else:
            db.update_publish_job(
                job_id,
                state="failed",
                message="Postiz takvimine ekleme kalıcı olarak başarısız oldu",
                last_error=str(exc),
                increment_attempt=True,
            )
        raise

    db.update_publish_job(
        job_id,
        state="scheduled",
        message="Postiz takvimine eklendi",
        next_attempt_at=str(job.get("scheduled_at") or "") or None,
        provider_job_id=str(result.get("provider_post_id") or ""),
        result=result,
        last_error=None,
    )
    return db.get_publish_job(job_id) or job


def delete_scheduled_post_from_postiz(job: dict[str, Any], *, store: SocialStore | None = None) -> None:
    db = store or get_social_store()
    subject = str(job["subject"])
    provider_job_id = str(job.get("provider_job_id") or "").strip()
    if not provider_job_id:
        return

    client, _credential = get_postiz_client_for_subject(subject, store=db)
    try:
        client.delete_post(provider_job_id)
    except PostizApiError as exc:
        if "HTTP 404" in str(exc):
            return
        raise


def dry_run_publish_via_postiz(
    *,
    subject: str,
    project_id: str,
    clip_name: str,
    mode: str,
    scheduled_at: str | None,
    targets: list[dict[str, Any]],
    content_by_platform: dict[str, dict[str, Any]],
    probe_media_upload: bool = False,
    store: SocialStore | None = None,
    resolve_client_for_subject: Any | None = None,
) -> dict[str, Any]:
    db = store or get_social_store()
    client_resolver = resolve_client_for_subject or get_postiz_client_for_subject
    client, _credential = client_resolver(subject, store=db)

    accounts = resolve_postiz_accounts_for_subject(
        subject,
        store=db,
        resolve_client_for_subject=client_resolver,
    )
    validated_targets = validate_publish_targets_for_subject(
        subject=subject,
        targets=targets,
        store=db,
        resolve_client_for_subject=client_resolver,
    )
    accounts_by_id = {str(account["id"]): account for account in accounts}

    clip_path = get_project_path(project_id, "shorts", clip_name)
    if not clip_path.exists():
        raise FileNotFoundError(f"Klip bulunamadı: {clip_path}")

    media_probe: dict[str, Any] | None = None
    if probe_media_upload:
        media = _resolve_media(
            client,
            clip_path,
            subject=subject,
            project_id=project_id,
            clip_name=clip_name,
            publish_job_id="dry-run",
        )
        media_probe = {
            "attempted": True,
            "method": "direct" if clip_path.stat().st_size <= MAX_DIRECT_UPLOAD_BYTES else "url",
            "media_id": str(media.get("id") or ""),
            "path": str(media.get("path") or ""),
        }

    previews: list[dict[str, Any]] = []
    for target in validated_targets:
        account_id = str(target.get("account_id") or "").strip()
        platform = str(target.get("platform") or "").strip()
        provider = str(target.get("provider") or "").strip() or None
        account = accounts_by_id.get(account_id)
        if account is None:
            raise ValueError(f"Hedef hesap bulunamadı: {account_id}")

        content = content_by_platform.get(platform)
        if not isinstance(content, dict):
            raise ValueError(f"{platform} için içerik bulunamadı")

        title = str(content.get("title") or "").strip()
        text = str(content.get("text") or "").strip()
        hashtags = [
            str(tag).strip().replace("#", "")
            for tag in content.get("hashtags", [])
            if str(tag).strip()
        ]

        settings_type, settings = _build_post_settings(
            platform=platform,
            provider=provider,
            title=title,
            hashtags=hashtags,
        )

        previews.append(
            {
                "account_id": account_id,
                "account_name": str(account.get("name") or account_id),
                "account_platform": platform,
                "provider": provider or account.get("provider"),
                "settings_type": settings_type,
                "settings": settings,
                "mode": "scheduled" if mode == "scheduled" else "now",
                "scheduled_at": scheduled_at,
                "title": title,
                "text_preview": text[:280],
                "text_length": len(text),
                "hashtags": hashtags,
                "hashtags_count": len(hashtags),
            }
        )

    return {
        "clip_path": str(clip_path),
        "clip_size_bytes": clip_path.stat().st_size,
        "postiz_base_url": client.base_url,
        "targets": previews,
        "media_probe": media_probe
        or {
            "attempted": False,
            "method": "direct" if clip_path.stat().st_size <= MAX_DIRECT_UPLOAD_BYTES else "url",
        },
    }


def run_publish_attempt(job: dict[str, Any], *, store: SocialStore | None = None) -> None:
    db = store or get_social_store()
    job_id = str(job["id"])
    state = str(job.get("state") or "")

    if state == "draft":
        db.update_publish_job(job_id, state="queued", message="Planlanan zaman geldi, kuyruğa alındı")

    db.update_publish_job(job_id, state="publishing", message="Postiz yayını başlatıldı")

    try:
        result = publish_job_via_postiz(job, store=db)
    except (PostizApiError, FileNotFoundError, ValueError, OSError) as exc:
        latest = db.get_publish_job(job_id)
        attempt = int((latest or {}).get("attempts") or 0) + 1
        if attempt <= len(RETRY_BACKOFF_MINUTES):
            eta = compute_retry_eta(attempt)
            db.update_publish_job(
                job_id,
                state="retrying",
                message=f"Yayın denemesi başarısız, yeniden denenecek ({attempt}/{len(RETRY_BACKOFF_MINUTES)})",
                next_attempt_at=eta,
                last_error=str(exc),
                increment_attempt=True,
            )
            logger.warning("Social publish retry scheduled job_id={} err={}", job_id, exc)
            return

        db.update_publish_job(
            job_id,
            state="failed",
            message="Yayın kalıcı olarak başarısız oldu",
            last_error=str(exc),
            increment_attempt=True,
        )
        logger.error("Social publish failed permanently job_id={} err={}", job_id, exc)
        return

    db.update_publish_job(
        job_id,
        state="published",
        message="Yayın başarılı",
        provider_job_id=str(result.get("provider_post_id") or ""),
        result=result,
    )
