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
                reserved = await session.scalar(select(func.coalesce(func.sum(UploadReservation.size_bytes), 0)).where(
                    UploadReservation.user_id == user_id))
                # A validated object has both rows. Keep its durable charge once,
                # including when an Asset is subsequently removed by retention.
                has_reservation = exists().where(UploadReservation.storage_key == Asset.storage_key)
                assets = await session.scalar(select(func.coalesce(func.sum(Asset.size_bytes), 0)).where(
                    Asset.user_id == user_id, ~has_reservation))
                if int(reserved or 0) + int(assets or 0) + size_bytes > limit:
                    raise UploadQuotaExceeded(
                        "Upload storage limit reached. Pending and unfinished uploads also use storage; "
                        "contact support if an unfinished upload is blocking capacity."
                    )
                session.add(UploadReservation(storage_key=storage_key, user_id=user_id,
                    content_type=content_type, size_bytes=size_bytes, expires_at=expires_at))
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
