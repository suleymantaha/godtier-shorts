from __future__ import annotations

from typing import cast

import pytest

from backend.db.models import JobType, Plan
from backend.services.billing.pricing import (
    EntitlementDenied,
    InvalidPricingRequest,
    JobPricingRequest,
    PlanLimitExceeded,
    estimate_job_cost,
)


def _plan(
    *,
    paid: bool = True,
    max_source_minutes: int = 60,
    max_clips: int = 10,
    priority: int = 0,
) -> Plan:
    return Plan(
        code="creator" if paid else "free",
        name="Creator" if paid else "Free",
        monthly_price_minor=9900 if paid else 0,
        currency="TRY",
        monthly_compute_credits=1_000 if paid else 0,
        max_source_minutes_per_job=max_source_minutes,
        max_clips_per_job=max_clips,
        max_active_jobs=2,
        retention_days=30,
        priority=priority,
        active=True,
    )


def test_standard_paid_job_cost_has_transparent_components() -> None:
    estimate = estimate_job_cost(
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=600,
            requested_clips=3,
            resolution="1080p",
        ),
        _plan(),
    )

    assert estimate.source_credits == 20
    assert estimate.clip_credits == 12
    assert estimate.resolution_multiplier_bp == 1_400
    assert estimate.premium_multiplier_bp == 1_000
    assert estimate.priority_multiplier_bp == 1_000
    assert estimate.total_credits == 45
    assert estimate.wallet_credits == 45
    assert estimate.abuse_telemetry_credits == 0
    assert estimate.requires_paid_entitlement is True


def test_premium_layout_and_priority_multipliers_apply_once() -> None:
    estimate = estimate_job_cost(
        JobPricingRequest(
            job_type=JobType.BATCH,
            source_seconds=600,
            requested_clips=3,
            resolution="1080p",
            layout="split",
            premium_features=frozenset({"kinetic_subtitles", "watermark_removal"}),
            priority=True,
        ),
        _plan(priority=1),
    )

    assert estimate.premium_multiplier_bp == 1_250
    assert estimate.priority_multiplier_bp == 1_250
    assert estimate.total_credits == 70
    assert estimate.wallet_credits == 70


@pytest.mark.parametrize(
    "pricing_request",
    [
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=301,
            requested_clips=1,
            resolution="720p",
        ),
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=300,
            requested_clips=3,
            resolution="720p",
        ),
    ],
)
def test_plan_source_and_clip_limits_are_enforced(pricing_request: JobPricingRequest) -> None:
    with pytest.raises(PlanLimitExceeded):
        estimate_job_cost(pricing_request, _plan(max_source_minutes=5, max_clips=2))


def test_free_preview_records_internal_cost_without_charging_wallet() -> None:
    estimate = estimate_job_cost(
        JobPricingRequest(
            job_type=JobType.PREVIEW,
            source_seconds=180,
            requested_clips=3,
            resolution="720p",
        ),
        _plan(paid=False, max_source_minutes=30, max_clips=10),
    )

    assert estimate.total_credits == 22
    assert estimate.wallet_credits == 0
    assert estimate.abuse_telemetry_credits == 22
    assert estimate.requires_paid_entitlement is False


def test_free_plan_cannot_authorize_full_production_render() -> None:
    request = JobPricingRequest(
        job_type=JobType.FULL_RENDER,
        source_seconds=180,
        requested_clips=1,
        resolution="720p",
    )

    with pytest.raises(EntitlementDenied):
        estimate_job_cost(request, _plan(paid=False))


@pytest.mark.parametrize(
    "pricing_request",
    [
        JobPricingRequest(
            job_type=JobType.PREVIEW,
            source_seconds=901,
            requested_clips=3,
            resolution="720p",
        ),
        JobPricingRequest(
            job_type=JobType.PREVIEW,
            source_seconds=180,
            requested_clips=4,
            resolution="720p",
        ),
        JobPricingRequest(
            job_type=JobType.PREVIEW,
            source_seconds=180,
            requested_clips=3,
            resolution="1080p",
        ),
        JobPricingRequest(
            job_type=JobType.PREVIEW,
            source_seconds=180,
            requested_clips=3,
            resolution="720p",
            layout="split",
        ),
    ],
)
def test_free_preview_is_strictly_bounded(pricing_request: JobPricingRequest) -> None:
    with pytest.raises(EntitlementDenied):
        estimate_job_cost(pricing_request, _plan(paid=False, max_source_minutes=60, max_clips=20))


def test_priority_requires_plan_entitlement() -> None:
    request = JobPricingRequest(
        job_type=JobType.FULL_RENDER,
        source_seconds=180,
        requested_clips=1,
        resolution="720p",
        priority=True,
    )

    with pytest.raises(EntitlementDenied):
        estimate_job_cost(request, _plan(paid=True, priority=0))


@pytest.mark.parametrize(
    "pricing_request",
    [
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=0,
            requested_clips=1,
            resolution="720p",
        ),
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=180,
            requested_clips=1,
            resolution="8k",
        ),
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=180,
            requested_clips=1,
            resolution="720p",
            layout="grid",
        ),
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=180,
            requested_clips=1,
            resolution=cast(str, None),
        ),
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=180,
            requested_clips=1,
            resolution="720p",
            layout=cast(str, None),
        ),
        JobPricingRequest(
            job_type=JobType.FULL_RENDER,
            source_seconds=180,
            requested_clips=1,
            resolution="720p",
            premium_features=frozenset({""}),
        ),
    ],
)
def test_invalid_internal_pricing_request_is_rejected(pricing_request: JobPricingRequest) -> None:
    with pytest.raises(InvalidPricingRequest):
        estimate_job_cost(pricing_request, _plan())
