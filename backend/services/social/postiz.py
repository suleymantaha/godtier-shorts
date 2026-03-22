"""Postiz Public API client helpers."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


class PostizApiError(RuntimeError):
    pass


def _build_postiz_root_candidates() -> list[str]:
    configured_base_url = os.getenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1").rstrip("/")
    candidates: list[str] = []

    def add(url: str) -> None:
        normalized = url.rstrip("/")
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    if configured_base_url.endswith("/api/public/v1"):
        root = configured_base_url[: -len("/api/public/v1")]
        add(root)
        add(f"{root}/api")
        return candidates

    if configured_base_url.endswith("/public/v1"):
        root = configured_base_url[: -len("/public/v1")]
        add(root)
        add(f"{root}/api")
        return candidates

    if configured_base_url.endswith("/api"):
        root = configured_base_url[: -len("/api")]
        add(root)
        add(configured_base_url)
        return candidates

    add(configured_base_url)
    add(f"{configured_base_url}/api")
    return candidates


def build_postiz_oauth_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    integration: str,
    state: str,
) -> str:
    if not client_id.strip():
        raise PostizApiError("POSTIZ_OAUTH_CLIENT_ID tanımlı olmalı")
    if not redirect_uri.strip():
        raise PostizApiError("SOCIAL_OAUTH_CALLBACK_URL tanımlı olmalı")

    roots = _build_postiz_root_candidates()
    if not roots:
        raise PostizApiError("POSTIZ OAuth authorize URL oluşturulamadı")

    query = urlencode(
        {
            "client_id": client_id.strip(),
            "redirect_uri": redirect_uri.strip(),
            "response_type": "code",
            "state": state,
            "integration": integration,
            "provider": integration,
        }
    )
    return f"{roots[0]}/oauth/authorize?{query}"


def exchange_postiz_oauth_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not client_id.strip():
        raise PostizApiError("POSTIZ_OAUTH_CLIENT_ID tanımlı olmalı")
    if not client_secret.strip():
        raise PostizApiError("POSTIZ_OAUTH_CLIENT_SECRET tanımlı olmalı")
    if not code.strip():
        raise PostizApiError("OAuth code boş olamaz")
    if not redirect_uri.strip():
        raise PostizApiError("SOCIAL_OAUTH_CALLBACK_URL tanımlı olmalı")

    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip(),
        "code": code.strip(),
        "redirect_uri": redirect_uri.strip(),
    }
    headers = {"Accept": "application/json"}
    roots = _build_postiz_root_candidates()
    token_urls = [f"{root}/oauth/token" for root in roots]
    last_error: PostizApiError | None = None

    for index, token_url in enumerate(token_urls):
        try:
            response = httpx.post(
                token_url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            last_error = PostizApiError(f"Postiz token exchange failed: {exc}")
            if index < len(token_urls) - 1:
                continue
            raise last_error from exc

        if response.status_code == 404 and index < len(token_urls) - 1:
            last_error = PostizApiError("Postiz oauth token endpoint not found")
            continue

        if response.status_code >= 400:
            raise PostizApiError(f"Postiz OAuth HTTP {response.status_code}: {response.text[:600]}")

        try:
            data = response.json() if response.text else {}
        except ValueError as exc:
            raise PostizApiError("Postiz OAuth token response is not valid JSON") from exc

        if not isinstance(data, dict):
            raise PostizApiError("Postiz OAuth token response must be an object")

        access_token = str(data.get("access_token") or data.get("accessToken") or "").strip()
        if not access_token:
            raise PostizApiError("Postiz OAuth token response missing access_token")

        return {
            "access_token": access_token,
            "refresh_token": data.get("refresh_token") or data.get("refreshToken"),
            "expires_in": data.get("expires_in") or data.get("expiresIn"),
            "token_type": data.get("token_type") or data.get("tokenType"),
            "scope": data.get("scope"),
            "raw": data,
        }

    if last_error is not None:
        raise last_error
    raise PostizApiError("Postiz token exchange failed")


def _serialize_postiz_tags(tags: list[str] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for tag in tags or []:
        value = str(tag).strip().replace("#", "")
        if not value:
            continue
        out.append({"label": value, "value": value})
    return out


class PostizClient:
    def __init__(self, api_key: str, *, timeout: float = 60.0):
        self.api_key = api_key
        configured_base_url = os.getenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1").rstrip("/")
        self._base_url_candidates = self._build_base_url_candidates(configured_base_url)
        self.base_url = self._base_url_candidates[0]
        self.timeout = timeout

    @staticmethod
    def _build_base_url_candidates(base_url: str) -> list[str]:
        raw = (base_url or "").rstrip("/")
        candidates: list[str] = []

        def add(url: str) -> None:
            normalized = url.rstrip("/")
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        if raw.endswith("/api/public/v1"):
            add(raw)
            add(raw.replace("/api/public/v1", "/public/v1"))
            return candidates

        if raw.endswith("/public/v1"):
            add(raw)
            add(raw.replace("/public/v1", "/api/public/v1"))
            return candidates

        if raw.endswith("/api"):
            add(f"{raw}/public/v1")
            add(raw.replace("/api", "/public/v1"))
            return candidates

        add(f"{raw}/api/public/v1")
        add(f"{raw}/public/v1")
        return candidates

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
        }

    @staticmethod
    def _looks_like_auth_redirect(response: httpx.Response) -> bool:
        if response.status_code not in {301, 302, 307, 308}:
            return False
        location = response.headers.get("location", "")
        return location.endswith("/auth") or location == "/auth"

    @staticmethod
    def _looks_like_html_or_auth_body(body: str) -> bool:
        text = (body or "").strip().lower()
        return bool(text) and (
            text == "/auth"
            or text.startswith("<!doctype html")
            or text.startswith("<html")
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        request_timeout = timeout or self.timeout
        last_error: PostizApiError | None = None
        candidate_bases = [self.base_url] + [base for base in self._base_url_candidates if base != self.base_url]

        for index, base_url in enumerate(candidate_bases):
            url = f"{base_url}{path}"
            try:
                response = httpx.request(
                    method,
                    url,
                    headers=self._headers,
                    json=json_body,
                    params=params,
                    files=files,
                    timeout=request_timeout,
                )
            except httpx.HTTPError as exc:
                last_error = PostizApiError(f"Postiz request failed: {exc}")
                if index < len(candidate_bases) - 1:
                    continue
                raise last_error from exc

            if self._looks_like_auth_redirect(response):
                last_error = PostizApiError("Postiz redirected to /auth")
                if index < len(candidate_bases) - 1:
                    continue
                raise last_error

            if response.status_code == 404 and index < len(candidate_bases) - 1:
                last_error = PostizApiError("Postiz endpoint not found")
                continue

            if response.status_code >= 400:
                raise PostizApiError(f"Postiz HTTP {response.status_code}: {response.text[:600]}")

            if not response.text:
                self.base_url = base_url
                return {}

            try:
                payload = response.json()
            except ValueError as exc:
                if self._looks_like_html_or_auth_body(response.text) and index < len(candidate_bases) - 1:
                    last_error = PostizApiError("Postiz returned auth/html response")
                    continue
                raise PostizApiError("Postiz response is not valid JSON") from exc

            self.base_url = base_url
            return payload

        if last_error is not None:
            raise last_error
        raise PostizApiError("Postiz request failed")

    def list_integrations(self) -> list[dict[str, Any]]:
        raw = self._request("GET", "/integrations")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            entries = raw.get("integrations") or raw.get("data") or raw.get("items")
            if isinstance(entries, list):
                return [item for item in entries if isinstance(item, dict)]
        return []

    def validate_connection(self) -> list[dict[str, Any]]:
        return self.list_integrations()

    def get_connect_channel_url(self, integration: str) -> str:
        integration_name = str(integration or "").strip().lower()
        if not integration_name:
            raise PostizApiError("Postiz connect integration adı boş olamaz")

        raw = self._request("GET", f"/social/{integration_name}", timeout=60)
        if isinstance(raw, dict):
            for key in ("url", "redirectUrl", "redirect_url", "authUrl", "auth_url"):
                value = str(raw.get(key) or "").strip()
                if value:
                    return value
        if isinstance(raw, str) and raw.strip().startswith("http"):
            return raw.strip()
        raise PostizApiError("Postiz connect channel URL bulunamadı")

    def upload_media_direct(self, clip_path: Path) -> dict[str, Any]:
        with open(clip_path, "rb") as f:
            raw = self._request(
                "POST",
                "/upload",
                files={"file": (clip_path.name, f, "video/mp4")},
                timeout=300,
            )
        if not isinstance(raw, dict):
            raise PostizApiError("Postiz upload response must be an object")
        if not raw.get("id"):
            raise PostizApiError("Postiz upload response missing media id")
        return raw

    def upload_media_from_url(self, url: str) -> dict[str, Any]:
        raw = self._request(
            "POST",
            "/upload-from-url",
            json_body={"url": url},
            timeout=120,
        )
        if not isinstance(raw, dict):
            raise PostizApiError("Postiz upload-from-url response must be an object")
        if not raw.get("id"):
            raise PostizApiError("Postiz upload-from-url response missing media id")
        return raw

    def create_post(
        self,
        *,
        integration_id: str,
        settings_type: str,
        content_text: str,
        media: dict[str, Any],
        settings: dict[str, Any],
        mode: str,
        scheduled_at: str | None,
        hashtags: list[str] | None = None,
    ) -> Any:
        post_type = "schedule" if mode == "scheduled" else "now"
        date_value = (
            scheduled_at
            if mode == "scheduled" and scheduled_at
            else datetime.now(timezone.utc).isoformat()
        )
        normalized_settings = dict(settings)
        if "tags" in normalized_settings:
            normalized_settings["tags"] = _serialize_postiz_tags(normalized_settings.get("tags"))

        payload: dict[str, Any] = {
            "type": post_type,
            "date": date_value,
            "shortLink": False,
            "tags": [],
            "posts": [
                {
                    "integration": {"id": integration_id},
                    "value": [
                        {
                            "content": content_text,
                            "image": [
                                {
                                    "id": str(media.get("id") or ""),
                                    "path": str(media.get("path") or ""),
                                }
                            ],
                        }
                    ],
                    "group": "",
                    "settings": {
                        "__type": settings_type,
                        **normalized_settings,
                    },
                }
            ],
        }

        return self._request("POST", "/posts", json_body=payload, timeout=120)

    def delete_post(self, post_id: str) -> Any:
        post_id_value = str(post_id).strip()
        if not post_id_value:
            raise PostizApiError("Postiz delete requires post id")
        return self._request("DELETE", f"/posts/{post_id_value}", timeout=60)

    def delete_integration(self, integration_id: str) -> Any:
        integration_id_value = str(integration_id).strip()
        if not integration_id_value:
            raise PostizApiError("Postiz delete integration requires integration id")
        return self._request("DELETE", f"/integrations/{integration_id_value}", timeout=60)
