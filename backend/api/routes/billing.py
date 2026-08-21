from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.security import AuthContext, authenticate_request
from backend.db.session import get_db_session
from backend.services.billing.iyzico_client import IyzicoClient, IyzicoError
from backend.services.billing.subscription_service import (
    BillingInterval,
    PlanReferenceMap,
    SqlAlchemySubscriptionRepository,
    SubscriptionService,
    SubscriptionServiceError,
)


router = APIRouter(prefix="/api/billing", tags=["billing"])


class BillingAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = Field(min_length=1, max_length=500)
    contact_name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=120)
    zip_code: str | None = Field(default=None, max_length=20)

    def provider_payload(self) -> dict[str, str]:
        payload = {
            "address": self.address,
            "contactName": self.contact_name,
            "city": self.city,
            "country": self.country,
        }
        if self.zip_code:
            payload["zipCode"] = self.zip_code
        return payload


class CheckoutCustomer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    gsm_number: str = Field(min_length=8, max_length=20)
    identity_number: str = Field(min_length=5, max_length=20)
    billing_address: BillingAddress
    shipping_address: BillingAddress

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("email gecersiz")
        return normalized

    def provider_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "surname": self.surname,
            "email": str(self.email),
            "gsmNumber": self.gsm_number,
            "identityNumber": self.identity_number,
            "billingAddress": self.billing_address.provider_payload(),
            "shippingAddress": self.shipping_address.provider_payload(),
        }


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=1, max_length=50)
    interval: BillingInterval
    customer: CheckoutCustomer


class CheckoutResponse(BaseModel):
    token: str
    checkout_form_content: str
    expires_in_seconds: int


class BillingStatusResponse(BaseModel):
    plan_code: str
    interval: BillingInterval
    status: str


def get_iyzico_client() -> IyzicoClient:
    return IyzicoClient(
        api_key=os.getenv("IYZICO_API_KEY", ""),
        secret_key=os.getenv("IYZICO_SECRET_KEY", ""),
        base_url=os.getenv("IYZICO_API_BASE_URL", ""),
    )


async def get_subscription_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubscriptionService:
    return SubscriptionService(
        SqlAlchemySubscriptionRepository(session),
        get_iyzico_client(),
        PlanReferenceMap.from_json(os.getenv("IYZICO_PLAN_REFERENCES_JSON", "")),
        os.getenv("IYZICO_CALLBACK_URL", ""),
        os.getenv("IYZICO_SECRET_KEY", ""),
        cooldown_seconds=int(os.getenv("BILLING_CHECKOUT_COOLDOWN_SECONDS", "30")),
    )


def _user_id(auth: AuthContext):
    if auth.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing identity unavailable",
        )
    return auth.user_id


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IyzicoError):
        return HTTPException(status_code=502, detail="Payment provider unavailable")
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> CheckoutResponse:
    try:
        checkout = await service.create_checkout(
            user_id=_user_id(auth),
            plan_code=request.plan_code,
            interval=request.interval,
            customer=request.customer.provider_payload(),
            idempotency_key=idempotency_key,
        )
    except (SubscriptionServiceError, IyzicoError, ValueError) as exc:
        raise _service_error(exc) from exc
    return CheckoutResponse(
        token=checkout.token,
        checkout_form_content=checkout.checkout_form_content,
        expires_in_seconds=checkout.expires_in_seconds,
    )


@router.get("/subscription", response_model=BillingStatusResponse)
@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> BillingStatusResponse:
    try:
        snapshot = await service.get_status(_user_id(auth))
    except (SubscriptionServiceError, IyzicoError, ValueError) as exc:
        raise _service_error(exc) from exc
    return BillingStatusResponse(
        plan_code=snapshot.plan_code,
        interval=snapshot.interval,
        status=snapshot.status.value,
    )


@router.post("/callback", response_model=BillingStatusResponse)
async def confirm_checkout(
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
    token: Annotated[str, Form(min_length=1, max_length=500)],
) -> BillingStatusResponse:
    try:
        snapshot = await service.confirm_checkout(token)
    except (SubscriptionServiceError, IyzicoError, ValueError) as exc:
        raise _service_error(exc) from exc
    return BillingStatusResponse(
        plan_code=snapshot.plan_code,
        interval=snapshot.interval,
        status=snapshot.status.value,
    )


@router.post("/cancel", response_model=BillingStatusResponse)
async def cancel_subscription(
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> BillingStatusResponse:
    try:
        snapshot = await service.cancel(_user_id(auth))
    except (SubscriptionServiceError, IyzicoError, ValueError) as exc:
        raise _service_error(exc) from exc
    return BillingStatusResponse(
        plan_code=snapshot.plan_code,
        interval=snapshot.interval,
        status=snapshot.status.value,
    )
