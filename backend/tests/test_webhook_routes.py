from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import webhooks
from backend.services.billing.webhook_service import (
    WebhookResult,
    WebhookSignatureError,
)


PAYLOAD = {
    "merchantId": 3404590,
    "iyziEventType": "subscription.order.success",
    "subscriptionReferenceCode": "sub-1",
    "orderReferenceCode": "order-1",
    "customerReferenceCode": "customer-1",
    "iyziReferenceCode": "event-1",
    "iyziEventTime": 1758704403161,
}


class FakeWebhookService:
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.calls = 0

    async def handle(self, payload, signature: str) -> WebhookResult:
        self.calls += 1
        if self.reject:
            raise WebhookSignatureError("iyzico webhook imzasi gecersiz")
        return WebhookResult(processed=True)


def _client(service: FakeWebhookService) -> TestClient:
    app = FastAPI()
    app.include_router(webhooks.router)
    app.dependency_overrides[webhooks.get_webhook_service] = lambda: service
    return TestClient(app)


def test_invalid_signature_returns_401_without_echoing_payload_or_signature() -> None:
    service = FakeWebhookService(reject=True)
    signature = "a" * 64

    response = _client(service).post(
        "/api/webhooks/iyzico/subscription",
        json=PAYLOAD,
        headers={"X-IYZ-SIGNATURE-V3": signature},
    )

    assert response.status_code == 401
    assert signature not in response.text
    assert "order-1" not in response.text
    assert service.calls == 1


def test_valid_webhook_returns_2xx_acknowledgement() -> None:
    response = _client(FakeWebhookService()).post(
        "/api/webhooks/iyzico/subscription",
        json=PAYLOAD,
        headers={"X-IYZ-SIGNATURE-V3": "b" * 64},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "processed": True}
