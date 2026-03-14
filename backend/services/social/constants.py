"""Constants and platform mappings for social publishing."""

from __future__ import annotations

from typing import Final

SUPPORTED_SOCIAL_PLATFORMS: Final[tuple[str, ...]] = (
    "youtube_shorts",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x",
    "linkedin",
)

POSTIZ_TO_PLATFORM: Final[dict[str, str]] = {
    "youtube": "youtube_shorts",
    "tiktok": "tiktok",
    "instagram": "instagram_reels",
    "instagram-standalone": "instagram_reels",
    "facebook": "facebook_reels",
    "x": "x",
    "twitter": "x",
    "linkedin": "linkedin",
    "linkedin-page": "linkedin",
}

PLATFORM_TO_POSTIZ: Final[dict[str, str]] = {
    value: key for key, value in POSTIZ_TO_PLATFORM.items()
}
PLATFORM_TO_POSTIZ["x"] = "x"
PLATFORM_TO_POSTIZ["linkedin"] = "linkedin"

PLATFORM_MAX_HASHTAGS: Final[dict[str, int]] = {
    "youtube_shorts": 15,
    "tiktok": 30,
    "instagram_reels": 30,
    "facebook_reels": 30,
    "x": 5,
    "linkedin": 5,
}

PLATFORM_MAX_TEXT: Final[dict[str, int]] = {
    "x": 280,
    "linkedin": 3000,
    "youtube_shorts": 5000,
    "tiktok": 2200,
    "instagram_reels": 2200,
    "facebook_reels": 2200,
}

SOCIAL_PROVIDER_POSTIZ = "postiz"

PUBLISH_FINAL_STATES: Final[set[str]] = {
    "published",
    "failed",
    "cancelled",
}

PUBLISH_ACTIVE_STATES: Final[set[str]] = {
    "draft",
    "queued",
    "scheduled",
    "retrying",
    "pending_approval",
    "publishing",
}

MAX_DIRECT_UPLOAD_BYTES: Final[int] = 200 * 1024 * 1024
