"""System dependency validation helpers for fresh installs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Iterable


Probe = Callable[[], tuple[bool, str]]
NVENC_SMOKE_DIMENSIONS = "256x256"


@dataclass(frozen=True, slots=True)
class SystemCheckResult:
    name: str
    required: bool
    ok: bool
    detail: str


def run_system_dependency_checks(
    *,
    require_gpu: bool = False,
    require_nvenc: bool = False,
) -> list[SystemCheckResult]:
    """Validate required CLI/runtime dependencies for local media processing."""
    gpu_required = require_gpu or require_nvenc
    results = [
        _run_cli_check("ffmpeg", ["ffmpeg", "-version"], required=True),
        _run_cli_check("yt-dlp", ["yt-dlp", "--version"], required=True),
        _run_cli_check("nvidia-smi", ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], required=gpu_required),
        _run_probe_check("torch.cuda", _probe_torch_cuda, required=gpu_required),
    ]
    if require_nvenc:
        results.append(_run_probe_check("ffmpeg.nvenc", _probe_ffmpeg_nvenc, required=True))
    return results


def summarize_failures(results: Iterable[SystemCheckResult]) -> list[str]:
    """Collect blocking failure messages."""
    return [f"{result.name}: {result.detail}" for result in results if result.required and not result.ok]


def log_system_dependency_results(results: Iterable[SystemCheckResult]) -> None:
    """Emit dependency probe results with the same semantics as the CLI helper."""
    from loguru import logger

    for result in results:
        if result.ok:
            logger.info("System dependency ok: {} -> {}", result.name, result.detail)
        elif result.required:
            logger.error("System dependency fail: {} -> {}", result.name, result.detail)
        else:
            logger.warning("System dependency warn: {} -> {}", result.name, result.detail)


def validate_accelerator_support_configuration() -> None:
    """Optionally fail startup when GPU/NVENC are required for the app."""
    require_gpu = _env_flag("REQUIRE_CUDA_FOR_APP")
    require_nvenc = _env_flag("REQUIRE_NVENC_FOR_APP")
    log_optional_status = _env_flag("LOG_ACCELERATOR_STATUS_ON_STARTUP", default=False)

    if not require_gpu and not require_nvenc and not log_optional_status:
        return

    results = run_system_dependency_checks(
        require_gpu=require_gpu or require_nvenc,
        require_nvenc=require_nvenc,
    )
    log_system_dependency_results(results)
    failures = summarize_failures(results)
    if failures:
        raise RuntimeError(
            "Accelerator runtime validation failed: " + "; ".join(failures)
        )


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
        detail = f"cuda kullanilabilir degil (torch cuda={version})"
        if _running_inside_codex_sandbox():
            detail += " [sandbox-restricted probe possible]"
        return False, detail

    device_name = torch.cuda.get_device_name(0)
    version = getattr(torch.version, "cuda", None) or "unknown"
    return True, f"{device_name} (torch cuda={version})"


def _probe_ffmpeg_nvenc() -> tuple[bool, str]:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        return False, "binary bulunamadi: ffmpeg"

    with tempfile.TemporaryDirectory(prefix="nvenc-smoke-") as temp_dir:
        output_path = os.path.join(temp_dir, "smoke.mp4")
        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={NVENC_SMOKE_DIMENSIONS}:rate=30",
            "-frames:v",
            "8",
            "-c:v",
            "h264_nvenc",
            output_path,
        ]
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, f"h264_nvenc smoke ok ({NVENC_SMOKE_DIMENSIONS})"

    detail = (completed.stderr or completed.stdout or "").strip()
    summary = detail.splitlines()[-1] if detail else "h264_nvenc smoke basarisiz"
    if _running_inside_codex_sandbox():
        summary += " [sandbox-restricted probe possible]"
    return False, summary


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _running_inside_codex_sandbox() -> bool:
    return bool(os.getenv("CODEX_SANDBOX") or os.getenv("CODEX_CI") or os.getenv("CODEX_THREAD_ID"))
