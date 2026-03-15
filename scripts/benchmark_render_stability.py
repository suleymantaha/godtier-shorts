#!/usr/bin/env python3
"""Benchmark determinism and throughput for an existing clip render."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.render_benchmark import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark determinism and render throughput for an existing clip.")
    parser.add_argument("--project", required=True, help="Owner-scoped project id")
    parser.add_argument("--clip", required=True, help="Clip filename, e.g. clip_1.mp4")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument("--samples", type=int, default=5, help="Frame hash samples per run")
    parser.add_argument("--keep-outputs", action="store_true", help="Keep temporary rendered outputs")
    args = parser.parse_args()

    report = run_benchmark(
        project_id=args.project,
        clip_name=args.clip,
        run_count=args.runs,
        sample_count=args.samples,
        keep_outputs=args.keep_outputs,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("deterministic") else 1


if __name__ == "__main__":
    raise SystemExit(main())
