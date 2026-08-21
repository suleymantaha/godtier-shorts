from __future__ import annotations

from dataclasses import dataclass, field

from backend.db.models import JobType, Plan


SOURCE_BUCKET_SECONDS = 5 * 60
SOURCE_BUCKET_CREDITS = 10
CLIP_CREDITS = 4
FREE_PREVIEW_MAX_SOURCE_SECONDS = 15 * 60
FREE_PREVIEW_MAX_CLIPS = 3
BASE_MULTIPLIER_BP = 1_000
PREMIUM_MULTIPLIER_BP = 1_250
PRIORITY_MULTIPLIER_BP = 1_250
RESOLUTION_MULTIPLIERS_BP = {
    "720p": 1_000,
    "1080p": 1_400,
    "1440p": 1_800,
    "2160p": 2_500,
}
RESOLUTION_ALIASES = {
    "720": "720p",
    "1080": "1080p",
    "best": "1080p",
    "1440": "1440p",
    "2160": "2160p",
    "4k": "2160p",
}
VALID_LAYOUTS = {"auto", "single", "split"}


class PricingError(ValueError):
    pass


class InvalidPricingRequest(PricingError):
    pass


class PlanLimitExceeded(PricingError):
    pass


class EntitlementDenied(PricingError):
    pass


@dataclass(frozen=True, slots=True)
class JobPricingRequest:
    job_type: JobType
    source_seconds: int
    requested_clips: int
    resolution: str
    layout: str = "single"
    premium_features: frozenset[str] = field(default_factory=frozenset)
    priority: bool = False


@dataclass(frozen=True, slots=True)
class CostEstimate:
    source_credits: int
    clip_credits: int
    resolution_multiplier_bp: int
    premium_multiplier_bp: int
    priority_multiplier_bp: int
    total_credits: int
    wallet_credits: int
    abuse_telemetry_credits: int
    requires_paid_entitlement: bool


def _ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def _normalize_request(request: JobPricingRequest) -> tuple[str, str]:
    if not isinstance(request.job_type, JobType):
        raise InvalidPricingRequest("job_type gecersiz")
    if (
        isinstance(request.source_seconds, bool)
        or not isinstance(request.source_seconds, int)
        or request.source_seconds <= 0
    ):
        raise InvalidPricingRequest("source_seconds pozitif bir tam sayi olmali")
    if (
        isinstance(request.requested_clips, bool)
        or not isinstance(request.requested_clips, int)
        or request.requested_clips <= 0
    ):
        raise InvalidPricingRequest("requested_clips pozitif bir tam sayi olmali")

    if not isinstance(request.resolution, str):
        raise InvalidPricingRequest("resolution must be a string")
    resolution = request.resolution.strip().lower()
    resolution = RESOLUTION_ALIASES.get(resolution, resolution)
    if resolution not in RESOLUTION_MULTIPLIERS_BP:
        raise InvalidPricingRequest("resolution desteklenmiyor")
    if not isinstance(request.layout, str):
        raise InvalidPricingRequest("layout must be a string")
    layout = request.layout.strip().lower()
    if layout not in VALID_LAYOUTS:
        raise InvalidPricingRequest("layout desteklenmiyor")
    if any(not isinstance(feature, str) or not feature.strip() for feature in request.premium_features):
        raise InvalidPricingRequest("premium_features gecersiz")
    return resolution, layout


def _enforce_plan_limits(request: JobPricingRequest, plan: Plan) -> None:
    if not plan.active:
        raise EntitlementDenied("plan aktif degil")
    if request.source_seconds > plan.max_source_minutes_per_job * 60:
        raise PlanLimitExceeded("kaynak suresi plan limitini asiyor")
    if request.requested_clips > plan.max_clips_per_job:
        raise PlanLimitExceeded("istenen klip sayisi plan limitini asiyor")


def _enforce_entitlement(
    request: JobPricingRequest,
    plan: Plan,
    *,
    resolution: str,
    layout: str,
) -> None:
    if request.job_type is JobType.PREVIEW:
        if (
            request.source_seconds > FREE_PREVIEW_MAX_SOURCE_SECONDS
            or request.requested_clips > FREE_PREVIEW_MAX_CLIPS
            or resolution != "720p"
            or layout != "single"
            or bool(request.premium_features)
            or request.priority
        ):
            raise EntitlementDenied("ucretsiz preview sinirlari asildi")
        return

    if plan.monthly_price_minor <= 0:
        raise EntitlementDenied("production render icin ucretli plan gerekli")
    if request.priority and plan.priority <= 0:
        raise EntitlementDenied("priority render bu planda kullanilamaz")


def estimate_job_cost(request: JobPricingRequest, plan: Plan) -> CostEstimate:
    resolution, layout = _normalize_request(request)
    _enforce_plan_limits(request, plan)
    _enforce_entitlement(request, plan, resolution=resolution, layout=layout)

    source_credits = _ceil_div(request.source_seconds, SOURCE_BUCKET_SECONDS) * SOURCE_BUCKET_CREDITS
    clip_credits = request.requested_clips * CLIP_CREDITS
    resolution_multiplier_bp = RESOLUTION_MULTIPLIERS_BP[resolution]
    premium_multiplier_bp = (
        PREMIUM_MULTIPLIER_BP
        if layout in {"auto", "split"} or request.premium_features
        else BASE_MULTIPLIER_BP
    )
    priority_multiplier_bp = PRIORITY_MULTIPLIER_BP if request.priority else BASE_MULTIPLIER_BP
    total_credits = _ceil_div(
        (source_credits + clip_credits)
        * resolution_multiplier_bp
        * premium_multiplier_bp
        * priority_multiplier_bp,
        BASE_MULTIPLIER_BP**3,
    )
    is_preview = request.job_type is JobType.PREVIEW
    return CostEstimate(
        source_credits=source_credits,
        clip_credits=clip_credits,
        resolution_multiplier_bp=resolution_multiplier_bp,
        premium_multiplier_bp=premium_multiplier_bp,
        priority_multiplier_bp=priority_multiplier_bp,
        total_credits=total_credits,
        wallet_credits=0 if is_preview else total_credits,
        abuse_telemetry_credits=total_credits if is_preview else 0,
        requires_paid_entitlement=not is_preview,
    )
