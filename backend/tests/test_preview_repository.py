from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.db.models import User, UserRole, UserStatus
from backend.db.session import create_session_factory
from backend.services.preview.repository import SqlAlchemyPreviewEntitlements


ROOT = Path(__file__).resolve().parents[2]


def test_preview_entitlement_is_single_use_and_failure_can_release() -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for preview repository integration test")
    config = Config(ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")

    async def scenario() -> None:
        factory = create_session_factory(database_url)
        user_id = uuid4()
        identity_hash = "a" * 64
        async with factory() as session:
            await session.execute(text("TRUNCATE trial_entitlements, users RESTART IDENTITY CASCADE"))
            session.add(User(
                id=user_id,
                clerk_subject=f"preview_{user_id.hex}",
                status=UserStatus.ACTIVE,
                role=UserRole.USER,
            ))
            await session.commit()

            repository = SqlAlchemyPreviewEntitlements(session)
            assert await repository.claim(user_id=user_id, identity_key_hash=identity_hash) is True
            assert await repository.claim(user_id=user_id, identity_key_hash=identity_hash) is False
            await repository.release(identity_key_hash=identity_hash)
            assert await repository.claim(user_id=user_id, identity_key_hash=identity_hash) is True

        await factory.kw["bind"].dispose()

    asyncio.run(scenario())
