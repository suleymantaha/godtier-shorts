from __future__ import annotations

import asyncio
import sys
import threading

import pytest

from backend.core.command_runner import CommandRunner


def test_run_async_streams_output_lines() -> None:
    runner = CommandRunner(threading.Event(), poll_interval=0.01)
    seen: list[tuple[str, str]] = []

    command = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "print('stdout-1', flush=True); "
            "sys.stderr.write('stderr-1\\n'); sys.stderr.flush(); "
            "time.sleep(0.05); "
            "print('stdout-2', flush=True)"
        ),
    ]

    rc, stdout, stderr = asyncio.run(
        runner.run_async(
            command,
            timeout=2,
            activity_timeout=1,
            error_message="timeout",
            on_output=lambda stream_name, line: seen.append((stream_name, line)),
        )
    )

    assert rc == 0
    assert "stdout-1" in stdout
    assert "stdout-2" in stdout
    assert "stderr-1" in stderr
    assert ("stdout", "stdout-1") in seen
    assert ("stderr", "stderr-1") in seen


def test_run_async_activity_timeout_resets_when_output_continues() -> None:
    runner = CommandRunner(threading.Event(), poll_interval=0.01)
    command = [
        sys.executable,
        "-c",
        (
            "import time; "
            "print('tick-1', flush=True); "
            "time.sleep(0.03); "
            "print('tick-2', flush=True); "
            "time.sleep(0.03); "
            "print('tick-3', flush=True)"
        ),
    ]

    rc, stdout, _stderr = asyncio.run(
        runner.run_async(
            command,
            timeout=2,
            activity_timeout=0.1,
            error_message="idle-timeout",
        )
    )

    assert rc == 0
    assert "tick-3" in stdout


def test_run_async_activity_timeout_raises_when_process_stalls() -> None:
    runner = CommandRunner(threading.Event(), poll_interval=0.01)
    command = [
        sys.executable,
        "-c",
        (
            "import time; "
            "print('tick', flush=True); "
            "time.sleep(0.25)"
        ),
    ]

    with pytest.raises(RuntimeError, match="idle-timeout"):
        asyncio.run(
            runner.run_async(
                command,
                timeout=2,
                activity_timeout=0.05,
                error_message="idle-timeout",
            )
        )
