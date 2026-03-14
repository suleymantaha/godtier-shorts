"""System dependency validation helpers for fresh installs."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable


Probe = Callable[[], tuple[bool, str]]


@dataclass(frozen=True, slots=True)
class SystemCheckResult:
    name: str
    required: bool
    ok: bool
    detail: str


def run_system_dependency_checks(*, require_gpu: bool = False) -> list[SystemCheckResult]:
    """Validate required CLI/runtime dependencies for local media processing."""
    results = [
        _run_cli_check("ffmpeg", ["ffmpeg", "-version"], required=True),
        _run_cli_check("yt-dlp", ["yt-dlp", "--version"], required=True),
        _run_cli_check("nvidia-smi", ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], required=require_gpu),
        _run_probe_check("torch.cuda", _probe_torch_cuda, required=require_gpu),
    ]
    return results


def summarize_failures(results: Iterable[SystemCheckResult]) -> list[str]:
    """Collect blocking failure messages."""
    return [f"{result.name}: {result.detail}" for result in results if result.required and not result.ok]


def _run_cli_check(name: str, cmd: list[str], *, required: bool) -> SystemCheckResult:
    binary = cmd[0]
    path = shutil.which(binary)
    if path is None:
        return SystemCheckResult(
            name=name,
            required=required,
            ok=False,
            detail=f"binary bulunamadi: {binary}",
        )

    try:
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"komut basarisiz: {' '.join(cmd)}"
        return SystemCheckResult(name=name, required=required, ok=False, detail=detail)

    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    summary = output[0] if output else f"ok ({path})"
    return SystemCheckResult(name=name, required=required, ok=True, detail=summary)


def _run_probe_check(name: str, probe: Probe, *, required: bool) -> SystemCheckResult:
    ok, detail = probe()
    return SystemCheckResult(name=name, required=required, ok=ok, detail=detail)


def _probe_torch_cuda() -> tuple[bool, str]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - defensive import guard
        return False, f"torch import hatasi: {exc}"

    if not torch.cuda.is_available():
        version = getattr(torch.version, "cuda", None) or "none"
        return False, f"cuda kullanilabilir degil (torch cuda={version})"

    device_name = torch.cuda.get_device_name(0)
    version = getattr(torch.version, "cuda", None) or "unknown"
    return True, f"{device_name} (torch cuda={version})"
