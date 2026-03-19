#!/usr/bin/env python3
"""Validate system-level media processing dependencies."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.system_validation import run_system_dependency_checks, summarize_failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-gpu",
        action="store_true",
        help="GPU kontrollerini zorunlu hale getir",
    )
    parser.add_argument(
        "--require-nvenc",
        action="store_true",
        help="ffmpeg h264_nvenc smoke testini zorunlu hale getir",
    )
    args = parser.parse_args()

    results = run_system_dependency_checks(
        require_gpu=args.require_gpu or args.require_nvenc,
        require_nvenc=args.require_nvenc,
    )
    failures = summarize_failures(results)

    for result in results:
        level = "ok" if result.ok else ("fail" if result.required else "warn")
        suffix = "required" if result.required else "optional"
        print(f"[{level}] {result.name} ({suffix}) - {result.detail}")

    if failures:
        raise SystemExit("system dependency check failed")

    print("system dependencies ok")


if __name__ == "__main__":
    main()
