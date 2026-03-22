"""Tests for social credential encryption hardening."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app
from backend.services.social.crypto import (
    SocialCrypto,
    get_social_encryption_secret,
    get_social_connection_mode,
    is_env_postiz_api_key_fallback_enabled,
    sanitize_managed_postiz_env_fallback,
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


def test_validate_social_security_configuration_rejects_env_postiz_fallback_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.delenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="ALLOW_ENV_POSTIZ_API_KEY_FALLBACK"):
        validate_social_security_configuration()


def test_validate_social_security_configuration_guides_managed_mode_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "managed")
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.delenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_social_security_configuration()

    message = str(exc_info.value)
    assert "SOCIAL_CONNECTION_MODE=managed" in message
    assert "unset POSTIZ_API_KEY" in message


def test_env_postiz_fallback_can_be_enabled_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_ENCRYPTION_SECRET", "test-social-encryption-secret")
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.setenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", "1")

    validate_social_security_configuration()
    assert is_env_postiz_api_key_fallback_enabled() is True


def test_get_social_connection_mode_defaults_to_managed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOCIAL_CONNECTION_MODE", raising=False)

    assert get_social_connection_mode() == "managed"


def test_sanitize_managed_postiz_env_fallback_removes_shell_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "managed")
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.delenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", raising=False)

    changed = sanitize_managed_postiz_env_fallback(messages.append)

    assert changed is True
    assert os.getenv("POSTIZ_API_KEY") is None
    assert messages and "POSTIZ_API_KEY" in messages[0]


def test_sanitize_managed_postiz_env_fallback_keeps_manual_mode_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_CONNECTION_MODE", "manual_api_key")
    monkeypatch.setenv("POSTIZ_API_KEY", "postiz_env_key_123")
    monkeypatch.delenv("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK", raising=False)

    changed = sanitize_managed_postiz_env_fallback()

    assert changed is False
    assert os.getenv("POSTIZ_API_KEY") == "postiz_env_key_123"


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
