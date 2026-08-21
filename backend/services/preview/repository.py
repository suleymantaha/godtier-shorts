from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TrialEntitlement, TrialStatus


class SqlAlchemyPreviewEntitlements:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(self, *, user_id: UUID, identity_key_hash: str) -> bool:
        statement = (
            insert(TrialEntitlement)
            .values(
                user_id=user_id,
                identity_key_hash=identity_key_hash,
                status=TrialStatus.CLAIMED,
                claimed_at=datetime.now(timezone.utc),
                reason="free_preview",
            )
            .on_conflict_do_nothing(index_elements=[TrialEntitlement.identity_key_hash])
            .returning(TrialEntitlement.id)
        )
        claimed_id = (await self._session.execute(statement)).scalar_one_or_none()
        await self._session.commit()
        return claimed_id is not None

    async def release(self, *, identity_key_hash: str) -> None:
        await self._session.execute(
            delete(TrialEntitlement).where(
                TrialEntitlement.identity_key_hash == identity_key_hash,
                TrialEntitlement.status == TrialStatus.CLAIMED,
                TrialEntitlement.reason == "free_preview",
            )
        )
        await self._session.commit()
