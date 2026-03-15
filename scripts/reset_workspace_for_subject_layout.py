#!/usr/bin/env python3
"""Reset legacy workspace roots before the nested subject layout cutover."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.config as config


def _clear_root(root: Path) -> int:
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return 0

    deleted = 0
    for child in list(root.iterdir()):
        deleted += 1
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    root.mkdir(parents=True, exist_ok=True)
    return deleted


def reset_workspace_for_subject_layout() -> dict[str, int]:
    summary = {
        "deleted_projects": _clear_root(config.PROJECTS_DIR),
        "deleted_downloads": _clear_root(config.DOWNLOADS_DIR),
        "deleted_metadata": _clear_root(config.METADATA_DIR),
        "deleted_outputs": _clear_root(config.OUTPUTS_DIR),
    }
    config.ensure_workspace()
    return summary


def main(argv: list[str] | None = None) -> dict[str, int]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="apply the destructive workspace reset")
    args = parser.parse_args(argv)
    if not args.yes:
        raise SystemExit("Refusing to reset workspace without --yes")

    summary = reset_workspace_for_subject_layout()
    for key, value in summary.items():
        print(f"{key}={value}")
    return summary


if __name__ == "__main__":
    main()
