"""Simple encryption wrapper for user-level social credentials."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Callable, Literal

from cryptography.fernet import Fernet, InvalidToken


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_social_encryption_secret(secret: str | None = None) -> str:
    value = (secret or os.getenv("SOCIAL_ENCRYPTION_SECRET") or "").strip()
    if not value:
        raise RuntimeError("SOCIAL_ENCRYPTION_SECRET tanımlı olmalıdır")
    return value


def is_env_postiz_api_key_fallback_enabled() -> bool:
    return _is_truthy_env("ALLOW_ENV_POSTIZ_API_KEY_FALLBACK")


def get_social_connection_mode() -> Literal["managed", "manual_api_key"]:
    raw = os.getenv("SOCIAL_CONNECTION_MODE", "").strip().lower()
    if raw == "manual_api_key":
        return "manual_api_key"
    return "managed"


def _build_env_postiz_fallback_disabled_message() -> str:
    mode = get_social_connection_mode()
    if mode == "managed":
        return (
            "POSTIZ_API_KEY env fallback'i varsayilan olarak kapali. "
            "SOCIAL_CONNECTION_MODE=managed iken POSTIZ_API_KEY tanimli olmamalidir. "
            "Degeri shell ortamindan kaldirin (ornegin `unset POSTIZ_API_KEY`) veya .env/.profile benzeri dosyalardan silin. "
            "Yalniz tek kullanicili lokal dev fallback icin SOCIAL_CONNECTION_MODE=manual_api_key ve "
            "ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1 kullanin."
        )

    return (
        "POSTIZ_API_KEY env fallback'i varsayilan olarak kapali. "
        "Tek kullanicili lokal dev fallback kullanacaksaniz ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1 ayarlayin. "
        "Paylasimli veya managed kullanimda ise POSTIZ_API_KEY degerini kaldirin."
    )


def sanitize_managed_postiz_env_fallback(
    notify: Callable[[str], None] | None = None,
) -> bool:
    if get_social_connection_mode() != "managed":
        return False
    if is_env_postiz_api_key_fallback_enabled():
        return False
    if not os.getenv("POSTIZ_API_KEY", "").strip():
        return False

    os.environ.pop("POSTIZ_API_KEY", None)
    if notify is not None:
        notify(
            "Managed modda shell ortamindan gelen POSTIZ_API_KEY yok sayildi. "
            "Uygulama subject-bazli credential/OAuth akisi ile devam edecek."
        )
    return True


def validate_social_security_configuration() -> None:
    get_social_encryption_secret()
    if os.getenv("POSTIZ_API_KEY", "").strip() and not is_env_postiz_api_key_fallback_enabled():
        raise RuntimeError(_build_env_postiz_fallback_disabled_message())


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
