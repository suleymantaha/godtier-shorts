from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import billing
from backend.api.security import AuthContext, authenticate_request
from backend.services.billing.iyzico_client import CheckoutSession
from backend.services.billing.subscription_service import (
    BillingInterval,
    SubscriptionSnapshot,
)
from backend.db.models import SubscriptionStatus


class FakeBillingService:
    def __init__(self) -> None:
        self.checkout_calls = 0

    async def create_checkout(self, **kwargs) -> CheckoutSession:
        self.checkout_calls += 1
        return CheckoutSession("token", "<script>hosted</script>", 1800)

    async def confirm_checkout(self, token: str) -> SubscriptionSnapshot:
        assert token == "checkout-token"
        return SubscriptionSnapshot("creator", BillingInterval.MONTHLY, SubscriptionStatus.ACTIVE)


def _app(service: FakeBillingService, *, authenticated: bool) -> FastAPI:
    app = FastAPI()
    app.include_router(billing.router)
    app.dependency_overrides[billing.get_subscription_service] = lambda: service
    if authenticated:
        app.dependency_overrides[authenticate_request] = lambda: AuthContext(
            subject="user-1",
            roles={"member"},
            token_type="jwt",
            auth_mode="clerk_jwt",
            user_id=uuid4(),
        )
    return app


def _checkout_payload() -> dict[str, object]:
    address = {
        "address": "Test Mahallesi 1",
        "contact_name": "Ada Lovelace",
        "city": "Istanbul",
        "country": "Turkey",
    }
    return {
        "plan_code": "creator",
        "interval": "monthly",
        "customer": {
            "name": "Ada",
            "surname": "Lovelace",
            "email": "ada@example.com",
            "gsm_number": "+905551112233",
            "identity_number": "11111111111",
            "billing_address": address,
            "shipping_address": address,
        },
    }


def test_checkout_requires_authentication() -> None:
    service = FakeBillingService()
    response = TestClient(_app(service, authenticated=False)).post(
        "/api/billing/checkout",
        json=_checkout_payload(),
        headers={"Idempotency-Key": "checkout-1"},
    )

    assert response.status_code == 401
    assert service.checkout_calls == 0


def test_frontend_success_flag_cannot_grant_entitlement() -> None:
    service = FakeBillingService()
    payload = _checkout_payload()
    payload["success"] = True

    response = TestClient(_app(service, authenticated=True)).post(
        "/api/billing/checkout",
        json=payload,
        headers={"Idempotency-Key": "checkout-1"},
    )

    assert response.status_code == 422
    assert service.checkout_calls == 0


def test_authenticated_checkout_returns_only_hosted_form_session() -> None:
    service = FakeBillingService()
    response = TestClient(_app(service, authenticated=True)).post(
        "/api/billing/checkout",
        json=_checkout_payload(),
        headers={"Idempotency-Key": "checkout-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "token": "token",
        "checkout_form_content": "<script>hosted</script>",
        "expires_in_seconds": 1800,
    }
    assert service.checkout_calls == 1


def test_checkout_requires_idempotency_key() -> None:
    service = FakeBillingService()
    response = TestClient(_app(service, authenticated=True)).post(
        "/api/billing/checkout", json=_checkout_payload()
    )
    assert response.status_code == 422
    assert service.checkout_calls == 0


def test_callback_confirms_token_with_provider_without_browser_auth() -> None:
    service = FakeBillingService()
    response = TestClient(_app(service, authenticated=False)).post(
        "/api/billing/callback",
        data={"token": "checkout-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "plan_code": "creator",
        "interval": "monthly",
        "status": "active",
    }
