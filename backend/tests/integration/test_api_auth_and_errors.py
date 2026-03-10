import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.security import require_policy


def build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get('/api/protected', dependencies=[Depends(require_policy("start_job"))])
    def protected():
        return {'ok': True}

    @app.get('/api/boom')
    def boom():
        raise HTTPException(status_code=400, detail='bad request')

    return app


def test_auth_required_returns_standard_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("API_BEARER_TOKENS", raising=False)
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("API_JWT_SECRET", raising=False)

    client = TestClient(build_app())
    res = client.get('/api/protected')
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "unauthorized"


def test_standard_error_response_schema():
    client = TestClient(build_app())
    res = client.get('/api/boom')
    assert res.status_code == 400
    data = res.json()
    assert set(data) >= {'code', 'message'}
