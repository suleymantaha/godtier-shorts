#!/usr/bin/env python3
"""CI guardrails for legacy/orphan Python entrypoints and imports."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"[orphan-check] {message}")
    sys.exit(1)


# 1) Prevent re-introducing legacy top-level subtitle renderer module.
legacy_renderer = ROOT / "subtitle_renderer.py"
if legacy_renderer.exists():
    fail(
        "Top-level 'subtitle_renderer.py' bulundu. Kanonik modül yolu "
        "'backend.services.subtitle_renderer' olmalı."
    )

# 2) Ensure imports don't reference ambiguous top-level module path.
for path in ROOT.rglob("*.py"):
    if ".git" in path.parts or ".venv" in path.parts:
        continue
    if path.name == "check_orphan_legacy.py":
        continue

    text = path.read_text(encoding="utf-8", errors="ignore")
    if "from subtitle_renderer import" in text or "import subtitle_renderer" in text:
        rel = path.relative_to(ROOT)
        fail(
            f"{rel} içinde legacy import bulundu. "
            "'backend.services.subtitle_renderer' kullanın."
        )

print("[orphan-check] OK")
