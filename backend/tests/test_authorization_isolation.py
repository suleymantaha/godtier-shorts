from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.api import security
from backend.api.routes import auth as auth_routes
from backend.db.models import User, UserRole
from backend.db.session import create_session_factory, get_session_factory


ROOT = Path(__file__).resolve().parents[2]


def _prepare_database(database_url: str) -> None:
    config = Config(ROOT / "alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


async def _delete_subject(database_url: str, clerk_subject: str) -> None:
    factory = create_session_factory(database_url)
    async with factory() as session:
        await session.execute(delete(User).where(User.clerk_subject == clerk_subject))
        await session.commit()
    await factory.kw["bind"].dispose()


async def _load_subjects(database_url: str, clerk_subject: str) -> list[User]:
    factory = create_session_factory(database_url)
    async with factory() as session:
        users = list(
            (
                await session.scalars(
                    select(User).where(User.clerk_subject == clerk_subject)
                )
            ).all()
        )
    await factory.kw["bind"].dispose()
    return users


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"member"}, UserRole.USER),
        ({"user"}, UserRole.USER),
        ({"support"}, UserRole.SUPPORT),
        ({"support", "admin"}, UserRole.ADMIN),
    ],
)
def test_clerk_roles_map_to_canonical_database_roles(
    claims: set[str],
    expected: UserRole,
) -> None:
    assert security.map_clerk_roles(claims) is expected


def test_admin_policy_requires_recent_second_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_AUDIENCE", "godtier-shorts-api")
    monkeypatch.setenv("ADMIN_MFA_MAX_AGE_MINUTES", "10")
    factor_age = [0, -1]

    def _decode(_token: str, _issuer: str, _audience: str) -> security.AuthContext:
        return security.AuthContext(
            subject="user_admin",
            roles={"admin"},
            token_type="jwt",
            auth_mode="clerk_jwt",
            claims={"fva": list(factor_age)},
        )

    monkeypatch.setattr(security, "_decode_jwt", _decode)

    app = FastAPI()

    @app.get("/admin")
    def admin_route(
        _auth: security.AuthContext = Depends(security.require_policy("admin")),
    ) -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    headers = {"Authorization": "Bearer jwt-token"}

    denied = client.get("/admin", headers=headers)
    factor_age[:] = [0, 0]
    allowed = client.get("/admin", headers=headers)

    assert denied.status_code == 403
    assert denied.json()["detail"]["error"]["code"] == "admin_mfa_required"
    assert allowed.status_code == 200


@pytest.mark.integration
def test_valid_clerk_jwt_maps_to_stable_internal_user_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for Clerk identity persistence")

    clerk_subject = "user_authorization_mapping"
    _prepare_database(database_url)
    asyncio.run(_delete_subject(database_url, clerk_subject))

    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_AUDIENCE", "godtier-shorts-api")

    def _decode(_token: str, _issuer: str, _audience: str) -> security.AuthContext:
        return security.AuthContext(
            subject=clerk_subject,
            roles={"member"},
            token_type="jwt",
            auth_mode="clerk_jwt",
            claims={"email": "User@Example.com", "fva": [0, -1]},
        )

    monkeypatch.setattr(security, "_decode_jwt", _decode)
    app = FastAPI()
    app.include_router(auth_routes.router)
    headers = {"Authorization": "Bearer jwt-token"}

    async def _exercise_requests() -> tuple[httpx.Response, httpx.Response, list[User]]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            first_response = await client.get("/api/auth/whoami", headers=headers)
            second_response = await client.get("/api/auth/whoami", headers=headers)
        persisted_users = await _load_subjects(database_url, clerk_subject)
        await get_session_factory(database_url).kw["bind"].dispose()
        return first_response, second_response, persisted_users

    try:
        first, second, users = asyncio.run(_exercise_requests())
    finally:
        asyncio.run(_delete_subject(database_url, clerk_subject))

    assert first.status_code == 200
    assert second.status_code == 200
    assert UUID(first.json()["user_id"]) == UUID(second.json()["user_id"])
    assert first.json()["roles"] == ["member", "user"]
    assert len(users) == 1
    assert users[0].id == UUID(first.json()["user_id"])
    assert users[0].email_normalized == "user@example.com"
    assert users[0].role is UserRole.USER
