from __future__ import annotations

import os
from typing import Any

import httpx
from svix.webhooks import Webhook, WebhookVerificationError


CLERK_API_BASE_URL = "https://api.clerk.com/v1"
DEFAULT_MEMBER_ROLES = ("member",)


class ClerkWebhookConfigError(RuntimeError):
    pass


class ClerkWebhookVerificationError(ValueError):
    pass


class ClerkMetadataSyncError(RuntimeError):
    pass


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ClerkWebhookConfigError(f"{name} tanimli olmali")
    return value


def _parse_roles(raw: str | None) -> list[str]:
    source = (raw or "").strip()
    if not source:
        return list(DEFAULT_MEMBER_ROLES)
    roles = [role.strip().lower() for role in source.split(",") if role.strip()]
    return roles or list(DEFAULT_MEMBER_ROLES)


def default_member_roles() -> list[str]:
    return _parse_roles(os.getenv("CLERK_DEFAULT_USER_ROLES"))


def admin_email_allowlist() -> set[str]:
    raw = os.getenv("CLERK_ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def resolve_roles_for_email(email: str | None) -> list[str]:
    normalized_email = str(email or "").strip().lower()
    if normalized_email and normalized_email in admin_email_allowlist():
        return ["admin"]
    return default_member_roles()


def verify_clerk_webhook(payload: bytes, headers: dict[str, str]) -> dict[str, Any]:
    signing_secret = _read_required_env("CLERK_WEBHOOK_SIGNING_SECRET")
    try:
        verified = Webhook(signing_secret).verify(payload, headers)
    except WebhookVerificationError as exc:
        raise ClerkWebhookVerificationError("Clerk webhook imzasi dogrulanamadi") from exc
    if not isinstance(verified, dict):
        raise ClerkWebhookVerificationError("Clerk webhook payload formati gecersiz")
    return verified


def _extract_primary_email(payload: dict[str, Any]) -> str | None:
    primary_email_id = str(payload.get("primary_email_address_id") or "").strip()
    email_entries = payload.get("email_addresses")
    if not isinstance(email_entries, list):
        return None

    fallback_email: str | None = None
    for entry in email_entries:
        if not isinstance(entry, dict):
            continue
        email_address = str(entry.get("email_address") or "").strip()
        if not email_address:
            continue
        if fallback_email is None:
            fallback_email = email_address
        if str(entry.get("id") or "").strip() == primary_email_id:
            return email_address
    return fallback_email


def extract_user_identity(event_payload: dict[str, Any]) -> tuple[str, str | None]:
    data = event_payload.get("data")
    if not isinstance(data, dict):
        raise ClerkWebhookVerificationError("Clerk webhook data alani gecersiz")

    user_id = str(data.get("id") or "").strip()
    if not user_id:
        raise ClerkWebhookVerificationError("Clerk webhook user id eksik")

    return user_id, _extract_primary_email(data)


async def sync_user_roles(*, user_id: str, roles: list[str]) -> None:
    secret_key = _read_required_env("CLERK_SECRET_KEY")
    timeout = httpx.Timeout(10.0, connect=5.0)
    url = f"{CLERK_API_BASE_URL}/users/{user_id}/metadata"
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "public_metadata": {
            "roles": roles,
        }
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.patch(url, headers=headers, json=payload)

    if response.status_code >= 400:
        detail = response.text.strip()
        raise ClerkMetadataSyncError(
            f"Clerk metadata guncellenemedi: status={response.status_code} body={detail[:500]}"
        )
