from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse
from uuid import UUID


ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}


class PreviewError(ValueError):
    pass


class PreviewUrlError(PreviewError):
    pass


class PreviewSourceTooLongError(PreviewError):
    pass


class PreviewAlreadyUsedError(PreviewError):
    pass


class PreviewRateLimitedError(PreviewError):
    pass


@dataclass(frozen=True, slots=True)
class PreviewMetadata:
    video_id: str
    title: str
    duration_seconds: int
    thumbnail_url: str | None


@dataclass(frozen=True, slots=True)
class PreviewResult:
    source: PreviewMetadata
    transcript: list[dict[str, Any]]
    transcript_source: str
    candidates: list[dict[str, Any]]
    preview_mode: str = field(default="browser", init=False)


class PreviewSource(Protocol):
    async def inspect(
        self, url: str
    ) -> tuple[PreviewMetadata, list[dict[str, Any]] | None]: ...


class PreviewEntitlements(Protocol):
    async def claim(self, *, user_id: UUID, identity_key_hash: str) -> bool: ...

    async def release(self, *, identity_key_hash: str) -> None: ...


class LimitedTranscriber(Protocol):
    async def transcribe(
        self, url: str, *, max_seconds: int
    ) -> list[dict[str, Any]]: ...


class PreviewAnalyzer(Protocol):
    async def analyze(
        self, transcript: list[dict[str, Any]], *, limit: int
    ) -> list[dict[str, Any]]: ...


class PreviewRateLimiter(Protocol):
    async def allow(self, *, identity_key_hash: str) -> bool: ...


def validate_preview_url(url: str) -> str:
    parsed = urlparse(url.strip())
    try:
        port = parsed.port
    except ValueError as exc:
        raise PreviewUrlError("Gecersiz YouTube URL portu") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_YOUTUBE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise PreviewUrlError("Yalnizca HTTPS YouTube video URL'leri desteklenir")

    if parsed.hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    else:
        path_parts = parsed.path.strip("/").split("/")
        video_id = (
            path_parts[1]
            if len(path_parts) == 2 and path_parts[0] in {"shorts", "embed"}
            else parse_qs(parsed.query).get("v", [""])[0]
        )
    if not video_id or len(video_id) > 32 or not all(c.isalnum() or c in "-_" for c in video_id):
        raise PreviewUrlError("Gecerli bir YouTube video kimligi gerekli")
    return url.strip()


class PreviewService:
    def __init__(
        self,
        *,
        source: PreviewSource,
        entitlements: PreviewEntitlements,
        transcriber: LimitedTranscriber,
        analyzer: PreviewAnalyzer,
        rate_limiter: PreviewRateLimiter,
        max_source_seconds: int,
        max_transcription_seconds: int,
    ) -> None:
        self._source = source
        self._entitlements = entitlements
        self._transcriber = transcriber
        self._analyzer = analyzer
        self._rate_limiter = rate_limiter
        self._max_source_seconds = max_source_seconds
        self._max_transcription_seconds = max_transcription_seconds

    async def analyze(self, *, url: str, user_id: UUID, identity: str) -> PreviewResult:
        safe_url = validate_preview_url(url)
        identity_hash = hashlib.sha256(f"preview-v1:{identity}".encode()).hexdigest()
        if not await self._rate_limiter.allow(identity_key_hash=identity_hash):
            raise PreviewRateLimitedError("Cok sik analiz istegi gonderildi")
        metadata, captions = await self._source.inspect(safe_url)
        if metadata.duration_seconds <= 0 or metadata.duration_seconds > self._max_source_seconds:
            raise PreviewSourceTooLongError(
                f"Kaynak video en fazla {self._max_source_seconds} saniye olabilir"
            )

        claimed = await self._entitlements.claim(
            user_id=user_id, identity_key_hash=identity_hash
        )
        if not claimed:
            raise PreviewAlreadyUsedError("Ucretsiz analiz hakki daha once kullanilmis")

        try:
            if captions:
                transcript = captions
                transcript_source = "captions"
            else:
                transcript = await self._transcriber.transcribe(
                    safe_url, max_seconds=self._max_transcription_seconds
                )
                transcript_source = "limited_transcription"
            candidates = await self._analyzer.analyze(transcript, limit=3)
            return PreviewResult(
                source=metadata,
                transcript=transcript,
                transcript_source=transcript_source,
                candidates=candidates[:3],
            )
        except Exception:
            await self._entitlements.release(identity_key_hash=identity_hash)
            raise
