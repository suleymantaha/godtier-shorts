from __future__ import annotations

import pytest

from backend.core.source_url_policy import SourceUrlPolicy, SourceUrlPolicyError
from backend.services.preview.adapters import YtDlpCaptionSource


def source() -> YtDlpCaptionSource:
    return YtDlpCaptionSource(
        source_url_policy=SourceUrlPolicy(
            resolver=lambda _host: ("142.250.184.206",)
        )
    )


def test_ytdlp_result_revalidates_redirected_webpage_url() -> None:
    with pytest.raises(SourceUrlPolicyError):
        source().validate_result_redirects(
            "https://youtube.com/watch?v=abc123DEF45",
            {
                "original_url": "https://youtube.com/watch?v=abc123DEF45",
                "webpage_url": "https://127.0.0.1/internal",
            },
        )


def test_ytdlp_result_accepts_supported_redirect_destination() -> None:
    source().validate_result_redirects(
        "https://youtube.com/watch?v=abc123DEF45",
        {"webpage_url": "https://www.youtube.com/watch?v=abc123DEF45"},
    )
