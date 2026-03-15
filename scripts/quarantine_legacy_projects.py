#!/usr/bin/env python3
"""Quarantine legacy workspace projects that do not have an ownership manifest."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.ownership import quarantine_legacy_projects


def main() -> list[str]:
    quarantined = quarantine_legacy_projects()
    if quarantined:
        for project_id in quarantined:
            print(project_id)
    else:
        print("no legacy projects found")
    return quarantined


if __name__ == "__main__":
    main()
