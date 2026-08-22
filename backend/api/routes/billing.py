from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.rate_limit import enforce_rate_limit, get_rate_limiter
from backend.api.security import AuthContext, authenticate_request
from backend.db.session import get_db_session
from backend.services.abuse.rate_limit import RedisFixedWindowRateLimiter
from backend.services.billing.account_service import (
    BillingAccountService,
    SqlAlchemyBillingAccountRepository,
)
from backend.services.billing.iyzico_client import IyzicoClient, IyzicoError
from backend.services.billing.subscription_service import (
    BillingInterval,
    PlanReferenceMap,
    SqlAlchemySubscriptionRepository,
    SubscriptionService,
    SubscriptionServiceError,
    paid_entitlement_is_active,
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


class PlanChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=1, max_length=50)
    interval: BillingInterval


class CheckoutResponse(BaseModel):
    token: str
    checkout_form_content: str
    expires_in_seconds: int


class BillingStatusResponse(BaseModel):
    plan_code: str
    interval: BillingInterval
    status: str
    entitlement_active: bool


class BillingPlanResponse(BaseModel):
    code: str
    name: str
    monthly_price_minor: int
    currency: str
    monthly_compute_credits: int
    max_source_minutes_per_job: int
    max_clips_per_job: int
    max_active_jobs: int
    retention_days: int


class BillingAccountSubscriptionResponse(BaseModel):
    plan: BillingPlanResponse
    interval: str | None
    status: str
    entitlement_active: bool
    period_start: str | None
    period_end: str | None
    cancel_at_period_end: bool
    grace_until: str | None


class BillingUsageResponse(BaseModel):
    current_period_source_seconds: int
    source_seconds_per_job_limit: int
    compute_credits_used: int
    compute_credits_available: int
    compute_credits_reserved: int


class BillingPaymentResponse(BaseModel):
    id: str
    amount_minor: int
    currency: str
    status: str
    created_at: str


class BillingAccountResponse(BaseModel):
    subscription: BillingAccountSubscriptionResponse | None
    plans: list[BillingPlanResponse]
    usage: BillingUsageResponse
    payments: list[BillingPaymentResponse]


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


async def get_billing_account_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BillingAccountService:
    return BillingAccountService(SqlAlchemyBillingAccountRepository(session))


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


def _plan_response(plan) -> BillingPlanResponse:
    return BillingPlanResponse(
        code=plan.code,
        name=plan.name,
        monthly_price_minor=plan.monthly_price_minor,
        currency=plan.currency,
        monthly_compute_credits=plan.monthly_compute_credits,
        max_source_minutes_per_job=plan.max_source_minutes_per_job,
        max_clips_per_job=plan.max_clips_per_job,
        max_active_jobs=plan.max_active_jobs,
        retention_days=plan.retention_days,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
    limiter: Annotated[RedisFixedWindowRateLimiter, Depends(get_rate_limiter)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> CheckoutResponse:
    user_id = _user_id(auth)
    subject = str(user_id)
    await enforce_rate_limit(
        limiter,
        scope="checkout_failed",
        subject=subject,
        limit=int(os.getenv("BILLING_FAILED_CHECKOUT_LIMIT", "3")),
        window_seconds=int(
            os.getenv("BILLING_FAILED_CHECKOUT_WINDOW_SECONDS", "600")
        ),
        consume=False,
    )
    await enforce_rate_limit(
        limiter,
        scope="checkout",
        subject=subject,
        limit=int(os.getenv("BILLING_CHECKOUT_REQUEST_LIMIT", "5")),
        window_seconds=int(
            os.getenv("BILLING_CHECKOUT_REQUEST_WINDOW_SECONDS", "60")
        ),
    )
    try:
        checkout = await service.create_checkout(
            user_id=user_id,
            plan_code=request.plan_code,
            interval=request.interval,
            customer=request.customer.provider_payload(),
            idempotency_key=idempotency_key,
        )
    except (SubscriptionServiceError, IyzicoError, ValueError) as exc:
        await enforce_rate_limit(
            limiter,
            scope="checkout_failed",
            subject=subject,
            limit=int(os.getenv("BILLING_FAILED_CHECKOUT_LIMIT", "3")),
            window_seconds=int(
                os.getenv("BILLING_FAILED_CHECKOUT_WINDOW_SECONDS", "600")
            ),
        )
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
        entitlement_active=snapshot.entitlement_active,
    )


@router.get("/account", response_model=BillingAccountResponse)
async def get_billing_account(
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    subscription_service: Annotated[SubscriptionService, Depends(get_subscription_service)],
    account_service: Annotated[BillingAccountService, Depends(get_billing_account_service)],
) -> BillingAccountResponse:
    user_id = _user_id(auth)
    interval = None
    try:
        status_snapshot = await subscription_service.get_status(user_id)
        interval = status_snapshot.interval.value
    except SubscriptionServiceError as exc:
        if str(exc) != "subscription bulunamadi":
            raise _service_error(exc) from exc
    except (IyzicoError, ValueError) as exc:
        raise _service_error(exc) from exc
    account = await account_service.get_account(user_id, interval=interval)
    subscription = None
    if account.subscription is not None:
        item = account.subscription
        subscription = BillingAccountSubscriptionResponse(
            plan=_plan_response(item.plan),
            interval=item.interval,
            status=item.status.value,
            entitlement_active=paid_entitlement_is_active(item.status, grace_until=item.grace_until),
            period_start=item.period_start.isoformat() if item.period_start else None,
            period_end=item.period_end.isoformat() if item.period_end else None,
            cancel_at_period_end=item.cancel_at_period_end,
            grace_until=item.grace_until.isoformat() if item.grace_until else None,
        )
    return BillingAccountResponse(
        subscription=subscription,
        plans=[_plan_response(plan) for plan in account.plans],
        usage=BillingUsageResponse(
            current_period_source_seconds=account.source_seconds_used,
            source_seconds_per_job_limit=account.source_seconds_per_job_limit,
            compute_credits_used=account.compute_credits_used,
            compute_credits_available=account.compute_credits_available,
            compute_credits_reserved=account.compute_credits_reserved,
        ),
        payments=[
            BillingPaymentResponse(
                id=str(payment.id),
                amount_minor=payment.amount_minor,
                currency=payment.currency,
                status=payment.status.value,
                created_at=payment.created_at.isoformat(),
            )
            for payment in account.payments
        ],
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
        entitlement_active=snapshot.entitlement_active,
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
        entitlement_active=snapshot.entitlement_active,
    )


@router.post("/plan", response_model=BillingStatusResponse)
async def change_subscription_plan(
    request: PlanChangeRequest,
    auth: Annotated[AuthContext, Depends(authenticate_request)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> BillingStatusResponse:
    try:
        snapshot = await service.change_plan(_user_id(auth), request.plan_code, request.interval)
    except (SubscriptionServiceError, IyzicoError, ValueError) as exc:
        raise _service_error(exc) from exc
    return BillingStatusResponse(
        plan_code=snapshot.plan_code,
        interval=snapshot.interval,
        status=snapshot.status.value,
        entitlement_active=snapshot.entitlement_active,
    )
