#!/usr/bin/env python3
"""Validate runtime configuration without starting the full app."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime_validation import validate_runtime_configuration


def main() -> None:
    load_dotenv()
    validate_runtime_configuration()
    print("runtime configuration ok")


if __name__ == "__main__":
    main()
