from __future__ import annotations

from fastapi import APIRouter, Depends
from backend.api.security import AuthContext, authenticate_request
from backend.services.ownership import build_subject_hash


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/whoami")
async def whoami(
    auth: AuthContext = Depends(authenticate_request),
) -> dict[str, object]:
    return {
        "auth_mode": auth.auth_mode,
        "roles": sorted(auth.roles),
        "subject": auth.subject,
        "subject_hash": build_subject_hash(auth.subject),
        "token_type": auth.token_type,
    }
