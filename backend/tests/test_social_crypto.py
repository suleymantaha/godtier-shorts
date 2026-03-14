"""Tests for social credential encryption hardening."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app
from backend.services.social.crypto import (
    SocialCrypto,
    get_social_encryption_secret,
    validate_social_security_configuration,
)


def test_social_crypto_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOCIAL_ENCRYPTION_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="SOCIAL_ENCRYPTION_SECRET"):
        SocialCrypto()


def test_social_crypto_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")

    crypto = SocialCrypto()
    encrypted = crypto.encrypt("postiz_test_key")

    assert encrypted != "postiz_test_key"
    assert crypto.decrypt(encrypted) == "postiz_test_key"


def test_validate_social_security_configuration_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOCIAL_ENCRYPTION_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="SOCIAL_ENCRYPTION_SECRET"):
        validate_social_security_configuration()


def test_get_social_encryption_secret_prefers_explicit_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOCIAL_ENCRYPTION_SECRET", raising=False)

    assert get_social_encryption_secret("explicit-secret") == "explicit-secret"


def test_create_app_startup_requires_social_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:admin")
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.delenv("SOCIAL_ENCRYPTION_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="SOCIAL_ENCRYPTION_SECRET"):
        with TestClient(create_app()):
            pass
