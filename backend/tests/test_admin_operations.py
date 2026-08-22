from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import admin_operations
from backend.api.security import AuthContext, authenticate_request


class FakeAdminService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def overview(self):
        return {
            "users": 4,
            "subscriptions": 2,
            "jobs": 8,
            "failed_jobs": 1,
            "risk_events": 3,
        }

    async def adjust_credit(self, *args, **kwargs):
        self.calls.append(("credit", args, kwargs))
        return 125

    async def suspend_user(self, *args, **kwargs):
        self.calls.append(("suspend", args, kwargs))

    async def sync_subscription(self, *args, **kwargs):
        self.calls.append(("sync", args, kwargs))
        return "active"

    async def retry_failed_job(self, *args, **kwargs):
        self.calls.append(("retry", args, kwargs))


def _client(service: FakeAdminService, *, roles: set[str] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(admin_operations.router)
    app.dependency_overrides[authenticate_request] = lambda: AuthContext(
        subject="admin_subject",
        roles=roles or {"admin"},
        token_type="static",
        auth_mode="static",
        claims={},
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    app.dependency_overrides[admin_operations.get_admin_service] = lambda: service
    return TestClient(app)


def test_admin_overview_requires_admin_role() -> None:
    response = _client(FakeAdminService(), roles={"member"}).get("/api/admin/overview")

    assert response.status_code == 403


def test_credit_adjustment_requires_reason_and_idempotency_key() -> None:
    service = FakeAdminService()
    client = _client(service)
    user_id = uuid4()

    missing_reason = client.post(
        f"/api/admin/users/{user_id}/credit-adjustments",
        headers={"Idempotency-Key": "admin-credit-0001"},
        json={"amount": 25, "reason": "short"},
    )
    missing_key = client.post(
        f"/api/admin/users/{user_id}/credit-adjustments",
        json={"amount": 25, "reason": "Customer support correction"},
    )

    assert missing_reason.status_code == 422
    assert missing_key.status_code == 422
    assert service.calls == []


def test_critical_admin_operations_forward_audit_context() -> None:
    service = FakeAdminService()
    client = _client(service)
    target_id = uuid4()
    headers = {"X-Request-ID": "req-admin-21", "Idempotency-Key": "admin-operation-0001"}
    reason = "Confirmed support investigation"

    adjusted = client.post(
        f"/api/admin/users/{target_id}/credit-adjustments",
        headers=headers,
        json={"amount": 25, "reason": reason},
    )
    suspended = client.post(
        f"/api/admin/users/{target_id}/suspend",
        headers=headers,
        json={"reason": reason},
    )
    synced = client.post(
        f"/api/admin/subscriptions/{target_id}/sync",
        headers=headers,
        json={"reason": reason},
    )
    retried = client.post(
        f"/api/admin/jobs/{target_id}/retry",
        headers=headers,
        json={"reason": reason},
    )

    assert adjusted.json() == {"available_credits": 125}
    assert suspended.status_code == 204
    assert synced.json() == {"status": "active"}
    assert retried.status_code == 202
    assert [call[0] for call in service.calls] == ["credit", "suspend", "sync", "retry"]
    for _, _, kwargs in service.calls:
        assert kwargs["reason"] == reason
        assert kwargs["audit"].request_id == "req-admin-21"
        assert kwargs["audit"].actor_id == UUID("00000000-0000-0000-0000-000000000001")
