"""Subprocess execution with cancellation and timeout handling."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class CompletedCommand:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def __init__(self, cancel_event: threading.Event, poll_interval: float = 0.5):
        self._cancel_event = cancel_event
        self._poll_interval = poll_interval

    async def run_async(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _watch_cancel() -> None:
            while proc.returncode is None:
                if self._cancel_event.is_set():
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    raise RuntimeError("Job cancelled by user")
                await asyncio.sleep(self._poll_interval)

        cancel_task = asyncio.create_task(_watch_cancel())

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            cancel_task.cancel()
            return proc.returncode or 0, stdout_bytes.decode(errors="replace"), stderr_bytes.decode(errors="replace")
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            cancel_task.cancel()
            raise RuntimeError(error_message)

    def run_sync(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ) -> CompletedCommand:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rc, out, err = loop.run_until_complete(self.run_async(cmd, timeout=timeout, error_message=error_message))
        loop.close()
        return CompletedCommand(args=cmd, returncode=rc, stdout=out, stderr=err)
