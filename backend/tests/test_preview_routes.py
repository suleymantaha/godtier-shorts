from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import preview
from backend.api.security import AuthContext, authenticate_request
from backend.services.preview.service import PreviewMetadata, PreviewResult
from backend.services.preview.service import PreviewService


class FakePreviewService:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, **kwargs) -> PreviewResult:
        self.calls += 1
        return PreviewResult(
            source=PreviewMetadata("abc123DEF45", "Video", 120, None),
            transcript=[{"start": 0.0, "end": 20.0, "text": "Guclu bir an"}],
            transcript_source="captions",
            candidates=[{"start_time": 0.0, "end_time": 20.0, "ui_title": "Aday"}],
        )


class FakeTurnstileVerifier:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.calls = []

    async def validate(self, token: str, **kwargs) -> None:
        self.calls.append((token, kwargs))
        if not self.valid:
            from backend.services.abuse.turnstile import TurnstileValidationError

            raise TurnstileValidationError(("timeout-or-duplicate",))


def build_app(
    service: FakePreviewService,
    *,
    user_id=True,
    verifier: FakeTurnstileVerifier | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(preview.router)
    app.dependency_overrides[preview.get_preview_service] = lambda: service
    app.dependency_overrides[preview.get_turnstile_verifier] = lambda: (
        verifier or FakeTurnstileVerifier()
    )
    if user_id is not None:
        app.dependency_overrides[authenticate_request] = lambda: AuthContext(
            subject="subject-1",
            roles={"member"},
            token_type="jwt",
            user_id=uuid4() if user_id else None,
        )
    return app


def test_preview_requires_authentication() -> None:
    service = FakePreviewService()
    response = TestClient(build_app(service, user_id=None)).post(
        "/api/preview/analyze",
        json={"url": "https://youtu.be/abc123DEF45", "turnstile_token": "valid-token"},
    )
    assert response.status_code == 401
    assert service.calls == 0


def test_preview_requires_database_identity() -> None:
    service = FakePreviewService()
    response = TestClient(build_app(service, user_id=False)).post(
        "/api/preview/analyze",
        json={"url": "https://youtu.be/abc123DEF45", "turnstile_token": "valid-token"},
    )
    assert response.status_code == 503
    assert service.calls == 0


def test_preview_returns_browser_only_candidate_payload() -> None:
    service = FakePreviewService()
    response = TestClient(build_app(service)).post(
        "/api/preview/analyze",
        json={"url": "https://youtu.be/abc123DEF45", "turnstile_token": "valid-token"},
    )
    assert response.status_code == 200
    assert response.json()["preview_mode"] == "browser"
    assert len(response.json()["candidates"]) == 1
    assert "mp4_url" not in response.json()
    assert service.calls == 1


def test_preview_rejects_missing_or_replayed_turnstile_before_free_work() -> None:
    service = FakePreviewService()
    verifier = FakeTurnstileVerifier(valid=False)
    response = TestClient(build_app(service, verifier=verifier)).post(
        "/api/preview/analyze",
        json={"url": "https://youtu.be/abc123DEF45", "turnstile_token": "replayed-token"},
    )

    assert response.status_code == 403
    assert service.calls == 0
    assert verifier.calls[0][1]["expected_action"] == "preview_analyze"


def test_preview_dependency_factory_returns_preview_service(monkeypatch) -> None:
    monkeypatch.setenv("PREVIEW_LIMITED_TRANSCRIPTION_ENABLED", "false")

    dependency = preview.get_preview_service.__wrapped__ if hasattr(
        preview.get_preview_service, "__wrapped__"
    ) else preview.get_preview_service
    result = asyncio.run(dependency(object()))

    assert isinstance(result, PreviewService)
