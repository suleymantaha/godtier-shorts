from __future__ import annotations

from fastapi import APIRouter, Depends
from backend.api.security import AuthContext, authenticate_request
from backend.services.ownership import build_subject_hash


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/whoami")
async def whoami(
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, object]:
    response: dict[str, object] = {
        "auth_mode": auth.auth_mode,
        "roles": sorted(auth.roles),
        "subject": auth.subject,
        "subject_hash": build_subject_hash(auth.subject),
        "token_type": auth.token_type,
    }
    if auth.user_id is not None:
        response["user_id"] = str(auth.user_id)
    if auth.database_role is not None:
        response["database_role"] = auth.database_role.value
    return response
