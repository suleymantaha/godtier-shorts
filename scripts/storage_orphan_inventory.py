#!/usr/bin/env python3
"""Offline, bounded comparison of exported R2 objects and durable storage keys.

No network, credentials, SQL execution, deletion, or quota release. Every result
is advisory, including unreferenced candidates: exports cannot prove finality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_manifest(path: Path, limit: int) -> dict[str, int]:
    rows: dict[str, int] = {}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if number > limit:
                raise ValueError(f"Manifest exceeds row bound: {path.name}")
            row = json.loads(line)
            key, size = row.get("key"), row.get("size_bytes")
            if not isinstance(key, str) or not key or type(size) is not int or size < 0:
                raise ValueError(f"Invalid manifest row: {path.name}:{number}")
            if key in rows and rows[key] != size:
                raise ValueError(f"Conflicting manifest sizes: {path.name}:{number}")
            rows[key] = size
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--max-objects", type=int, default=10_000)
    parser.add_argument("--max-references", type=int, default=100_000)
    args = parser.parse_args()
    if not (1 <= args.max_objects <= 100_000 and 1 <= args.max_references <= 1_000_000):
        parser.error("Positive bounded limits required (objects <=100000; references <=1000000)")
    try:
        objects = load_manifest(args.objects, args.max_objects)
        references = load_manifest(args.references, args.max_references)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.error(str(exc))
    for key, size in objects.items():
        if not key.startswith(("uploads/", "outputs/")):
            classification = "unknown_namespace"
        elif key not in references:
            classification = "unreferenced_candidate"
        elif size != references[key]:
            classification = "size_mismatch"
        else:
            classification = "tracked"
        print(json.dumps(dict(key=key, size_bytes=size,
            classification=classification, deletion_authorized=False)))


if __name__ == "__main__":
    main()
