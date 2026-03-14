from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_python_toolchain_contract_is_aligned() -> None:
    expected = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyre_toml = tomllib.loads((ROOT / "pyre.toml").read_text(encoding="utf-8"))
    pyright = json.loads((ROOT / "pyrightconfig.json").read_text(encoding="utf-8"))
    pyre_json = json.loads((ROOT / ".pyre_configuration").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")

    assert pyproject["tool"]["pyre"]["python_version"] == expected
    assert pyre_toml["python_version"] == expected
    assert pyright["pythonVersion"] == expected
    assert pyre_json["python"]["version"] == expected
    assert pyre_json["search_path"] == ["."]
    assert f'python-version: "{expected}"' in workflow


def test_node_toolchain_contract_is_aligned() -> None:
    expected_node = (ROOT / ".nvmrc").read_text(encoding="utf-8").strip()
    package_json = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")

    assert package_json["packageManager"].startswith("npm@10.")
    assert package_json["engines"]["node"] == f">={expected_node} <{int(expected_node) + 1}"
    assert package_json["engines"]["npm"] == ">=10 <11"
    assert f'node-version: "{expected_node}"' in workflow


def test_verify_gate_runs_toolchain_and_runtime_checks() -> None:
    verify_script = (ROOT / "scripts" / "verify.sh").read_text(encoding="utf-8")

    assert 'python scripts/check_toolchain.py' in verify_script
    assert 'python scripts/check_runtime_config.py' in verify_script
