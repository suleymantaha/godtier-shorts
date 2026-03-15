"""
backend/api/security.py
=======================
Bearer/JWT tabanlı kimlik doğrulama ve rol/policy denetimi.
"""
from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from backend.core.log_sanitizer import sanitize_subject
from backend.services.ownership import resolve_project_access

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
    "view_projects": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "view_project_media": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "view_clips": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "delete_clip": {"admin", "producer", "editor"},
    "view_clip_transcript": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "recover_clip_transcript": {"admin", "producer", "editor"},
    "recover_project_transcript": {"admin", "producer", "editor"},
    "view_transcript": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "view_jobs": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "view_styles": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "save_transcript": {"admin", "producer", "editor"},
    "websocket_progress": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "social_connect": {"admin", "producer", "editor"},
    "social_publish": {"admin", "producer", "editor"},
    "social_approve": {"admin", "producer"},
    "social_view_jobs": {"admin", "producer", "editor", "viewer"},
    "manage_support_grants": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
    "delete_account_data": {"admin", "producer", "editor", "operator", "uploader", "viewer"},
}

WEAK_STATIC_TOKENS = {"test-token", "changeme", "change-me", "default-token", "example-token"}


class ClerkTokenExpiredError(ValueError):
    pass


class ClerkProviderUnavailableError(ValueError):
    pass


def _security_log_ws(event: str, reason: str, subject: str = "anonymous", roles: set[str] | None = None) -> None:
    logger.warning(
        "🔐 Security event={} reason='{}' method=WS path=/ws/progress subject={} roles={}",
        event,
        reason,
        sanitize_subject(subject),
        sorted(roles or []),
    )


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
        if " " in token or token.lower() in WEAK_STATIC_TOKENS:
            raise ValueError("Zayıf veya geçersiz static token değeri tespit edildi")
        if not sep:
            mapping[token] = {"admin"}
            continue
        roles = {r.strip().lower() for r in role_part.split(",") if r.strip()}
        if not roles:
            raise ValueError("Static token için en az bir rol belirtilmelidir")
        mapping[token] = roles
    return mapping


def _get_static_token_mapping() -> dict[str, set[str]]:
    raw = os.getenv("API_BEARER_TOKENS", "").strip()
    if raw:
        return _parse_static_tokens(raw)

    single = os.getenv("API_BEARER_TOKEN", "").strip()
    if single:
        if " " in single or single.lower() in WEAK_STATIC_TOKENS:
            raise ValueError("Zayıf veya geçersiz static token değeri tespit edildi")
        return {single: {"admin"}}
    return {}


def _extract_roles(payload: dict[str, Any]) -> set[str]:
    raw_roles = payload.get("roles", payload.get("role", []))
    if isinstance(raw_roles, str):
        return {raw_roles.lower()}
    if isinstance(raw_roles, list):
        return {str(role).lower() for role in raw_roles if str(role).strip()}
    return set()


def _read_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} sayisal bir deger olmali") from exc

    if value <= 0:
        raise RuntimeError(f"{name} sifirdan buyuk olmali")

    return value


@lru_cache(maxsize=8)
def _get_jwks_client(issuer: str, cache_ttl_seconds: int, timeout_seconds: int) -> PyJWKClient:
    return PyJWKClient(
        f"{issuer}/.well-known/jwks.json",
        cache_jwk_set=True,
        cache_keys=True,
        lifespan=cache_ttl_seconds,
        timeout=timeout_seconds,
    )


def _decode_jwt(token: str, issuer: str, audience: str) -> AuthContext:
    cache_ttl_seconds = _read_positive_int_env("CLERK_JWKS_CACHE_TTL_SECONDS", 3600)
    timeout_seconds = _read_positive_int_env("CLERK_JWKS_TIMEOUT_SECONDS", 5)
    jwks_client = _get_jwks_client(issuer, cache_ttl_seconds, timeout_seconds)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"verify_aud": True},
        )
    except ExpiredSignatureError as exc:
        raise ClerkTokenExpiredError("JWT token expired") from exc
    except PyJWKClientConnectionError as exc:
        raise ClerkProviderUnavailableError("Clerk JWKS endpoint ulasilamiyor") from exc
    except (PyJWKClientError, InvalidTokenError) as exc:
        raise ValueError(f"JWT verification failed: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"JWT verification failed: {exc}") from exc

    subject = str(payload.get("sub") or "jwt-user")
    roles = _extract_roles(payload)
    if not roles:
        raise ValueError("JWT roles claim eksik veya boş")
    return AuthContext(subject=subject, roles=roles, token_type="jwt")


def _authenticate_token(token: str) -> AuthContext:
    token = token.strip()
    if not token:
        raise _auth_exception(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Bearer token gerekli")

    try:
        static_tokens = _get_static_token_mapping()
    except ValueError as exc:
        raise _auth_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "auth_config_invalid",
            str(exc),
        ) from exc
    if token in static_tokens:
        roles = static_tokens[token]
        fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
        return AuthContext(subject=f"static-token:{fingerprint}", roles=roles, token_type="bearer")

    clerk_issuer = os.getenv("CLERK_ISSUER_URL", "").strip()
    clerk_audience = os.getenv("CLERK_AUDIENCE", "").strip()
    if clerk_issuer:
        if not clerk_audience:
            raise _auth_exception(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "auth_config_invalid",
                "CLERK_AUDIENCE tanımlı olmalıdır",
            )
        try:
            return _decode_jwt(token, clerk_issuer, clerk_audience)
        except ClerkTokenExpiredError as exc:
            raise _auth_exception(
                status.HTTP_401_UNAUTHORIZED,
                "token_expired",
                "Oturum suresi doldu. Lutfen yeniden giris yapin.",
            ) from exc
        except ClerkProviderUnavailableError as exc:
            raise _auth_exception(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "auth_provider_unavailable",
                "Kimlik dogrulama servisine su anda ulasilamiyor",
            ) from exc
        except ValueError as exc:
            raise _auth_exception(status.HTTP_401_UNAUTHORIZED, "unauthorized", "Geçersiz kimlik doğrulama bilgisi") from exc

    raise _auth_exception(
        status.HTTP_401_UNAUTHORIZED,
        "unauthorized",
        "Sunucu kimlik doğrulama yapılandırması eksik",
    )


def _security_log(request: Request, event: str, reason: str, subject: str = "anonymous", roles: set[str] | None = None) -> None:
    logger.warning(
        "🔐 Security event={} reason='{}' method={} path={} subject={} roles={}",
        event,
        reason,
        request.method,
        request.url.path,
        sanitize_subject(subject),
        sorted(roles or []),
    )


def _security_log_ownership_denied(
    request: Request,
    auth: AuthContext,
    *,
    project_id: str,
    clip_name: str | None = None,
    job_id: str | None = None,
    reason: str,
) -> None:
    logger.warning(
        "🔐 Security event=ownership_denied reason='{}' method={} path={} subject={} roles={} project_id={} clip_name={} job_id={}",
        reason,
        request.method,
        request.url.path,
        sanitize_subject(auth.subject),
        sorted(auth.roles),
        project_id,
        clip_name or "-",
        job_id or "-",
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

    try:
        return _authenticate_token(credentials.credentials)
    except HTTPException as exc:
        _security_log(request, event="auth_failed", reason=str(exc.detail))
        raise


def authenticate_websocket_token(token: str | None) -> AuthContext:
    if token is None:
        _security_log_ws(event="auth_failed", reason="WebSocket token eksik")
        raise _auth_exception(status.HTTP_401_UNAUTHORIZED, "unauthorized", "WebSocket token gerekli")
    try:
        return _authenticate_token(token)
    except HTTPException as exc:
        _security_log_ws(event="auth_failed", reason=str(exc.detail))
        raise


def validate_auth_configuration() -> None:
    issuer = os.getenv("CLERK_ISSUER_URL", "").strip()
    audience = os.getenv("CLERK_AUDIENCE", "").strip()
    has_static = bool(os.getenv("API_BEARER_TOKENS", "").strip() or os.getenv("API_BEARER_TOKEN", "").strip())
    if not issuer and not has_static:
        raise RuntimeError("Auth config eksik: CLERK_ISSUER_URL veya static bearer token tanımlanmalı")
    if issuer and not audience:
        raise RuntimeError("Auth config eksik: CLERK_AUDIENCE zorunlu")
    # Also fail-fast on invalid static tokens.
    _get_static_token_mapping()
    if issuer:
        _read_positive_int_env("CLERK_JWKS_CACHE_TTL_SECONDS", 3600)
        _read_positive_int_env("CLERK_JWKS_TIMEOUT_SECONDS", 5)


def ensure_project_access(
    request: Request,
    auth: AuthContext,
    project_id: str,
    *,
    clip_name: str | None = None,
    job_id: str | None = None,
) -> None:
    allowed, reason, _manifest = resolve_project_access(project_id, auth.subject)
    if allowed:
        if reason == "support_grant":
            logger.info(
                "🔐 Security event=support_grant_used method={} path={} subject={} roles={} project_id={} clip_name={} job_id={}",
                request.method,
                request.url.path,
                sanitize_subject(auth.subject),
                sorted(auth.roles),
                project_id,
                clip_name or "-",
                job_id or "-",
            )
        return
    _security_log_ownership_denied(
        request,
        auth,
        project_id=project_id,
        clip_name=clip_name,
        job_id=job_id,
        reason=reason,
    )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kaynak bulunamadı")


def ensure_project_owner(
    request: Request,
    auth: AuthContext,
    project_id: str,
) -> None:
    allowed, reason, _manifest = resolve_project_access(project_id, auth.subject)
    if allowed and reason == "owner_match":
        return
    _security_log_ownership_denied(
        request,
        auth,
        project_id=project_id,
        reason=reason,
    )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kaynak bulunamadı")


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
