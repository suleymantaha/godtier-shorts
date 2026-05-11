#!/usr/bin/env python3
"""Validate the local toolchain against the pinned project contract."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    python_target = _read_text(PROJECT_ROOT / ".python-version")
    node_target = _read_text(PROJECT_ROOT / ".nvmrc")
    package_json = json.loads((PROJECT_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

    _require_python_version(python_target)
    _require_node_major(node_target)
    _require_npm_major(_parse_package_manager_major(package_json["packageManager"]))
    _require_python_config_alignment(python_target)
    _require_node_config_alignment(node_target, package_json)

    print("toolchain ok")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _require_python_version(expected: str) -> None:
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual != expected:
        raise SystemExit(f"Python {expected}.x gerekli, mevcut: {sys.version.split()[0]}")


def _require_node_major(expected_major: str) -> None:
    actual = _run_version(["node", "--version"])
    major = _extract_major(actual)
    if major != int(expected_major):
        raise SystemExit(f"Node {expected_major}.x gerekli, mevcut: {actual}")


def _require_npm_major(expected_major: int) -> None:
    actual = _run_version(["npm", "--version"])
    major = _extract_major(actual)
    if major != expected_major:
        raise SystemExit(f"npm {expected_major}.x gerekli, mevcut: {actual}")


def _require_python_config_alignment(expected: str) -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyre_toml = tomllib.loads((PROJECT_ROOT / "pyre.toml").read_text(encoding="utf-8"))
    pyright = json.loads((PROJECT_ROOT / "pyrightconfig.json").read_text(encoding="utf-8"))
    pyre_json = json.loads((PROJECT_ROOT / ".pyre_configuration").read_text(encoding="utf-8"))
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")

    pyproject_version = pyproject["tool"]["pyre"]["python_version"]
    pyre_version = pyre_toml["python_version"]
    pyright_version = pyright["pythonVersion"]
    pyre_json_version = pyre_json["python"]["version"]

    if {pyproject_version, pyre_version, pyright_version, pyre_json_version} != {expected}:
        raise SystemExit("Python toolchain config dosyalari hizali degil")
    if pyre_json.get("search_path") != ["."]:
        raise SystemExit(".pyre_configuration search_path portable degil")
    if f'python-version: "{expected}"' not in workflow:
        raise SystemExit("CI Python version sozlesmesi hizali degil")


def _require_node_config_alignment(expected_major: str, package_json: dict) -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
    engines = package_json.get("engines", {})
    node_engine = engines.get("node")
    npm_engine = engines.get("npm")
    package_manager_major = _parse_package_manager_major(package_json["packageManager"])

    if node_engine != f">={expected_major} <{int(expected_major) + 1}":
        raise SystemExit("frontend/package.json node engine hizali degil")
    if npm_engine != f">={package_manager_major} <{package_manager_major + 1}":
        raise SystemExit("frontend/package.json npm engine hizali degil")
    if f'node-version: "{expected_major}"' not in workflow:
        raise SystemExit("CI Node version sozlesmesi hizali degil")


def _parse_package_manager_major(package_manager: str) -> int:
    match = re.match(r"npm@(\d+)\.", package_manager)
    if match is None:
        raise SystemExit("frontend/package.json packageManager alani gecersiz")
    return int(match.group(1))


def _run_version(cmd: list[str]) -> str:
    executable = _resolve_executable(cmd[0])
    completed = subprocess.run([executable, *cmd[1:]], check=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return completed.stdout.strip()


def _resolve_executable(name: str) -> str:
    candidates = [name]
    if sys.platform == "win32" and not name.lower().endswith((".exe", ".cmd", ".bat")):
        candidates = [f"{name}.cmd", f"{name}.exe", f"{name}.bat", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SystemExit(f"Komut bulunamadi: {name}")


def _extract_major(raw: str) -> int:
    match = re.search(r"(\d+)", raw)
    if match is None:
        raise SystemExit(f"Versiyon okunamadi: {raw}")
    return int(match.group(1))


if __name__ == "__main__":
    main()
