from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.security import AuthContext, require_policy
from backend.db.session import get_db_session
from backend.services.storage.media_validation import (
    ArqMediaValidationQueue,
    MediaValidationQueue,
)
from backend.services.storage.object_store import (
    ObjectNotFoundError,
    ObjectStoreError,
    UploadValidationError,
)
from backend.services.storage.r2_store import R2ObjectStore, SqlAlchemyAssetRepository


router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class PresignUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(gt=0)


class PresignUploadResponse(BaseModel):
    url: str
    storage_key: str
    required_headers: dict[str, str]
    expires_seconds: int


class CompleteUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    storage_key: str = Field(min_length=1, max_length=1024)


class CompleteUploadResponse(BaseModel):
    validation_job_id: str
    status: str


class DownloadUrlResponse(BaseModel):
    url: str
    expires_seconds: int = 600


async def get_object_store(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> R2ObjectStore:
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    return R2ObjectStore(
        client=client,
        bucket_name=os.environ["R2_BUCKET_NAME"],
        asset_repository=SqlAlchemyAssetRepository(session),
    )


def get_media_validation_queue() -> MediaValidationQueue:
    return ArqMediaValidationQueue(os.environ["REDIS_URL"])


def _database_user_id(auth: AuthContext) -> UUID:
    if auth.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload identity unavailable",
        )
    return auth.user_id


@router.post("/presign", response_model=PresignUploadResponse)
async def presign_upload(
    payload: PresignUploadRequest,
    auth: Annotated[AuthContext, Depends(require_policy("upload"))],
    store: Annotated[R2ObjectStore, Depends(get_object_store)],
):
    try:
        return await store.create_upload_url(
            _database_user_id(auth),
            payload.filename,
            payload.content_type,
            payload.size_bytes,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ObjectStoreError as exc:
        raise HTTPException(status_code=502, detail="Object storage unavailable") from exc


@router.post(
    "/complete", response_model=CompleteUploadResponse, status_code=status.HTTP_202_ACCEPTED
)
async def complete_upload(
    payload: CompleteUploadRequest,
    auth: Annotated[AuthContext, Depends(require_policy("upload"))],
    store: Annotated[R2ObjectStore, Depends(get_object_store)],
    validation_queue: Annotated[
        MediaValidationQueue, Depends(get_media_validation_queue)
    ],
):
    user_id = _database_user_id(auth)
    try:
        metadata = await store.verify_uploaded_object(user_id, payload.storage_key)
        job_id = await validation_queue.enqueue(user_id=user_id, metadata=metadata)
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Uploaded object not found") from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ObjectStoreError as exc:
        raise HTTPException(status_code=502, detail="Object storage unavailable") from exc
    return CompleteUploadResponse(validation_job_id=job_id, status="queued")


@router.post("/assets/{asset_id}/download", response_model=DownloadUrlResponse)
async def create_asset_download(
    asset_id: UUID,
    auth: Annotated[
        AuthContext, Depends(require_policy("view_project_media"))
    ],
    store: Annotated[R2ObjectStore, Depends(get_object_store)],
):
    try:
        url = await store.create_download_url(_database_user_id(auth), asset_id)
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    except ObjectStoreError as exc:
        raise HTTPException(status_code=502, detail="Object storage unavailable") from exc
    return DownloadUrlResponse(url=url)
