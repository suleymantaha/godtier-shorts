import asyncio
import threading
from asyncio.threads import to_thread as real_to_thread
from types import SimpleNamespace

import pytest

from backend.core import workflow_common


def test_cancelled_blocking_call_waits_for_worker_thread_before_releasing_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate production mode without altering pytest's own environment.
    monkeypatch.setattr(workflow_common, "os", SimpleNamespace(getenv=lambda *_: None))
    monkeypatch.setattr(asyncio, "to_thread", real_to_thread)
    started = threading.Event()
    release = threading.Event()
    main_thread = threading.get_ident()
    worker_threads: list[int] = []

    def blocking() -> None:
        worker_threads.append(threading.get_ident())
        started.set()
        release.wait(timeout=2)

    async def scenario() -> None:
        task = asyncio.create_task(workflow_common.run_blocking(blocking))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()
            assert worker_threads[0] != main_thread
            task.cancel()
            await asyncio.sleep(0.03)
            assert not task.done(), "GPU stage must remain owned until worker stops"
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
