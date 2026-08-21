from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from backend.services.abuse.turnstile import (
    TurnstileProviderError,
    TurnstileValidationError,
    TurnstileVerifier,
)


ROOT = Path(__file__).resolve().parents[2]


def build_verifier(payload: dict, *, status_code: int = 200) -> TurnstileVerifier:
    async def handler(request: httpx.Request) -> httpx.Response:
        submitted = dict(httpx.QueryParams(request.content.decode()))
        assert submitted["secret"] == "server-secret"
        assert submitted["response"] == "browser-token"
        assert submitted["remoteip"] == "203.0.113.10"
        assert submitted["idempotency_key"]
        return httpx.Response(status_code, content=json.dumps(payload).encode())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TurnstileVerifier(
        secret_key="server-secret",
        client=client,
        expected_hostname="app.example.com",
    )


def test_valid_token_requires_matching_action_and_hostname() -> None:
    verifier = build_verifier(
        {
            "success": True,
            "action": "preview_analyze",
            "hostname": "app.example.com",
            "challenge_ts": "2026-08-21T20:00:00Z",
        }
    )

    result = asyncio.run(
        verifier.validate(
            "browser-token",
            remote_ip="203.0.113.10",
            expected_action="preview_analyze",
        )
    )

    assert result.action == "preview_analyze"
    assert result.hostname == "app.example.com"


@pytest.mark.parametrize("error_code", ["timeout-or-duplicate", "invalid-input-response"])
def test_expired_replayed_or_invalid_token_is_rejected(error_code: str) -> None:
    verifier = build_verifier({"success": False, "error-codes": [error_code]})

    with pytest.raises(TurnstileValidationError) as error:
        asyncio.run(
            verifier.validate(
                "browser-token",
                remote_ip="203.0.113.10",
                expected_action="preview_analyze",
            )
        )

    assert error_code in error.value.error_codes


@pytest.mark.parametrize(
    "payload",
    [
        {"success": True, "action": "signup", "hostname": "app.example.com"},
        {"success": True, "action": "preview_analyze", "hostname": "evil.example"},
    ],
)
def test_action_or_hostname_mismatch_fails_closed(payload: dict) -> None:
    verifier = build_verifier(payload)

    with pytest.raises(TurnstileValidationError):
        asyncio.run(
            verifier.validate(
                "browser-token",
                remote_ip="203.0.113.10",
                expected_action="preview_analyze",
            )
        )


def test_network_failure_is_provider_error_without_leaking_secret() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    verifier = TurnstileVerifier(
        secret_key="do-not-leak",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(TurnstileProviderError) as error:
        asyncio.run(verifier.validate("browser-token", expected_action="signup"))

    assert "do-not-leak" not in str(error.value)
    assert error.value.__cause__ is None


def test_missing_or_oversized_token_is_rejected_without_provider_call() -> None:
    verifier = build_verifier({"success": True})

    for token in ("", "x" * 2049):
        with pytest.raises(TurnstileValidationError):
            asyncio.run(verifier.validate(token, expected_action="signup"))


def test_secret_key_is_not_exposed_through_vite_frontend_source() -> None:
    frontend_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".ts", ".tsx"}
    )

    assert "VITE_TURNSTILE_SECRET_KEY" not in frontend_source
    assert "TURNSTILE_SECRET_KEY" not in frontend_source
