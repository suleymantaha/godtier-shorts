from __future__ import annotations

import os
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, autoflush=False, expire_on_commit=False)


@lru_cache(maxsize=4)
def _cached_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(database_url)


def get_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    resolved_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if not resolved_url:
        raise RuntimeError("DATABASE_URL is required")
    return _cached_session_factory(resolved_url)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
