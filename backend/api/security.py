"""
backend/api/security.py
=======================
Bearer/JWT tabanlı kimlik doğrulama ve rol/policy denetimi.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import jwt
from jwt import PyJWKClient
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    subject: str
    roles: set[str]
    token_type: str


POLICY_ROLES: dict[str, set[str]] = {
    "start_job": {"admin", "producer", "operator"},
    "upload": {"admin", "uploader", "producer"},
    "process_manual": {"admin", "editor", "producer"},
    "process_batch": {"admin", "editor", "producer"},
    "reburn": {"admin", "editor"},
    "manual_cut_upload": {"admin", "editor", "producer"},
    "cancel_job": {"admin", "operator"},
}


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _parse_static_tokens(raw: str) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for chunk in raw.split(";"):
        piece = chunk.strip()
        if not piece:
            continue
        token, sep, role_part = piece.partition(":")
        token = token.strip()
        if not token:
            continue
        if not sep:
            mapping[token] = {"admin"}
            continue
        roles = {r.strip().lower() for r in role_part.split(",") if r.strip()}
        mapping[token] = roles or {"admin"}
    return mapping


def _get_static_token_mapping() -> dict[str, set[str]]:
    raw = os.getenv("API_BEARER_TOKENS", "").strip()
    if raw:
        return _parse_static_tokens(raw)

    single = os.getenv("API_BEARER_TOKEN", "").strip()
    if single:
        return {single: {"admin"}}
    return {}


def _extract_roles(payload: dict[str, Any]) -> set[str]:
    raw_roles = payload.get("roles", payload.get("role", []))
    if isinstance(raw_roles, str):
        return {raw_roles.lower()}
    if isinstance(raw_roles, list):
        return {str(role).lower() for role in raw_roles if str(role).strip()}
    return set()


def _decode_jwt(token: str, issuer: str) -> AuthContext:
    # Clerk uses RS256, we need to fetch their public key (JWKS)
    jwks_client = PyJWKClient(f"{issuer}/.well-known/jwks.json")
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False}
        )
    except Exception as e:
        raise ValueError(f"JWT Verification failed: {str(e)}")

    subject = str(payload.get("sub") or "jwt-user")
    
    # Eger jwt icinde ozellestirilmis `roles` varsa al, yoksa clerk'ten gelen tum kullanicilara varsayilan olarak "admin" ver (esneklik icin).
    roles = _extract_roles(payload) or {"admin"}
    
    return AuthContext(subject=subject, roles=roles, token_type="jwt")


def _security_log(request: Request, event: str, reason: str, subject: str = "anonymous", roles: set[str] | None = None) -> None:
    logger.warning(
        "🔐 Security event={} reason='{}' method={} path={} subject={} roles={}",
        event,
        reason,
        request.method,
        request.url.path,
        subject,
        sorted(roles or []),
    )


def _auth_exception(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


def authenticate_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        _security_log(request, event="auth_failed", reason="Bearer token eksik veya şema hatalı")
        raise _auth_exception(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Bearer token gerekli")

    token = credentials.credentials.strip()
    static_tokens = _get_static_token_mapping()

    if token in static_tokens:
        roles = static_tokens[token]
        return AuthContext(subject="static-token", roles=roles, token_type="bearer")

    clerk_issuer = os.getenv("CLERK_ISSUER_URL", "").strip()
    if clerk_issuer:
        try:
            return _decode_jwt(token, clerk_issuer)
        except ValueError as exc:
            _security_log(request, event="auth_failed", reason=str(exc))
            raise _auth_exception(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Geçersiz kimlik doğrulama bilgisi") from exc

    _security_log(request, event="auth_failed", reason="Token doğrulama yapılandırması (CLERK_ISSUER_URL veya static tokens) bulunamadı")
    raise _auth_exception(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Sunucu kimlik doğrulama yapılandırması eksik")


def require_policy(policy_name: str) -> Callable[[Request, AuthContext], AuthContext]:
    required_roles = POLICY_ROLES.get(policy_name, {"admin"})

    def _dependency(request: Request, auth: AuthContext = Depends(authenticate_request)) -> AuthContext:
        if auth.roles.isdisjoint(required_roles):
            _security_log(
                request,
                event="authorization_failed",
                reason=f"policy={policy_name} için role yetersiz",
                subject=auth.subject,
                roles=auth.roles,
            )
            raise _auth_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Bu işlem için yetkiniz yok")
        return auth

    return _dependency
