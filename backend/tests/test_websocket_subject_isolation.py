from __future__ import annotations

import asyncio

from backend.api.websocket import ConnectionManager


class DummyWebSocket:
    def __init__(self) -> None:
        self.accepted: list[str | None] = []
        self.sent: list[dict] = []

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted.append(subprotocol)

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def test_broadcast_progress_reaches_only_matching_subject() -> None:
    manager = ConnectionManager()
    ws_a = DummyWebSocket()
    ws_b = DummyWebSocket()

    asyncio.run(manager.connect(ws_a, subject="subject-a"))
    asyncio.run(manager.connect(ws_b, subject="subject-b"))

    manager.jobs["job-a"] = {
        "status": "queued",
        "progress": 0,
        "last_message": "",
        "subject": "subject-a",
    }

    asyncio.run(manager.broadcast_progress("started", 25, "job-a"))

    assert len(ws_a.sent) == 1
    assert ws_a.sent[0]["job_id"] == "job-a"
    assert ws_b.sent == []


def test_global_broadcast_reaches_all_connected_subjects() -> None:
    manager = ConnectionManager()
    ws_a = DummyWebSocket()
    ws_b = DummyWebSocket()

    asyncio.run(manager.connect(ws_a, subject="subject-a"))
    asyncio.run(manager.connect(ws_b, subject="subject-b"))

    asyncio.run(manager.broadcast_progress("hello", 10))

    assert ws_a.sent == [{"message": "hello", "progress": 10}]
    assert ws_b.sent == [{"message": "hello", "progress": 10}]
