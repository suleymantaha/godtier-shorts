from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import security_gate
from backend.services.abuse.turnstile import TurnstileValidationError


class FakeVerifier:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.calls = []

    async def validate(self, token: str, **kwargs) -> None:
        self.calls.append((token, kwargs))
        if not self.valid:
            raise TurnstileValidationError(("timeout-or-duplicate",))


def build_client(verifier: FakeVerifier) -> TestClient:
    app = FastAPI()
    app.include_router(security_gate.router)
    app.dependency_overrides[security_gate.get_turnstile_verifier] = lambda: verifier
    return TestClient(app)


def test_signup_gate_is_verified_server_side() -> None:
    verifier = FakeVerifier()

    response = build_client(verifier).post(
        "/api/security/turnstile/verify",
        json={"token": "signup-token", "action": "signup"},
    )

    assert response.status_code == 200
    assert response.json() == {"verified": True}
    assert verifier.calls[0][1]["expected_action"] == "signup"


def test_signup_gate_rejects_replayed_token() -> None:
    verifier = FakeVerifier(valid=False)

    response = build_client(verifier).post(
        "/api/security/turnstile/verify",
        json={"token": "replayed-token", "action": "signup"},
    )

    assert response.status_code == 403


def test_public_gate_does_not_accept_arbitrary_actions() -> None:
    response = build_client(FakeVerifier()).post(
        "/api/security/turnstile/verify",
        json={"token": "token", "action": "admin_delete"},
    )

    assert response.status_code == 422
