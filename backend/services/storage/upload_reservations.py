from __future__ import annotations

import os
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.db.models import Asset, UploadReservation, User, UserStatus
from backend.db.session import get_session_factory
from backend.services.storage.object_store import ObjectStoreError, UploadValidationError


class UploadQuotaExceeded(ObjectStoreError):
    pass


class UploadReservations(Protocol):
    async def reserve(self, *, user_id: UUID, storage_key: str, content_type: str,
                      size_bytes: int, expires_at: datetime) -> None: ...

    async def verify(self, *, user_id: UUID, storage_key: str, content_type: str,
                     size_bytes: int) -> None: ...


class SqlAlchemyUploadReservations:
    """Serialize account admission and commit the charge before a URL can escape.

    Expiry is audit information, never permission to drop a charge: a PUT started
    before URL expiry can still finish later. Orphans deliberately consume quota.
    Reservations also survive Asset deletion until remote finality is proven.
    """

    async def reserve(self, *, user_id: UUID, storage_key: str, content_type: str,
                      size_bytes: int, expires_at: datetime) -> None:
        limit = int(os.getenv("UPLOAD_STORAGE_QUOTA_BYTES", str(5 * 1024**3)))
        if limit <= 0:
            raise ObjectStoreError("Upload storage quota is unavailable")
        try:
            async with get_session_factory()() as session, session.begin():
                user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
                if user is None or user.status is not UserStatus.ACTIVE:
                    raise UploadValidationError("Account is not active")
                await reserve_storage_in_session(
                    session, user_id=user_id, storage_key=storage_key,
                    content_type=content_type, size_bytes=size_bytes,
                    expires_at=expires_at, limit=limit,
                )
        except SQLAlchemyError as exc:
            raise ObjectStoreError("Upload reservation unavailable") from exc

    async def verify(self, *, user_id: UUID, storage_key: str, content_type: str,
                     size_bytes: int) -> None:
        try:
            async with get_session_factory()() as session:
                user = await session.scalar(select(User).where(User.id == user_id))
                row = await session.scalar(select(UploadReservation).where(
                    UploadReservation.storage_key == storage_key, UploadReservation.user_id == user_id))
                if user is None or user.status is not UserStatus.ACTIVE:
                    raise UploadValidationError("Account is not active")
                if row is None or row.content_type != content_type or row.size_bytes != size_bytes:
                    raise UploadValidationError("Upload does not match a storage reservation")
        except SQLAlchemyError as exc:
            raise ObjectStoreError("Upload reservation unavailable") from exc


async def reserve_storage_in_session(
    session, *, user_id: UUID, storage_key: str, content_type: str,
    size_bytes: int, expires_at: datetime, limit: int | None = None,
    allow_existing: bool = False,
) -> None:
    """Charge before remote writes; caller holds the User lock and commits first.

    Both presigned PUTs and worker outputs use this ledger. Expiry never releases
    bytes; failed/ambiguous writes remain charged until remote finality is proven.
    """
    if limit is None:
        limit = int(os.getenv("UPLOAD_STORAGE_QUOTA_BYTES", str(5 * 1024**3)))
    if limit <= 0 or size_bytes <= 0:
        raise ObjectStoreError("Storage quota is unavailable")
    existing = await session.scalar(select(UploadReservation).where(
        UploadReservation.storage_key == storage_key))
    if existing is not None:
        if (allow_existing and existing.user_id == user_id
                and existing.content_type == content_type and existing.size_bytes == size_bytes):
            return
        raise UploadValidationError("Storage reservation conflicts with existing charge")
    reserved = await session.scalar(select(func.coalesce(func.sum(UploadReservation.size_bytes), 0)).where(
        UploadReservation.user_id == user_id))
    has_reservation = exists().where(UploadReservation.storage_key == Asset.storage_key)
    assets = await session.scalar(select(func.coalesce(func.sum(Asset.size_bytes), 0)).where(
        Asset.user_id == user_id, ~has_reservation))
    # Legacy Assets already consume quota; adding their durable charge must not
    # count the same object twice, even for accounts already above the limit.
    asset = await session.scalar(select(Asset).where(Asset.storage_key == storage_key))
    if asset is not None and (asset.user_id != user_id or asset.size_bytes != size_bytes):
        raise UploadValidationError("Storage reservation conflicts with existing asset")
    increment = 0 if asset is not None else size_bytes
    if increment and int(reserved or 0) + int(assets or 0) + increment > limit:
        raise UploadQuotaExceeded(
            "Upload storage limit reached. Pending and unfinished uploads also use storage; "
            "contact support if an unfinished upload is blocking capacity."
        )
    session.add(UploadReservation(storage_key=storage_key, user_id=user_id,
        content_type=content_type, size_bytes=size_bytes, expires_at=expires_at))
