from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select

from backend.db.models import Asset, AssetKind, Project, SourceType, User, UserStatus
from backend.db.session import get_session_factory


def upload_project_id(user_id: UUID, storage_key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"godtier:upload:{user_id}:{storage_key}")


async def persist_validated_upload(
    *, user_id: UUID, storage_key: str, content_type: str, size_bytes: int,
    duration_seconds: int, sha256: str,
) -> UUID:
    factory = get_session_factory()
    async with factory() as session, session.begin():
        user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None or user.status is not UserStatus.ACTIVE:
            raise ValueError("Account is not active")
        existing = await session.scalar(select(Asset).where(Asset.storage_key == storage_key))
        if existing is not None:
            if existing.user_id != user_id or existing.sha256 != sha256:
                raise ValueError("Validated upload conflicts with existing source")
            return existing.project_id
        project_id = upload_project_id(user_id, storage_key)
        session.add(Project(
            id=project_id, user_id=user_id, source_type=SourceType.UPLOAD,
            source_ref=storage_key, source_fingerprint=sha256,
            duration_seconds=duration_seconds,
        ))
        await session.flush()
        session.add(Asset(
            id=uuid4(), user_id=user_id, project_id=project_id, kind=AssetKind.SOURCE,
            storage_key=storage_key, mime_type=content_type, size_bytes=size_bytes,
            sha256=sha256,
        ))
    return project_id
