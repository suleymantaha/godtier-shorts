#!/usr/bin/env python3
"""Pin direct requirements to the currently installed versions."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.requirements import Requirement

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "requirements.txt"
TARGET = PROJECT_ROOT / "requirements.lock"


def _pin_requirement(raw_line: str) -> str:
    requirement = Requirement(raw_line)
    package_name = requirement.name
    try:
        installed_version = version(package_name)
    except PackageNotFoundError as exc:
        raise RuntimeError(f"Package not installed for lock generation: {package_name}") from exc

    extras = f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
    marker = f"; {requirement.marker}" if requirement.marker else ""
    return f"{package_name}{extras}=={installed_version}{marker}"


def main() -> int:
    lines: list[str] = []
    for raw_line in SOURCE.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(raw_line)
            continue
        lines.append(_pin_requirement(stripped))

    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
