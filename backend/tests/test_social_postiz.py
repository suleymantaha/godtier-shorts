import httpx

from backend.services.social.postiz import PostizClient, exchange_postiz_oauth_code
from backend.services.social.service import _build_post_settings


class _FakeResponse:
    def __init__(self, status_code: int, text: str, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):
        import json

        return json.loads(self.text)


def test_postiz_client_falls_back_to_api_public_v1(monkeypatch):
    calls: list[str] = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        if url == "http://localhost:4007/public/v1/integrations":
            return _FakeResponse(307, "/auth", {"location": "/auth"})
        if url == "http://localhost:4007/api/public/v1/integrations":
            return _FakeResponse(200, "[]")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setenv("POSTIZ_API_BASE_URL", "http://localhost:4007/public/v1")
    monkeypatch.setattr(httpx, "request", fake_request)

    client = PostizClient(api_key="postiz_test_key")
    integrations = client.list_integrations()

    assert integrations == []
    assert calls == [
        "http://localhost:4007/public/v1/integrations",
        "http://localhost:4007/api/public/v1/integrations",
    ]
    assert client.base_url == "http://localhost:4007/api/public/v1"


def test_postiz_create_post_normalizes_tags(monkeypatch):
    captured: dict[str, object] = {}

    def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["json_body"] = kwargs.get("json")
        return _FakeResponse(200, "{\"id\":\"post_1\"}")

    monkeypatch.setenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1")
    monkeypatch.setattr(httpx, "request", fake_request)

    client = PostizClient(api_key="postiz_test_key")
    settings_type, settings = _build_post_settings(
        platform="youtube_shorts",
        provider="youtube",
        title="Test Title",
        hashtags=["shorts", "viral"],
    )

    result = client.create_post(
        integration_id="acc_1",
        settings_type=settings_type,
        content_text="Body",
        media={"id": "media_1", "path": "/uploads/test.mp4"},
        settings=settings,
        mode="now",
        scheduled_at=None,
        hashtags=["shorts", "viral"],
    )

    assert result == {"id": "post_1"}
    payload = captured["json_body"]
    assert isinstance(payload, dict)
    assert payload["tags"] == []
    settings_payload = payload["posts"][0]["settings"]
    assert settings_payload["tags"] == [
        {"label": "shorts", "value": "shorts"},
        {"label": "viral", "value": "viral"},
    ]


def test_exchange_postiz_oauth_code_falls_back_from_redirect_to_api_token(monkeypatch):
    calls: list[str] = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url == "http://localhost:4007/oauth/token":
            return _FakeResponse(307, "/auth", {"location": "/auth"})
        if url == "http://localhost:4007/api/oauth/token":
            return _FakeResponse(200, "{\"access_token\":\"tok_123\",\"token_type\":\"bearer\"}")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1")
    monkeypatch.setattr(httpx, "post", fake_post)

    payload = exchange_postiz_oauth_code(
        client_id="client_123",
        client_secret="secret_123",
        code="code_123",
        redirect_uri="http://localhost:8000/api/social/oauth/callback",
    )

    assert payload["access_token"] == "tok_123"
    assert calls == [
        "http://localhost:4007/oauth/token",
        "http://localhost:4007/api/oauth/token",
    ]
