"""Simple encryption wrapper for user-level social credentials."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def get_social_encryption_secret(secret: str | None = None) -> str:
    value = (secret or os.getenv("SOCIAL_ENCRYPTION_SECRET") or "").strip()
    if not value:
        raise RuntimeError("SOCIAL_ENCRYPTION_SECRET tanımlı olmalıdır")
    return value


def validate_social_security_configuration() -> None:
    get_social_encryption_secret()


class SocialCrypto:
    def __init__(self, secret: str | None = None):
        secret_value = get_social_encryption_secret(secret).encode("utf-8")
        digest = hashlib.sha256(secret_value).digest()
        key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Encrypted credential could not be decrypted") from exc
