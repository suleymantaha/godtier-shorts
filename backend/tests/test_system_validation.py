from __future__ import annotations

import sys
import pytest

from backend.system_validation import (
    SystemCheckResult,
    run_system_dependency_checks,
    summarize_failures,
    validate_accelerator_support_configuration,
)
import backend.system_validation as system_validation


def test_summarize_failures_only_returns_required_failures() -> None:
    results = [
        SystemCheckResult(name="ffmpeg", required=True, ok=False, detail="missing"),
        SystemCheckResult(name="nvidia-smi", required=False, ok=False, detail="missing"),
        SystemCheckResult(name="yt-dlp", required=True, ok=True, detail="ok"),
    ]

    assert summarize_failures(results) == ["ffmpeg: missing"]


def test_run_system_dependency_checks_treats_gpu_as_optional_by_default(monkeypatch) -> None:
    def fake_cli(name: str, cmd: list[str], *, required: bool) -> SystemCheckResult:
        return SystemCheckResult(name=name, required=required, ok=name != "nvidia-smi", detail="stub")

    def fake_probe(name: str, probe, *, required: bool) -> SystemCheckResult:
        return SystemCheckResult(name=name, required=required, ok=False, detail="cuda unavailable")

    monkeypatch.setattr(system_validation, "_run_cli_check", fake_cli)
    monkeypatch.setattr(system_validation, "_run_probe_check", fake_probe)

    results = run_system_dependency_checks()

    assert [result.required for result in results] == [True, True, False, False]
    assert summarize_failures(results) == []


def test_run_system_dependency_checks_can_require_gpu(monkeypatch) -> None:
    def fake_cli(name: str, cmd: list[str], *, required: bool) -> SystemCheckResult:
        return SystemCheckResult(name=name, required=required, ok=name != "nvidia-smi", detail="stub")

    def fake_probe(name: str, probe, *, required: bool) -> SystemCheckResult:
        return SystemCheckResult(name=name, required=required, ok=False, detail="cuda unavailable")

    monkeypatch.setattr(system_validation, "_run_cli_check", fake_cli)
    monkeypatch.setattr(system_validation, "_run_probe_check", fake_probe)

    results = run_system_dependency_checks(require_gpu=True)

    assert [result.required for result in results] == [True, True, True, True]
    assert summarize_failures(results) == [
        "nvidia-smi: stub",
        "torch.cuda: cuda unavailable",
    ]


def test_run_system_dependency_checks_can_require_nvenc(monkeypatch) -> None:
    def fake_cli(name: str, cmd: list[str], *, required: bool) -> SystemCheckResult:
        return SystemCheckResult(name=name, required=required, ok=True, detail="stub")

    def fake_probe(name: str, probe, *, required: bool) -> SystemCheckResult:
        ok = name != "ffmpeg.nvenc"
        detail = "nvenc unavailable" if name == "ffmpeg.nvenc" else "stub"
        return SystemCheckResult(name=name, required=required, ok=ok, detail=detail)

    monkeypatch.setattr(system_validation, "_run_cli_check", fake_cli)
    monkeypatch.setattr(system_validation, "_run_probe_check", fake_probe)

    results = run_system_dependency_checks(require_nvenc=True)

    assert [result.name for result in results] == [
        "ffmpeg",
        "yt-dlp",
        "nvidia-smi",
        "torch.cuda",
        "ffmpeg.nvenc",
    ]
    assert [result.required for result in results] == [True, True, True, True, True]
    assert summarize_failures(results) == [
        "ffmpeg.nvenc: nvenc unavailable",
    ]


def test_validate_accelerator_support_configuration_requires_gpu_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("REQUIRE_CUDA_FOR_APP", "1")
    monkeypatch.delenv("REQUIRE_NVENC_FOR_APP", raising=False)
    monkeypatch.delenv("LOG_ACCELERATOR_STATUS_ON_STARTUP", raising=False)
    monkeypatch.setattr(
        system_validation,
        "run_system_dependency_checks",
        lambda **_kwargs: [
            SystemCheckResult(name="ffmpeg", required=True, ok=True, detail="ok"),
            SystemCheckResult(name="yt-dlp", required=True, ok=True, detail="ok"),
            SystemCheckResult(name="nvidia-smi", required=True, ok=False, detail="gpu missing"),
        ],
    )

    with pytest.raises(RuntimeError, match="gpu missing"):
        validate_accelerator_support_configuration()


def test_probe_torch_cuda_marks_sandbox_hint(monkeypatch) -> None:
    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return False

    class FakeTorch:
        cuda = FakeCuda()

        class version:
            cuda = "12.8"

    monkeypatch.setenv("CODEX_THREAD_ID", "sandbox")
    monkeypatch.setitem(sys.modules, "torch", FakeTorch())
    ok, detail = system_validation._probe_torch_cuda()
    assert ok is False
    assert "sandbox-restricted" in detail
