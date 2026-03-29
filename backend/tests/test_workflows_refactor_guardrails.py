"""Guardrails for workflow module decomposition."""

from __future__ import annotations

from pathlib import Path

import backend.core.workflows as workflows

WORKFLOWS_FACADE = Path(__file__).resolve().parents[1] / "core" / "workflows.py"
MODULE_BUDGETS = {
    "workflows_pipeline.py": 300,
    "workflows_manual.py": 340,
    "workflows_batch.py": 220,
    "workflows_reburn.py": 150,
}


def test_workflows_facade_is_thin() -> None:
    line_count = len(WORKFLOWS_FACADE.read_text(encoding="utf-8").splitlines())
    assert line_count <= 50, f"workflows.py satır sayısı {line_count}; hedef <= 50"


def test_workflow_module_line_budgets() -> None:
    core_dir = WORKFLOWS_FACADE.parent
    for filename, budget in MODULE_BUDGETS.items():
        path = core_dir / filename
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= budget, f"{filename} satır sayısı {line_count}; hedef <= {budget}"


def test_workflows_public_exports_are_stable() -> None:
    expected = {
        "OrchestratorContext",
        "PipelineWorkflow",
        "ManualClipWorkflow",
        "CutPointsWorkflow",
        "BatchClipWorkflow",
        "ReburnWorkflow",
    }
    assert set(workflows.__all__) == expected
