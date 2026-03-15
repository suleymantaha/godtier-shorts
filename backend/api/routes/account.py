from __future__ import annotations

from fastapi import APIRouter, Depends
from loguru import logger

from backend.api.security import AuthContext, require_policy
from backend.core.exceptions import InvalidInputError
from backend.models.schemas import AccountDeletionRequest
from backend.services.account_purge import purge_subject_data


router = APIRouter(prefix="/api/account", tags=["account"])


@router.delete("/me/data")
async def delete_my_account_data(
    payload: AccountDeletionRequest,
    auth: AuthContext = Depends(require_policy("delete_account_data")),
) -> dict[str, object]:
    if payload.confirm != "DELETE":
        raise InvalidInputError("Hesap verilerini silmek icin DELETE onayi gerekli")

    summary = await purge_subject_data(auth.subject)
    logger.info(
        "🔐 Security event=account_data_purged subject={} deleted_projects={} deleted_social_rows={} cancelled_jobs={} scrubbed_grants={}",
        auth.subject,
        summary["deleted_projects"],
        summary["deleted_social_rows"],
        summary["cancelled_jobs"],
        summary["scrubbed_grants"],
    )
    return {"status": "purged", "summary": summary}
