from __future__ import annotations

from loguru import logger

from fastapi import APIRouter, HTTPException, Request, status

from backend.services.clerk_sync import (
    ClerkMetadataSyncError,
    ClerkWebhookConfigError,
    ClerkWebhookVerificationError,
    extract_user_identity,
    resolve_roles_for_email,
    sync_user_roles,
    verify_clerk_webhook,
)


router = APIRouter(prefix="/api/clerk", tags=["clerk"])


def _config_error(exc: ClerkWebhookConfigError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "clerk_webhook_unavailable",
                "message": str(exc),
            }
        },
    )


def _verification_error(exc: ClerkWebhookVerificationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": "clerk_webhook_invalid",
                "message": str(exc),
            }
        },
    )


@router.post("/webhooks")
async def handle_clerk_webhook(request: Request) -> dict[str, object]:
    payload = await request.body()
    headers = {key: value for key, value in request.headers.items()}

    try:
        event = verify_clerk_webhook(payload, headers)
    except ClerkWebhookConfigError as exc:
        raise _config_error(exc) from exc
    except ClerkWebhookVerificationError as exc:
        raise _verification_error(exc) from exc

    event_type = str(event.get("type") or "").strip()
    if event_type != "user.created":
        return {"status": "ignored", "event_type": event_type or "unknown"}

    try:
        user_id, primary_email = extract_user_identity(event)
        roles = resolve_roles_for_email(primary_email)
        await sync_user_roles(user_id=user_id, roles=roles)
    except ClerkWebhookVerificationError as exc:
        raise _verification_error(exc) from exc
    except ClerkWebhookConfigError as exc:
        raise _config_error(exc) from exc
    except ClerkMetadataSyncError as exc:
        logger.error("Clerk metadata sync failed for user_id={}: {}", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": {
                    "code": "clerk_metadata_sync_failed",
                    "message": "Kullanici rolleri Clerk tarafinda guncellenemedi",
                }
            },
        ) from exc

    logger.info(
        "Clerk user.created sync tamamlandi user_id={} email={} roles={}",
        user_id,
        primary_email or "-",
        roles,
    )
    return {
        "status": "synced",
        "event_type": event_type,
        "roles": roles,
        "user_id": user_id,
    }
