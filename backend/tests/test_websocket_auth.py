from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from backend.api.security import authenticate_websocket_token


def _build_ws_app() -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws/progress")
    async def ws_progress(websocket: WebSocket) -> None:
        token = None
        selected_subprotocol = None
        protocol_header = websocket.headers.get("sec-websocket-protocol", "")
        if protocol_header:
            parts = [part.strip() for part in protocol_header.split(",") if part.strip()]
            if len(parts) >= 2 and parts[0].lower() == "bearer":
                token = parts[1]
                selected_subprotocol = "bearer"
        if token is None:
            token = websocket.query_params.get("token")
        try:
            authenticate_websocket_token(token)
        except Exception:
            await websocket.close(code=1008)
            return

        await websocket.accept(subprotocol=selected_subprotocol)
        await websocket.send_json({"ok": True})
        await websocket.close()

    return app


def test_websocket_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")
    client = TestClient(_build_ws_app())

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/progress"):
            pass
    assert exc.value.code == 1008


def test_websocket_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")
    client = TestClient(_build_ws_app())

    with client.websocket_connect("/ws/progress?token=token123") as ws:
        payload = ws.receive_json()
        assert payload == {"ok": True}


def test_websocket_accepts_bearer_subprotocol_token(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")
    client = TestClient(_build_ws_app())

    with client.websocket_connect("/ws/progress", subprotocols=["bearer", "token123"]) as ws:
        payload = ws.receive_json()
        assert payload == {"ok": True}
