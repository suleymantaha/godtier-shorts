"""Checks that runtime backend imports are represented in requirements.txt."""

from __future__ import annotations

from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements.txt"


def _normalized_requirement_names() -> set[str]:
    names: set[str] = set()
    for raw_line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        package = line.split(";", 1)[0].strip()
        for separator in ("[", ">=", "==", "<=", "~=", "!=", ">", "<"):
            if separator in package:
                package = package.split(separator, 1)[0].strip()
        names.add(package.lower().replace("_", "-"))
    return names


def test_requirements_cover_critical_runtime_dependencies() -> None:
    requirement_names = _normalized_requirement_names()

    assert "pyjwt" in requirement_names
    assert "cryptography" in requirement_names

