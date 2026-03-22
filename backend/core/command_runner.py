"""Subprocess execution with cancellation and timeout handling."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CompletedCommand:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


OutputLineHandler = Callable[[str, str], None]


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
        activity_timeout: float | None = None,
        on_output: OutputLineHandler | None = None,
    ) -> tuple[int, str, str]:
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        last_activity_at = started_at
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _drain_stream(stream: asyncio.StreamReader | None, stream_name: str) -> str:
            nonlocal last_activity_at
            if stream is None:
                return ""

            buffer: list[str] = []
            while True:
                chunk = await stream.readline()
                if not chunk:
                    break
                decoded = chunk.decode(errors="replace")
                buffer.append(decoded)
                last_activity_at = loop.time()
                if on_output is not None:
                    on_output(stream_name, decoded.rstrip("\r\n"))
            return "".join(buffer)

        stdout_task = asyncio.create_task(_drain_stream(proc.stdout, "stdout"))
        stderr_task = asyncio.create_task(_drain_stream(proc.stderr, "stderr"))

        try:
            while proc.returncode is None:
                if self._cancel_event.is_set():
                    raise RuntimeError("Job cancelled by user")
                now = loop.time()
                if now - started_at > timeout:
                    raise RuntimeError(error_message)
                if activity_timeout is not None and now - last_activity_at > activity_timeout:
                    raise RuntimeError(error_message)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=self._poll_interval)
                except asyncio.TimeoutError:
                    continue

            stdout_text, stderr_text = await asyncio.gather(stdout_task, stderr_task)
            return proc.returncode or 0, stdout_text, stderr_text
        except RuntimeError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            stdout_task.cancel()
            stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stdout_task
            with contextlib.suppress(asyncio.CancelledError):
                await stderr_task
            raise

    def run_sync(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
        activity_timeout: float | None = None,
        on_output: OutputLineHandler | None = None,
    ) -> CompletedCommand:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rc, out, err = loop.run_until_complete(
            self.run_async(
                cmd,
                timeout=timeout,
                error_message=error_message,
                activity_timeout=activity_timeout,
                on_output=on_output,
            )
        )
        loop.close()
        return CompletedCommand(args=cmd, returncode=rc, stdout=out, stderr=err)
