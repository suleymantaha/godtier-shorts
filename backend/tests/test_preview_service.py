from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from backend.services.preview.service import (
    PreviewAlreadyUsedError,
    PreviewMetadata,
    PreviewRateLimitedError,
    PreviewService,
    PreviewSourceTooLongError,
    PreviewUrlError,
)


TRANSCRIPT = [
    {"start": 0.0, "end": 20.0, "text": "Ilk dikkat cekici fikir."},
    {"start": 20.0, "end": 45.0, "text": "Ikinci guclu fikir."},
]


class FakeSource:
    def __init__(self, *, duration: int = 120, captions=None) -> None:
        self.metadata = PreviewMetadata(
            video_id="abc123DEF45",
            title="Test video",
            duration_seconds=duration,
            thumbnail_url="https://i.ytimg.com/vi/abc123DEF45/hqdefault.jpg",
        )
        self.captions = captions
        self.calls = 0

    async def inspect(self, _url: str):
        self.calls += 1
        return self.metadata, self.captions


class FakeEntitlements:
    def __init__(self, claim: bool = True) -> None:
        self.claim_result = claim
        self.claimed = 0
        self.released = 0

    async def claim(self, *, user_id, identity_key_hash: str) -> bool:
        assert len(identity_key_hash) == 64
        self.claimed += 1
        return self.claim_result

    async def release(self, *, identity_key_hash: str) -> None:
        self.released += 1


class FakeTranscriber:
    def __init__(self) -> None:
        self.calls = 0

    async def transcribe(self, url: str, *, max_seconds: int):
        self.calls += 1
        assert max_seconds == 900
        return TRANSCRIPT


class FakeRateLimiter:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls = 0

    async def allow(self, *, identity_key_hash: str) -> bool:
        assert len(identity_key_hash) == 64
        self.calls += 1
        return self.allowed


class FakeAnalyzer:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def analyze(self, transcript, *, limit: int):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider unavailable")
        assert transcript == TRANSCRIPT
        assert limit == 3
        return [
            {
                "start_time": index * 10.0,
                "end_time": index * 10.0 + 20.0,
                "hook_text": f"Hook {index}",
                "ui_title": f"Candidate {index}",
                "viral_score": 90 - index,
            }
            for index in range(5)
        ]


def build_service(*, duration=120, captions=TRANSCRIPT, claim=True, analyzer=None, rate_allowed=True):
    source = FakeSource(duration=duration, captions=captions)
    entitlements = FakeEntitlements(claim=claim)
    transcriber = FakeTranscriber()
    analyzer = analyzer or FakeAnalyzer()
    rate_limiter = FakeRateLimiter(rate_allowed)
    service = PreviewService(
        source=source,
        entitlements=entitlements,
        transcriber=transcriber,
        analyzer=analyzer,
        rate_limiter=rate_limiter,
        max_source_seconds=3600,
        max_transcription_seconds=900,
    )
    return service, source, entitlements, transcriber, analyzer, rate_limiter


@pytest.mark.parametrize(
    "url",
    [
        "http://youtube.com/watch?v=abc123DEF45",
        "https://youtube.com.evil.example/watch?v=abc123DEF45",
        "https://user:pass@youtube.com/watch?v=abc123DEF45",
        "https://127.0.0.1/watch?v=abc123DEF45",
        "https://youtube.com:99999/watch?v=abc123DEF45",
    ],
)
def test_preview_rejects_urls_outside_narrow_https_youtube_policy(url: str) -> None:
    service, source, entitlements, *_ = build_service()

    with pytest.raises(PreviewUrlError):
        asyncio.run(service.analyze(url=url, user_id=uuid4(), identity="subject-1"))

    assert source.calls == 0
    assert entitlements.claimed == 0


def test_preview_rejects_long_source_before_consuming_entitlement() -> None:
    service, _, entitlements, *_ = build_service(duration=3601)

    with pytest.raises(PreviewSourceTooLongError):
        asyncio.run(service.analyze(
            url="https://www.youtube.com/watch?v=abc123DEF45",
            user_id=uuid4(),
            identity="subject-1",
        ))

    assert entitlements.claimed == 0


def test_preview_rate_limit_runs_before_remote_metadata_lookup() -> None:
    service, source, entitlements, *_ = build_service(rate_allowed=False)

    with pytest.raises(PreviewRateLimitedError):
        asyncio.run(service.analyze(
            url="https://youtube.com/watch?v=abc123DEF45",
            user_id=uuid4(),
            identity="subject-1",
        ))

    assert source.calls == 0
    assert entitlements.claimed == 0


def test_caption_preview_is_bounded_to_three_candidates_without_transcription() -> None:
    service, _, entitlements, transcriber, analyzer, _ = build_service()

    result = asyncio.run(service.analyze(
        url="https://youtu.be/abc123DEF45",
        user_id=uuid4(),
        identity="subject-1",
    ))

    assert entitlements.claimed == 1
    assert transcriber.calls == 0
    assert analyzer.calls == 1
    assert len(result.candidates) == 3
    assert result.preview_mode == "browser"
    assert result.transcript == TRANSCRIPT
    assert not hasattr(result, "mp4_url")


def test_missing_captions_use_configured_limited_transcriber() -> None:
    service, _, _, transcriber, _, _ = build_service(captions=None)

    result = asyncio.run(service.analyze(
        url="https://youtube.com/watch?v=abc123DEF45",
        user_id=uuid4(),
        identity="subject-1",
    ))

    assert transcriber.calls == 1
    assert result.transcript_source == "limited_transcription"


def test_used_identity_is_rejected_before_expensive_analysis() -> None:
    service, _, _, transcriber, analyzer, _ = build_service(claim=False)

    with pytest.raises(PreviewAlreadyUsedError):
        asyncio.run(service.analyze(
            url="https://youtube.com/watch?v=abc123DEF45",
            user_id=uuid4(),
            identity="subject-1",
        ))

    assert transcriber.calls == 0
    assert analyzer.calls == 0


def test_provider_failure_releases_claim_for_retry() -> None:
    service, _, entitlements, _, _, _ = build_service(analyzer=FakeAnalyzer(fail=True))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(service.analyze(
            url="https://youtube.com/watch?v=abc123DEF45",
            user_id=uuid4(),
            identity="subject-1",
        ))

    assert entitlements.released == 1
