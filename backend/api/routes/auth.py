from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.routes.clips import invalidate_clips_cache
from backend.api.security import AuthContext, authenticate_request, require_policy
from backend.api.websocket import manager
from backend.services.ownership import (
    build_subject_hash,
    build_subject_ownership_diagnostics,
    reassign_project_owner,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])

ACTIVE_PROJECT_JOB_STATUSES = {"queued", "processing"}


class ClaimProjectOwnershipRequest(BaseModel):
    project_id: str


def _assert_project_has_no_active_jobs(project_id: str) -> None:
    for job in manager.jobs.values():
        if str(job.get("project_id") or "") != project_id:
            continue
        if str(job.get("status") or "") not in ACTIVE_PROJECT_JOB_STATUSES:
            continue
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "project_has_active_jobs",
                    "message": "Aktif veya kuyruktaki bir is varken proje sahipligi degistirilemez.",
                }
            },
        )


def _rewrite_job_project_references(old_project_id: str, new_project_id: str) -> None:
    for job in manager.jobs.values():
        if str(job.get("project_id") or "") != old_project_id:
            continue
        job["project_id"] = new_project_id
        output_url = job.get("output_url")
        if isinstance(output_url, str) and old_project_id in output_url:
            job["output_url"] = output_url.replace(old_project_id, new_project_id)


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


@router.get("/ownership-diagnostics")
async def ownership_diagnostics(
    auth: AuthContext = Depends(require_policy("inspect_project_ownership")),
) -> dict[str, object]:
    diagnostics = build_subject_ownership_diagnostics(auth.subject)
    return {
        "auth_mode": auth.auth_mode,
        "current_subject": auth.subject,
        "current_subject_hash": diagnostics["current_subject_hash"],
        "reclaimable_projects": diagnostics["reclaimable_projects"],
        "token_type": auth.token_type,
        "visible_project_count": diagnostics["visible_project_count"],
    }


@router.post("/claim-project-ownership")
async def claim_project_ownership(
    payload: ClaimProjectOwnershipRequest,
    auth: AuthContext = Depends(require_policy("claim_project_ownership")),
) -> dict[str, object]:
    _assert_project_has_no_active_jobs(payload.project_id)
    try:
        summary = reassign_project_owner(payload.project_id, new_owner_subject=auth.subject)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "project_not_found",
                    "message": str(exc),
                }
            },
        ) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "destination_project_exists",
                    "message": str(exc),
                }
            },
        ) from exc
    except ValueError as exc:
        error_code = "project_already_claimed" if "already belongs" in str(exc) else "invalid_project_id"
        http_status = status.HTTP_409_CONFLICT if error_code == "project_already_claimed" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=http_status,
            detail={
                "error": {
                    "code": error_code,
                    "message": str(exc),
                }
            },
        ) from exc

    old_project_id = str(summary["old_project_id"])
    new_project_id = str(summary["new_project_id"])
    _rewrite_job_project_references(old_project_id, new_project_id)
    invalidate_clips_cache(reason=f"project_claimed:{old_project_id}->{new_project_id}")
    return {
        "status": "claimed",
        "clip_count": summary["clip_count"],
        "current_subject_hash": summary["new_owner_subject_hash"],
        "metadata_files_updated": summary["metadata_files_updated"],
        "new_project_id": new_project_id,
        "old_project_id": old_project_id,
    }
