from __future__ import annotations

from backend.system_validation import SystemCheckResult, run_system_dependency_checks, summarize_failures
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
