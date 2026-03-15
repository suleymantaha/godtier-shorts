"""Auth ve policy helper testleri."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api.security import (
    ClerkProviderUnavailableError,
    ClerkTokenExpiredError,
    authenticate_request,
    authenticate_websocket_token,
    require_policy,
    validate_auth_configuration,
)


def test_authenticate_with_static_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:producer,editor")

    app = FastAPI()

    @app.get("/protected")
    def protected(auth=Depends(authenticate_request)):
        return {"subject": auth.subject, "roles": sorted(auth.roles)}

    client = TestClient(app)
    response = client.get("/protected", headers={"Authorization": "Bearer token123"})
    assert response.status_code == 200
    assert response.json()["roles"] == ["editor", "producer"]


def test_policy_rejects_insufficient_role(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")

    app = FastAPI()

    @app.get("/start")
    def start(_: object = Depends(require_policy("start_job"))):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/start", headers={"Authorization": "Bearer token123"})
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"]["code"] == "forbidden"


def test_missing_bearer_returns_401_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)

    app = FastAPI()

    @app.get("/start")
    def start(_: object = Depends(require_policy("start_job"))):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/start")
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"]["code"] == "unauthorized"


def test_read_policy_requires_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")

    app = FastAPI()

    @app.get("/projects")
    def projects(_: object = Depends(require_policy("view_projects"))):
        return {"ok": True}

    client = TestClient(app)
    unauthorized = client.get("/projects")
    assert unauthorized.status_code == 401

    authorized = client.get("/projects", headers={"Authorization": "Bearer token123"})
    assert authorized.status_code == 200
    assert authorized.json() == {"ok": True}


def test_validate_auth_configuration_requires_audience(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://example.clerk.accounts.dev")
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)

    with pytest.raises(RuntimeError):
        validate_auth_configuration()


def test_authenticate_websocket_token_with_static_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")
    auth = authenticate_websocket_token("token123")
    assert auth.subject.startswith("static-token:")
    assert "viewer" in auth.roles


def test_expired_clerk_token_returns_specific_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_AUDIENCE", "godtier-shorts-api")

    def _raise_expired(*_args, **_kwargs):
        raise ClerkTokenExpiredError("expired")

    monkeypatch.setattr("backend.api.security._decode_jwt", _raise_expired)

    app = FastAPI()

    @app.get("/projects")
    def projects(_: object = Depends(require_policy("view_projects"))):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/projects", headers={"Authorization": "Bearer jwt-token"})

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "token_expired"


def test_unreachable_clerk_provider_returns_503(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_AUDIENCE", "godtier-shorts-api")

    def _raise_provider_error(*_args, **_kwargs):
        raise ClerkProviderUnavailableError("down")

    monkeypatch.setattr("backend.api.security._decode_jwt", _raise_provider_error)

    app = FastAPI()

    @app.get("/projects")
    def projects(_: object = Depends(require_policy("view_projects"))):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/projects", headers={"Authorization": "Bearer jwt-token"})

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "auth_provider_unavailable"
