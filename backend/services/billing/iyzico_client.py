from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx


class IyzicoError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    token: str
    checkout_form_content: str
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class ProviderOrder:
    reference_code: str
    amount_minor: int
    currency: str
    order_status: str
    payment_statuses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderSubscription:
    reference_code: str
    pricing_plan_reference_code: str
    status: str
    product_reference_code: str = ""
    customer_reference_code: str = ""
    order_references: frozenset[str] = frozenset()
    orders: dict[str, ProviderOrder] = field(default_factory=dict)


class IyzicoClient:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        random_key_factory: Callable[[], str] | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._secret_key = secret_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._random_key_factory = random_key_factory or self._random_key
        if not self._api_key or not self._secret_key or not self._base_url:
            raise ValueError("iyzico client configuration eksik")

    @staticmethod
    def _random_key() -> str:
        return f"{time.time_ns()}{secrets.randbelow(1_000_000_000):09d}"

    def _headers(self, path: str, body: bytes, random_key: str) -> dict[str, str]:
        signature = hmac.new(
            self._secret_key.encode("utf-8"),
            random_key.encode("utf-8") + path.encode("utf-8") + body,
            hashlib.sha256,
        ).hexdigest()
        authorization = base64.b64encode(
            (
                f"apiKey:{self._api_key}&randomKey:{random_key}"
                f"&signature:{signature}"
            ).encode("utf-8")
        ).decode("ascii")
        return {
            "Authorization": f"IYZWSv2 {authorization}",
            "Content-Type": "application/json",
            "x-iyzi-rnd": random_key,
        }

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else b""
        )
        random_key = self._random_key_factory()
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.request(
                method,
                path,
                content=body or None,
                headers=self._headers(path, body, random_key),
            )
        try:
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IyzicoError("iyzico istegi basarisiz") from exc
        if not isinstance(result, dict) or result.get("status") != "success":
            raise IyzicoError("iyzico islemi basarisiz")
        return result

    async def initialize_subscription_checkout(
        self,
        *,
        callback_url: str,
        pricing_plan_reference_code: str,
        conversation_id: str,
        customer: dict[str, Any],
    ) -> CheckoutSession:
        result = await self._request(
            "POST",
            "/v2/subscription/checkoutform/initialize",
            {
                "locale": "tr",
                "callbackUrl": callback_url,
                "pricingPlanReferenceCode": pricing_plan_reference_code,
                "subscriptionInitialStatus": "ACTIVE",
                "conversationId": conversation_id,
                "customer": customer,
            },
        )
        token = str(result.get("token") or "").strip()
        content = str(result.get("checkoutFormContent") or "").strip()
        if not token or not content:
            raise IyzicoError("iyzico checkout yaniti eksik")
        return CheckoutSession(
            token=token,
            checkout_form_content=content,
            expires_in_seconds=int(result.get("tokenExpireTime") or 0),
        )

    async def get_subscription(self, reference_code: str) -> ProviderSubscription:
        safe_reference = quote(reference_code.strip(), safe="")
        if not safe_reference:
            raise ValueError("subscription reference bos olamaz")
        result = await self._request("GET", f"/v2/subscription/subscriptions/{safe_reference}")
        data = result.get("data")
        if not isinstance(data, dict):
            raise IyzicoError("iyzico subscription yaniti eksik")
        if not data.get("referenceCode"):
            items = data.get("items")
            if not isinstance(items, list):
                raise IyzicoError("iyzico subscription yaniti eksik")
            data = next(
                (
                    item
                    for item in items
                    if isinstance(item, dict)
                    and str(item.get("referenceCode") or "").strip() == reference_code
                ),
                {},
            )
        orders: dict[str, ProviderOrder] = {}
        for order in data.get("orders", []):
            if not isinstance(order, dict):
                continue
            reference = str(order.get("referenceCode") or "").strip()
            currency = str(order.get("currencyCode") or "").strip().upper()
            try:
                minor_decimal = Decimal(str(order.get("price"))) * 100
            except (InvalidOperation, TypeError, ValueError):
                continue
            if (
                not reference
                or len(currency) != 3
                or minor_decimal != minor_decimal.to_integral_value()
                or minor_decimal < 0
            ):
                continue
            orders[reference] = ProviderOrder(
                reference_code=reference,
                amount_minor=int(minor_decimal),
                currency=currency,
                order_status=str(order.get("orderStatus") or "").strip().upper(),
                payment_statuses=tuple(
                    str(attempt.get("paymentStatus") or "").strip().upper()
                    for attempt in order.get("paymentAttempts", [])
                    if isinstance(attempt, dict)
                    and str(attempt.get("paymentStatus") or "").strip()
                ),
            )
        subscription = ProviderSubscription(
            reference_code=str(data.get("referenceCode") or "").strip(),
            product_reference_code=str(data.get("productReferenceCode") or "").strip(),
            pricing_plan_reference_code=str(data.get("pricingPlanReferenceCode") or "").strip(),
            status=str(data.get("subscriptionStatus") or "").strip().upper(),
            customer_reference_code=str(data.get("customerReferenceCode") or "").strip(),
            order_references=frozenset(
                str(order.get("referenceCode") or "").strip()
                for order in data.get("orders", [])
                if isinstance(order, dict) and str(order.get("referenceCode") or "").strip()
            ),
            orders=orders,
        )
        if not all(
            (
                subscription.reference_code,
                subscription.product_reference_code,
                subscription.pricing_plan_reference_code,
                subscription.status,
            )
        ):
            raise IyzicoError("iyzico subscription yaniti gecersiz")
        return subscription

    async def retrieve_checkout(self, token: str) -> ProviderSubscription:
        safe_token = quote(token.strip(), safe="")
        if not safe_token:
            raise ValueError("checkout token bos olamaz")
        result = await self._request("GET", f"/v2/subscription/checkoutform/{safe_token}")
        data = result.get("data")
        if not isinstance(data, dict):
            raise IyzicoError("iyzico checkout result yaniti eksik")
        subscription = ProviderSubscription(
            reference_code=str(data.get("referenceCode") or "").strip(),
            product_reference_code=str(data.get("productReferenceCode") or "").strip(),
            pricing_plan_reference_code=str(data.get("pricingPlanReferenceCode") or "").strip(),
            status=str(data.get("subscriptionStatus") or "").strip().upper(),
        )
        if not all(
            (
                subscription.reference_code,
                subscription.pricing_plan_reference_code,
                subscription.status,
            )
        ):
            raise IyzicoError("iyzico checkout result yaniti gecersiz")
        return subscription

    async def cancel_subscription(self, reference_code: str) -> None:
        safe_reference = quote(reference_code.strip(), safe="")
        if not safe_reference:
            raise ValueError("subscription reference bos olamaz")
        await self._request(
            "POST",
            f"/v2/subscription/subscriptions/{safe_reference}/cancel",
            {"subscriptionReferenceCode": reference_code},
        )

    async def upgrade_subscription(self, reference_code: str, pricing_reference: str) -> str:
        safe_reference = quote(reference_code.strip(), safe="")
        if not safe_reference or not pricing_reference.strip():
            raise ValueError("subscription plan degisikligi referansi bos olamaz")
        result = await self._request(
            "POST",
            f"/v2/subscription/subscriptions/{safe_reference}/upgrade",
            {
                "newPricingPlanReferenceCode": pricing_reference,
                "upgradePeriod": "NOW",
                "useTrial": False,
                "resetRecurrenceCount": False,
            },
        )
        data = result.get("data")
        upgraded_reference = str(data.get("referenceCode") or "").strip() if isinstance(data, dict) else ""
        return upgraded_reference or reference_code
