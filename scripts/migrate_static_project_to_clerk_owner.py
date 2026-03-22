#!/usr/bin/env python3
"""Migrate an owner-scoped project from a static-token subject to a Clerk subject."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.config as config
from backend.services.ownership import (
    reassign_project_owner,
)


def migrate_project_owner(old_project_id: str, new_owner_subject: str) -> dict[str, object]:
    return reassign_project_owner(old_project_id, new_owner_subject=new_owner_subject)


def main(argv: list[str] | None = None) -> dict[str, object]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="existing owner-scoped project id")
    parser.add_argument("--new-owner-subject", required=True, help="target Clerk subject")
    parser.add_argument("--yes", action="store_true", help="apply the migration")
    args = parser.parse_args(argv)
    if not args.yes:
        raise SystemExit("Refusing to migrate project owner without --yes")

    summary = migrate_project_owner(args.project, args.new_owner_subject)
    for key, value in summary.items():
        print(f"{key}={value}")
    return summary


if __name__ == "__main__":
    main()
