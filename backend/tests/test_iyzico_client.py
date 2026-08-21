from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json

import httpx

from backend.services.billing.iyzico_client import IyzicoClient


def test_checkout_uses_hosted_form_and_iyzws_v2_signature() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "token": "checkout-token",
                "checkoutFormContent": "<script>hosted</script>",
                "tokenExpireTime": 1800,
            },
        )

    client = IyzicoClient(
        api_key="sandbox-api-key",
        secret_key="sandbox-secret",
        base_url="https://sandbox-api.iyzipay.com",
        transport=httpx.MockTransport(handler),
        random_key_factory=lambda: "rnd-123",
    )
    result = asyncio.run(
        client.initialize_subscription_checkout(
            callback_url="https://api.example.com/api/billing/callback",
            pricing_plan_reference_code="pricing-monthly",
            conversation_id="conv-1",
            customer={
                "name": "Ada",
                "surname": "Lovelace",
                "email": "ada@example.com",
                "gsmNumber": "+905551112233",
                "identityNumber": "11111111111",
                "billingAddress": {
                    "address": "Test Mahallesi 1",
                    "contactName": "Ada Lovelace",
                    "city": "Istanbul",
                    "country": "Turkey",
                },
                "shippingAddress": {
                    "address": "Test Mahallesi 1",
                    "contactName": "Ada Lovelace",
                    "city": "Istanbul",
                    "country": "Turkey",
                },
            },
        )
    )

    request = captured[0]
    body = request.content.decode("utf-8")
    payload = json.loads(body)
    signature = hmac.new(
        b"sandbox-secret",
        ("rnd-123/v2/subscription/checkoutform/initialize" + body).encode(),
        hashlib.sha256,
    ).hexdigest()
    authorization = base64.b64encode(
        f"apiKey:sandbox-api-key&randomKey:rnd-123&signature:{signature}".encode()
    ).decode()

    assert request.method == "POST"
    assert request.url.path == "/v2/subscription/checkoutform/initialize"
    assert request.headers["authorization"] == f"IYZWSv2 {authorization}"
    assert request.headers["x-iyzi-rnd"] == "rnd-123"
    assert payload["subscriptionInitialStatus"] == "ACTIVE"
    assert payload["pricingPlanReferenceCode"] == "pricing-monthly"
    assert "paymentCard" not in payload
    assert result.token == "checkout-token"
    assert result.checkout_form_content == "<script>hosted</script>"


def test_subscription_query_and_cancel_use_provider_endpoints() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "totalCount": 1,
                    "items": [{
                        "referenceCode": "sub-1",
                        "productReferenceCode": "product-creator",
                        "customerReferenceCode": "customer-1",
                        "pricingPlanReferenceCode": "pricing-monthly",
                        "subscriptionStatus": "CANCELED",
                        "orders": [{
                            "referenceCode": "order-1",
                            "price": 99.90,
                            "currencyCode": "TRY",
                            "orderStatus": "SUCCESS",
                            "paymentAttempts": [{"paymentStatus": "SUCCESS"}],
                        }],
                    }],
                },
            },
        )

    client = IyzicoClient(
        api_key="api-key",
        secret_key="secret-key",
        base_url="https://sandbox-api.iyzipay.com",
        transport=httpx.MockTransport(handler),
        random_key_factory=lambda: "rnd-1",
    )

    queried = asyncio.run(client.get_subscription("sub-1"))
    asyncio.run(client.cancel_subscription("sub-1"))

    assert requests == [
        ("GET", "/v2/subscription/subscriptions/sub-1"),
        ("POST", "/v2/subscription/subscriptions/sub-1/cancel"),
    ]
    assert queried.reference_code == "sub-1"
    assert queried.status == "CANCELED"
    assert queried.customer_reference_code == "customer-1"
    assert queried.order_references == frozenset({"order-1"})
    assert queried.orders["order-1"].amount_minor == 9990
    assert queried.orders["order-1"].order_status == "SUCCESS"
    assert queried.orders["order-1"].payment_statuses == ("SUCCESS",)


def test_checkout_result_is_retrieved_from_provider_by_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/subscription/checkoutform/checkout-token"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "referenceCode": "sub-1",
                    "pricingPlanReferenceCode": "pricing-monthly",
                    "subscriptionStatus": "ACTIVE",
                },
            },
        )

    client = IyzicoClient(
        api_key="api-key",
        secret_key="secret-key",
        base_url="https://sandbox-api.iyzipay.com",
        transport=httpx.MockTransport(handler),
        random_key_factory=lambda: "rnd-1",
    )

    result = asyncio.run(client.retrieve_checkout("checkout-token"))

    assert result.reference_code == "sub-1"
    assert result.product_reference_code == ""
