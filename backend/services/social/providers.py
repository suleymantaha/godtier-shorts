"""Provider registry for the native social suite."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SocialProviderDescriptor:
    platform: str
    title: str
    description: str
    integrations: tuple[str, ...]
    analytics_supported: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SOCIAL_PROVIDER_DESCRIPTORS: tuple[SocialProviderDescriptor, ...] = (
    SocialProviderDescriptor(
        platform="youtube_shorts",
        title="YouTube Shorts",
        description="Short-form video publishing and channel analytics.",
        integrations=("youtube",),
    ),
    SocialProviderDescriptor(
        platform="tiktok",
        title="TikTok",
        description="Vertical short video publishing and performance tracking.",
        integrations=("tiktok",),
    ),
    SocialProviderDescriptor(
        platform="instagram_reels",
        title="Instagram Reels",
        description="Instagram Reels publishing for linked and standalone accounts.",
        integrations=("instagram", "instagram-standalone"),
    ),
    SocialProviderDescriptor(
        platform="facebook_reels",
        title="Facebook Reels",
        description="Facebook page video publishing and schedule management.",
        integrations=("facebook",),
    ),
    SocialProviderDescriptor(
        platform="x",
        title="X",
        description="Short-form social posting and threaded campaign tracking.",
        integrations=("x", "twitter"),
    ),
    SocialProviderDescriptor(
        platform="linkedin",
        title="LinkedIn",
        description="Professional publishing for profile and page destinations.",
        integrations=("linkedin", "linkedin-page"),
    ),
)

_PLATFORM_INDEX = {item.platform: item for item in SOCIAL_PROVIDER_DESCRIPTORS}
_INTEGRATION_INDEX = {
    integration: descriptor.platform
    for descriptor in SOCIAL_PROVIDER_DESCRIPTORS
    for integration in descriptor.integrations
}


def list_social_provider_descriptors() -> list[SocialProviderDescriptor]:
    return list(SOCIAL_PROVIDER_DESCRIPTORS)


def get_social_provider_descriptor(platform: str) -> SocialProviderDescriptor:
    normalized = str(platform or "").strip().lower()
    descriptor = _PLATFORM_INDEX.get(normalized)
    if descriptor is None:
        raise ValueError(f"Desteklenmeyen sosyal platform: {platform}")
    return descriptor


def get_primary_postiz_integration(platform: str) -> str:
    descriptor = get_social_provider_descriptor(platform)
    return descriptor.integrations[0]


def resolve_platform_from_integration(integration: str | None) -> str | None:
    normalized = str(integration or "").strip().lower()
    if not normalized:
        return None
    return _INTEGRATION_INDEX.get(normalized)
