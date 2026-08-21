from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.core.source_url_policy import DEFAULT_SOURCE_URL_POLICY, SourceUrlPolicy
from backend.services.preview.service import PreviewMetadata
from backend.services.viral_analyzer import ViralAnalyzer


def _parse_json3(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    transcript: list[dict[str, Any]] = []
    for event in data.get("events", []):
        text = "".join(str(seg.get("utf8", "")) for seg in event.get("segs", [])).strip()
        if not text or text == "\n":
            continue
        start = float(event.get("tStartMs", 0)) / 1000
        duration = float(event.get("dDurationMs", 0)) / 1000
        transcript.append({"start": start, "end": start + duration, "text": text})
    return transcript


class YtDlpCaptionSource:
    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        source_url_policy: SourceUrlPolicy = DEFAULT_SOURCE_URL_POLICY,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._source_url_policy = source_url_policy

    def validate_result_redirects(self, requested_url: str, info: dict[str, Any]) -> None:
        redirect_destinations = [
            str(info[key])
            for key in ("original_url", "webpage_url")
            if info.get(key) and str(info[key]) != requested_url
        ]
        self._source_url_policy.validate_redirect_chain(
            requested_url, redirect_destinations
        )

    async def inspect(self, url: str):
        try:
            return await asyncio.to_thread(self._inspect_sync, url)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("YouTube preview metadata is unavailable") from exc

    def _inspect_sync(self, url: str):
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError("yt-dlp preview dependency is unavailable") from exc

        with tempfile.TemporaryDirectory(prefix="godtier-preview-") as temp_dir:
            options = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["tr", "en", "tr-orig", "en-orig"],
                "subtitlesformat": "json3",
                "outtmpl": str(Path(temp_dir) / "%(id)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": self._timeout_seconds,
            }
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
            if not isinstance(info, dict):
                raise RuntimeError("YouTube metadata could not be read")
            self.validate_result_redirects(url, info)
            subtitle_files = sorted(Path(temp_dir).glob("*.json3"))
            captions = _parse_json3(subtitle_files[0]) if subtitle_files else None
            metadata = PreviewMetadata(
                video_id=str(info.get("id") or ""),
                title=str(info.get("title") or "YouTube video"),
                duration_seconds=int(info.get("duration") or 0),
                thumbnail_url=str(info["thumbnail"]) if info.get("thumbnail") else None,
            )
            return metadata, captions


class LocalPreviewAnalyzer:
    def __init__(self) -> None:
        self._analyzer = ViralAnalyzer(engine="local")

    async def analyze(self, transcript: list[dict[str, Any]], *, limit: int):
        result = await asyncio.to_thread(
            self._analyzer.analyze_transcript_segment,
            transcript,
            limit,
            0,
            0,
            15.0,
            60.0,
        )
        return list((result or {}).get("segments", []))[:limit]


class DisabledLimitedTranscriber:
    async def transcribe(self, url: str, *, max_seconds: int):
        raise RuntimeError(
            "Video captions are unavailable and limited transcription is disabled"
        )


class RemoteLimitedTranscriber:
    """Sends only a bounded audio range to a configured transcription provider."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        parsed = urlparse(endpoint_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("preview transcription endpoint must be a trusted HTTPS URL")
        if not api_key.strip():
            raise ValueError("preview transcription API key is required")
        self._endpoint_url = endpoint_url
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def transcribe(self, url: str, *, max_seconds: int):
        try:
            with tempfile.TemporaryDirectory(prefix="godtier-preview-audio-") as temp_dir:
                audio_path = await asyncio.to_thread(
                    self._download_bounded_audio, url, max_seconds, Path(temp_dir)
                )
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    with audio_path.open("rb") as audio_file:
                        response = await client.post(
                            self._endpoint_url,
                            headers={"Authorization": f"Bearer {self._api_key}"},
                            data={"model": self._model, "response_format": "verbose_json"},
                            files={"file": ("preview.wav", audio_file, "audio/wav")},
                        )
                response.raise_for_status()
                payload = response.json()
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("limited transcription provider is unavailable") from exc
            segments = payload.get("segments", []) if isinstance(payload, dict) else []
            return [
                {
                    "start": float(segment["start"]),
                    "end": float(segment["end"]),
                    "text": str(segment.get("text", "")).strip(),
                }
                for segment in segments
                if isinstance(segment, dict)
                and segment.get("text")
                and isinstance(segment.get("start"), (int, float))
                and isinstance(segment.get("end"), (int, float))
            ]

    def _download_bounded_audio(self, url: str, max_seconds: int, temp_dir: Path) -> Path:
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import download_range_func
        except ImportError as exc:
            raise RuntimeError("limited transcription dependency is unavailable") from exc

        options = {
            "format": "bestaudio/best",
            "download_ranges": download_range_func(None, [(0, max_seconds)]),
            "force_keyframes_at_cuts": True,
            "outtmpl": str(temp_dir / "preview.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self._timeout_seconds,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        }
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        audio_files = list(temp_dir.glob("*.wav"))
        if not audio_files:
            raise RuntimeError("bounded preview audio could not be downloaded")
        return audio_files[0]
