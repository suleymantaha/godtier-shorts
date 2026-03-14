"""Postiz Public API client helpers."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


class PostizApiError(RuntimeError):
    pass


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
