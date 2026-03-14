"""Guardrails for ViralAnalyzer refactor boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

ANALYZER_PATH = Path(__file__).resolve().parents[1] / "services" / "viral_analyzer.py"
CORE_PATH = Path(__file__).resolve().parents[1] / "services" / "viral_analyzer_core.py"
MAX_ANALYZER_LINES = 350
MAX_METHOD_LINES = 110
TARGET_METHODS = {"analyze_metadata", "analyze_transcript_segment"}


def _method_lengths() -> dict[str, int]:
    tree = ast.parse(ANALYZER_PATH.read_text(encoding="utf-8"))
    analyzer_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ViralAnalyzer"
    )
    lengths: dict[str, int] = {}
    for node in analyzer_class.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", node.lineno)
            lengths[node.name] = end_lineno - node.lineno + 1
    return lengths


def test_analyzer_file_line_budget() -> None:
    line_count = len(ANALYZER_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count <= MAX_ANALYZER_LINES, f"viral_analyzer.py satır: {line_count}, hedef <= {MAX_ANALYZER_LINES}"


def test_core_module_exists_and_is_nontrivial() -> None:
    assert CORE_PATH.exists()
    line_count = len(CORE_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count >= 120


def test_target_method_lengths() -> None:
    lengths = _method_lengths()
    for name in TARGET_METHODS:
        assert name in lengths
        assert lengths[name] <= MAX_METHOD_LINES, f"{name} çok uzun: {lengths[name]} satır"
