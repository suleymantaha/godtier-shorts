#!/usr/bin/env python3
"""Validate local markdown links inside repo documents."""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
IGNORED_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def _candidate_targets(source: Path, raw_target: str) -> list[Path]:
    target = raw_target.strip()
    if not target or target.startswith("#") or target.startswith(IGNORED_PREFIXES):
        return []

    target = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not target:
        return []

    path = Path(target)
    if path.suffix and path.suffix.lower() != ".md":
        return []
    resolved = path if path.is_absolute() else (source.parent / path).resolve()
    candidates = [resolved]
    if resolved.is_dir() or str(target).endswith("/"):
        candidates.append(resolved / "README.md")
        candidates.append(resolved / "index.md")
    return candidates


def _iter_markdown_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_file() and target.suffix == ".md":
            files.append(target)
            continue
        if target.is_dir():
            files.extend(sorted(path for path in target.rglob("*.md") if path.is_file()))
    return files


def main(argv: list[str]) -> int:
    roots = [Path(arg).resolve() for arg in (argv or ["docs", "README.md"])]
    markdown_files = _iter_markdown_files(roots)
    missing: list[str] = []

    for source in markdown_files:
        content = source.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(content):
            candidates = _candidate_targets(source, raw_target)
            if not candidates:
                continue
            if any(candidate.exists() for candidate in candidates):
                continue
            missing.append(f"{source.relative_to(Path.cwd())} -> {raw_target}")

    if missing:
        print(f"Missing local markdown targets: {len(missing)}")
        for item in missing:
            print(item)
        return 1

    print(f"Markdown links ok: {len(markdown_files)} files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
