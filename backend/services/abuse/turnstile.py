from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx


SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
MAX_TOKEN_LENGTH = 2048


class TurnstileValidationError(ValueError):
    def __init__(self, error_codes: tuple[str, ...]) -> None:
        super().__init__("Turnstile verification failed")
        self.error_codes = error_codes


class TurnstileProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TurnstileResult:
    action: str
    hostname: str
    challenge_timestamp: str | None


class TurnstileVerifier:
    def __init__(
        self,
        *,
        secret_key: str,
        client: httpx.AsyncClient | None = None,
        expected_hostname: str | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if not secret_key.strip():
            raise ValueError("Turnstile secret key is required")
        self._secret_key = secret_key
        self._client = client
        self._expected_hostname = (expected_hostname or "").strip().lower() or None
        self._timeout_seconds = timeout_seconds

    async def validate(
        self,
        token: str,
        *,
        expected_action: str,
        remote_ip: str | None = None,
    ) -> TurnstileResult:
        normalized_token = token.strip()
        if not normalized_token or len(normalized_token) > MAX_TOKEN_LENGTH:
            raise TurnstileValidationError(("invalid-input-response",))
        if not expected_action.strip():
            raise ValueError("Expected Turnstile action is required")

        form = {
            "secret": self._secret_key,
            "response": normalized_token,
            "idempotency_key": str(uuid4()),
        }
        if remote_ip:
            form["remoteip"] = remote_ip

        payload = await self._siteverify(form)
        error_codes = self._error_codes(payload)
        if payload.get("success") is not True:
            raise TurnstileValidationError(error_codes or ("verification-failed",))

        action = str(payload.get("action") or "")
        hostname = str(payload.get("hostname") or "").lower()
        if action != expected_action:
            raise TurnstileValidationError(("action-mismatch",))
        if self._expected_hostname and hostname != self._expected_hostname:
            raise TurnstileValidationError(("hostname-mismatch",))

        challenge_timestamp = payload.get("challenge_ts")
        return TurnstileResult(
            action=action,
            hostname=hostname,
            challenge_timestamp=(
                str(challenge_timestamp) if challenge_timestamp is not None else None
            ),
        )

    async def _siteverify(self, form: dict[str, str]) -> dict[str, Any]:
        try:
            if self._client is not None:
                response = await self._client.post(
                    SITEVERIFY_URL,
                    data=form,
                    timeout=self._timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        SITEVERIFY_URL,
                        data=form,
                        timeout=self._timeout_seconds,
                    )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            raise TurnstileProviderError("Turnstile provider unavailable") from None
        if not isinstance(payload, dict):
            raise TurnstileProviderError("Turnstile provider returned an invalid response")
        return payload

    @staticmethod
    def _error_codes(payload: dict[str, Any]) -> tuple[str, ...]:
        raw_codes = payload.get("error-codes")
        if not isinstance(raw_codes, list):
            return ()
        return tuple(str(code) for code in raw_codes if isinstance(code, str))
