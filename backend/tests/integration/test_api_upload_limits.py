from __future__ import annotations

import pytest

import backend.api.server as server_module
from backend.api.server import create_app
from backend.tests.compat_testclient import CompatTestClient


@pytest.mark.parametrize("path", ["/api/upload", "/api/manual-cut-upload"])
def test_guarded_upload_routes_reject_oversized_content_length_early(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:editor")
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setattr(server_module, "REQUEST_BODY_HARD_LIMIT_BYTES", 8)

    client = CompatTestClient(create_app())
    response = client.post(
        path,
        headers={
            "authorization": "Bearer token123",
            "content-length": "9",
        },
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["code"] == "REQUEST_TOO_LARGE"
    assert payload["details"]["limit_bytes"] == 8
    assert "trace_id" in payload
