#!/usr/bin/env python3
"""Resolve complete Linux/Python 3.13 dependency locks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    for source, target in (
        ("requirements.txt", "requirements.lock"),
        ("requirements-api.txt", "requirements-api.lock"),
    ):
        try:
            subprocess.run(
                ["uv", "pip", "compile", source,
                 "--python-version", "3.13",
                 "--python-platform", "x86_64-unknown-linux-gnu",
                 "--output-file", target, "--quiet"],
                cwd=PROJECT_ROOT,
                check=True,
            )
        except FileNotFoundError as exc:
            raise SystemExit("uv is required: python -m pip install uv") from exc
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
