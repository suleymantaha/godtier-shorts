from __future__ import annotations

import datetime as dt
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from svix.webhooks import Webhook

from backend.api.routes import clerk as clerk_routes


def _signed_headers(secret: str, payload_text: str) -> dict[str, str]:
    message_id = "msg_123"
    timestamp = dt.datetime.now(dt.timezone.utc)
    signature = Webhook(secret).sign(message_id, timestamp, payload_text)
    return {
        "svix-id": message_id,
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature,
    }


def test_clerk_user_created_webhook_assigns_member_roles(monkeypatch) -> None:
    monkeypatch.setenv("CLERK_WEBHOOK_SIGNING_SECRET", "whsec_test_secret")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_secret")
    monkeypatch.setenv("CLERK_DEFAULT_USER_ROLES", "member")

    captured: dict[str, object] = {}

    async def _fake_sync_user_roles(*, user_id: str, roles: list[str]) -> None:
        captured["user_id"] = user_id
        captured["roles"] = roles

    monkeypatch.setattr("backend.api.routes.clerk.sync_user_roles", _fake_sync_user_roles)

    app = FastAPI()
    app.include_router(clerk_routes.router)
    client = TestClient(app)
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_123",
            "primary_email_address_id": "idn_123",
            "email_addresses": [
                {"id": "idn_123", "email_address": "newuser@example.com"},
            ],
        },
    }
    payload_text = json.dumps(payload)
    response = client.post(
        "/api/clerk/webhooks",
        content=payload_text,
        headers=_signed_headers("whsec_test_secret", payload_text),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "synced"
    assert captured == {"user_id": "user_123", "roles": ["member"]}


def test_clerk_user_created_webhook_assigns_admin_for_allowlisted_email(monkeypatch) -> None:
    monkeypatch.setenv("CLERK_WEBHOOK_SIGNING_SECRET", "whsec_test_secret")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_secret")
    monkeypatch.setenv("CLERK_DEFAULT_USER_ROLES", "member")
    monkeypatch.setenv("CLERK_ADMIN_EMAILS", "suleymantahab@gmail.com")

    captured: dict[str, object] = {}

    async def _fake_sync_user_roles(*, user_id: str, roles: list[str]) -> None:
        captured["user_id"] = user_id
        captured["roles"] = roles

    monkeypatch.setattr("backend.api.routes.clerk.sync_user_roles", _fake_sync_user_roles)

    app = FastAPI()
    app.include_router(clerk_routes.router)
    client = TestClient(app)
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_admin",
            "primary_email_address_id": "idn_admin",
            "email_addresses": [
                {"id": "idn_admin", "email_address": "suleymantahab@gmail.com"},
            ],
        },
    }
    payload_text = json.dumps(payload)
    response = client.post(
        "/api/clerk/webhooks",
        content=payload_text,
        headers=_signed_headers("whsec_test_secret", payload_text),
    )

    assert response.status_code == 200
    assert captured == {"user_id": "user_admin", "roles": ["admin"]}


def test_clerk_webhook_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("CLERK_WEBHOOK_SIGNING_SECRET", "whsec_expected")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_secret")

    app = FastAPI()
    app.include_router(clerk_routes.router)
    client = TestClient(app)
    payload_text = json.dumps({"type": "user.created", "data": {"id": "user_123"}})

    response = client.post(
        "/api/clerk/webhooks",
        content=payload_text,
        headers=_signed_headers("whsec_d3JvbmdzZWNyZXQ", payload_text),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "clerk_webhook_invalid"
