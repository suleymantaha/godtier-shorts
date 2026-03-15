from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx


class CompatTestClient:
    __test__ = False

    def __init__(
        self,
        app: Any,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: str = "asyncio",
        backend_options: dict[str, Any] | None = None,
        cookies: httpx._types.CookieTypes | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
    ) -> None:
        if backend != "asyncio":
            raise LookupError(f"No such backend: {backend}")
        if backend_options:
            raise RuntimeError("CompatTestClient does not support backend options")

        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.cookies = cookies
        self.headers = headers or {}
        self.follow_redirects = follow_redirects
        self.client = client
        self._lifespan_cm: Any | None = None
        self._lifespan_runner: asyncio.Runner | None = None

    async def _request_once(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        merged_headers = dict(self.headers)
        request_headers = kwargs.pop("headers", None) or {}
        merged_headers.update(request_headers)
        params = kwargs.pop("params", None)
        json_body = kwargs.pop("json", None)
        data = kwargs.pop("data", None)
        content = kwargs.pop("content", None)
        if kwargs:
            unsupported = ", ".join(sorted(kwargs))
            raise TypeError(f"Unsupported request kwargs: {unsupported}")

        parsed = urlsplit(url)
        path = parsed.path or "/"
        query_pairs: list[tuple[str, Any]] = []
        if parsed.query:
            from urllib.parse import parse_qsl

            query_pairs.extend(parse_qsl(parsed.query, keep_blank_values=True))
        if params is not None:
            if isinstance(params, dict):
                query_pairs.extend(params.items())
            else:
                query_pairs.extend(params)
        query_string = urlencode(query_pairs, doseq=True).encode("utf-8")

        body = b""
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            merged_headers.setdefault("content-type", "application/json")
        elif data is not None:
            if isinstance(data, bytes):
                body = data
            elif isinstance(data, str):
                body = data.encode("utf-8")
            elif isinstance(data, dict):
                body = urlencode(data, doseq=True).encode("utf-8")
                merged_headers.setdefault("content-type", "application/x-www-form-urlencoded")
            else:
                body = urlencode(list(data), doseq=True).encode("utf-8")
                merged_headers.setdefault("content-type", "application/x-www-form-urlencoded")
        elif content is not None:
            body = content if isinstance(content, bytes) else str(content).encode("utf-8")

        host = urlsplit(self.base_url).hostname or "testserver"
        port = urlsplit(self.base_url).port or 80
        headers = [(b"host", host.encode("ascii"))]
        headers.extend((key.lower().encode("ascii"), value.encode("utf-8")) for key, value in merged_headers.items())

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": urlsplit(self.base_url).scheme or "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query_string,
            "headers": headers,
            "client": self.client,
            "server": (host, port),
            "root_path": self.root_path,
            "state": {},
        }

        request_sent = False
        response_started = False
        response_status = 500
        response_headers: list[tuple[str, str]] = []
        response_body: list[bytes] = []
        async def receive() -> dict[str, Any]:
            nonlocal request_sent
            if request_sent:
                return {"type": "http.disconnect"}
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            nonlocal response_started, response_status, response_headers
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                response_headers = [
                    (key.decode("latin-1"), value.decode("latin-1"))
                    for key, value in message.get("headers", [])
                ]
                return
            if message["type"] == "http.response.body":
                if body_part := message.get("body", b""):
                    response_body.append(body_part)

        try:
            await self.app(scope, receive, send)
        except Exception:
            if self.raise_server_exceptions:
                raise
            response_status = 500
            response_headers = []
            response_body = []

        if not response_started:
            raise AssertionError("CompatTestClient did not receive any response")

        request = httpx.Request(method.upper(), httpx.URL(self.base_url + path, query=query_string))
        return httpx.Response(
            status_code=response_status,
            headers=response_headers,
            content=b"".join(response_body),
            request=request,
        )

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._lifespan_runner is None:
            return asyncio.run(self._request_once(method, url, **kwargs))
        return self._lifespan_runner.run(self._request_once(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def websocket_connect(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("CompatTestClient does not support WebSocket tests")

    def __enter__(self) -> CompatTestClient:
        runner = asyncio.Runner()
        lifespan_cm = self.app.router.lifespan_context(self.app)
        try:
            runner.run(lifespan_cm.__aenter__())
        except Exception:
            runner.close()
            raise
        self._lifespan_runner = runner
        self._lifespan_cm = lifespan_cm
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._lifespan_runner is not None and self._lifespan_cm is not None:
                self._lifespan_runner.run(self._lifespan_cm.__aexit__(exc_type, exc, tb))
        finally:
            if self._lifespan_runner is not None:
                self._lifespan_runner.close()
            self._lifespan_runner = None
            self._lifespan_cm = None

    def close(self) -> None:
        self.__exit__(None, None, None)
