from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from backend.api.server import create_app


def _production_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_URL", "https://app.godtier.example")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    return TestClient(create_app())


def test_production_responses_have_security_headers_and_request_id(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    response = client.get("/health/live", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"
    assert response.headers["x-trace-id"] == "request-123"
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_invalid_request_id_is_replaced_and_early_rejections_keep_headers(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    response = client.post(
        "/api/upload",
        headers={"X-Request-ID": "invalid request id", "Content-Length": str(6 * 1024**3)},
    )

    assert response.status_code == 413
    UUID(response.headers["x-request-id"])
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["strict-transport-security"] == "max-age=31536000"


def test_production_cors_allows_only_the_configured_frontend_and_headers_preflight(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    allowed = client.request(
        "OPTIONS",
        "/api/billing/account",
        headers={
            "Origin": "https://app.godtier.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.request(
        "OPTIONS",
        "/api/billing/account",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "https://app.godtier.example"
    assert allowed.headers["x-request-id"]
    assert allowed.headers["strict-transport-security"] == "max-age=31536000"
    assert "access-control-allow-origin" not in denied.headers


def test_production_disables_api_schema_and_development_keeps_docs(monkeypatch) -> None:
    production = _production_client(monkeypatch)
    assert production.get("/docs").status_code == 404
    assert production.get("/openapi.json").status_code == 404

    monkeypatch.setenv("APP_ENV", "development")
    development = TestClient(create_app())
    assert development.get("/docs").status_code == 200
    assert "strict-transport-security" not in development.get("/health/live").headers
