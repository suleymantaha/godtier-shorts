from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.billing import get_iyzico_client
from backend.db.session import get_db_session
from backend.services.billing.iyzico_client import IyzicoError
from backend.services.billing.webhook_service import (
    IyzicoWebhookService,
    SqlAlchemyWebhookRepository,
    WebhookConflictError,
    WebhookError,
    WebhookPayloadError,
    WebhookSignatureError,
)


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


async def get_webhook_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IyzicoWebhookService:
    return IyzicoWebhookService(
        repository=SqlAlchemyWebhookRepository(session),
        provider=get_iyzico_client(),
        merchant_id=os.getenv("IYZICO_MERCHANT_ID", ""),
        secret_key=os.getenv("IYZICO_SECRET_KEY", ""),
        plan_references_json=os.getenv("IYZICO_PLAN_REFERENCES_JSON", ""),
        grace_days=int(os.getenv("BILLING_PAST_DUE_GRACE_DAYS", "3")),
    )


@router.post("/iyzico/subscription")
async def iyzico_subscription_webhook(
    payload: dict[str, Any],
    signature: Annotated[
        str,
        Header(alias="X-IYZ-SIGNATURE-V3", min_length=64, max_length=128),
    ],
    service: Annotated[IyzicoWebhookService, Depends(get_webhook_service)],
) -> dict[str, bool]:
    try:
        result = await service.handle(payload, signature)
    except WebhookSignatureError as exc:
        raise HTTPException(status_code=401, detail="Invalid webhook signature") from exc
    except (WebhookPayloadError, WebhookConflictError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook") from exc
    except (WebhookError, IyzicoError) as exc:
        raise HTTPException(status_code=503, detail="Webhook processing unavailable") from exc
    return {"received": True, "processed": result.processed}
