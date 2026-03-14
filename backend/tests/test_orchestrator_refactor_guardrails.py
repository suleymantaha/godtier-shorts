"""Guardrail tests for orchestrator facade size and method length budgets."""

from __future__ import annotations

import ast
from pathlib import Path

ORCHESTRATOR_PATH = Path(__file__).resolve().parents[1] / "core" / "orchestrator.py"
MAX_ORCHESTRATOR_LINES = 350
MAX_FACADE_METHOD_LINES = 65
FACADE_METHODS = {
    "run_pipeline_async",
    "run_manual_clip_async",
    "run_manual_clips_from_cut_points_async",
    "run_batch_manual_clips_async",
    "reburn_subtitles_async",
}


def _method_lengths() -> dict[str, int]:
    tree = ast.parse(ORCHESTRATOR_PATH.read_text(encoding="utf-8"))
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GodTierShortsCreator"
    )
    lengths: dict[str, int] = {}
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", node.lineno)
            lengths[node.name] = end_lineno - node.lineno + 1
    return lengths


def test_orchestrator_file_line_budget() -> None:
    line_count = len(ORCHESTRATOR_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count <= MAX_ORCHESTRATOR_LINES, (
        f"orchestrator.py satır sayısı {line_count}; hedef <= {MAX_ORCHESTRATOR_LINES}"
    )


def test_facade_method_line_budget() -> None:
    lengths = _method_lengths()
    for method_name in FACADE_METHODS:
        assert method_name in lengths, f"Beklenen facade methodu bulunamadı: {method_name}"
        assert lengths[method_name] <= MAX_FACADE_METHOD_LINES, (
            f"{method_name} çok uzun: {lengths[method_name]} satır (hedef <= {MAX_FACADE_METHOD_LINES})"
        )
