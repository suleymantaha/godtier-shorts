import httpx

from backend.services.social.postiz import PostizClient
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
