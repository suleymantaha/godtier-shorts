import asyncio
import json
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket

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


def _run_ws_exchange(app: FastAPI, url: str, *, subprotocols: list[str] | None = None) -> list[dict]:
    async def _exercise() -> list[dict]:
        parsed = urlsplit(url)
        path = parsed.path or "/"
        messages: list[dict] = []
        inbox: asyncio.Queue[dict] = asyncio.Queue()
        await inbox.put({"type": "websocket.connect"})
        headers = [(b"host", b"testserver")]
        if subprotocols:
            headers.append((b"sec-websocket-protocol", ", ".join(subprotocols).encode("ascii")))
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": parsed.query.encode("ascii"),
            "headers": headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "subprotocols": subprotocols or [],
            "root_path": "",
            "state": {},
            "extensions": {"websocket.http.response": {}},
        }

        async def receive() -> dict:
            return await inbox.get()

        async def send(message: dict) -> None:
            messages.append(message)

        await app(scope, receive, send)
        return messages

    return asyncio.run(_exercise())


def test_websocket_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")

    messages = _run_ws_exchange(_build_ws_app(), "/ws/progress")
    close_message = next(message for message in messages if message["type"] == "websocket.close")
    assert close_message["code"] == 1008


def test_websocket_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")

    messages = _run_ws_exchange(_build_ws_app(), "/ws/progress?token=token123")
    payload_message = next(message for message in messages if message["type"] == "websocket.send")
    assert json.loads(payload_message["text"]) == {"ok": True}


def test_websocket_accepts_bearer_subprotocol_token(monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")

    messages = _run_ws_exchange(_build_ws_app(), "/ws/progress", subprotocols=["bearer", "token123"])
    accept_message = next(message for message in messages if message["type"] == "websocket.accept")
    payload_message = next(message for message in messages if message["type"] == "websocket.send")
    assert accept_message["subprotocol"] == "bearer"
    assert json.loads(payload_message["text"]) == {"ok": True}
