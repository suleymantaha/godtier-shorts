"""Fails the build when an Alembic upgrade path performs destructive schema work.

Production v1 forbids destructive schema migrations: an upgrade must be
forward-compatible so that a failed deploy can roll the application back to the
previous image without losing data. Destruction is still allowed inside
``downgrade()`` because that path is only used for local development.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = PROJECT_ROOT / "alembic" / "versions"

FORBIDDEN_OPERATIONS = frozenset(
    {
        "drop_table",
        "drop_column",
        "rename_table",
    }
)

# ``alter_column`` is only destructive when it narrows the contract of an
# existing column; widening a type or relaxing nullability stays allowed.
NARROWING_ALTER_KEYWORDS = frozenset({"new_column_name", "type_"})

FORBIDDEN_SQL = re.compile(
    r"\b(drop\s+table|drop\s+column|drop\s+database|truncate|rename\s+to)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    """A single destructive statement found inside an ``upgrade()`` body."""

    path: Path
    line: int
    operation: str

    def render(self) -> str:
        relative = self.path.relative_to(PROJECT_ROOT).as_posix()
        return f"{relative}:{self.line}: destructive upgrade operation `{self.operation}`"


def _called_operation(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "op":
            return func.attr
    return None


def _literal_sql(node: ast.Call) -> str:
    parts: list[str] = []
    for argument in node.args:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            parts.append(argument.value)
    return " ".join(parts)


def _narrows_column(node: ast.Call) -> bool:
    for keyword in node.keywords:
        if keyword.arg in NARROWING_ALTER_KEYWORDS:
            return True
        if keyword.arg == "nullable" and isinstance(keyword.value, ast.Constant):
            if keyword.value.value is False:
                return True
    return False


def find_destructive_operations(path: Path) -> list[Finding]:
    """Return every destructive operation reachable from ``upgrade()``."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    findings: list[Finding] = []

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "upgrade":
            continue

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            operation = _called_operation(child)
            if operation is None:
                continue

            if operation in FORBIDDEN_OPERATIONS:
                findings.append(Finding(path, child.lineno, operation))
                continue

            if operation == "alter_column" and _narrows_column(child):
                findings.append(Finding(path, child.lineno, "alter_column (narrowing)"))
                continue

            if operation == "execute" and FORBIDDEN_SQL.search(_literal_sql(child)):
                findings.append(Finding(path, child.lineno, "execute (destructive SQL)"))

    return findings


def main() -> int:
    if not VERSIONS_DIR.is_dir():
        print(f"migration safety: versions directory missing: {VERSIONS_DIR}", file=sys.stderr)
        return 1

    findings: list[Finding] = []
    migrations = sorted(VERSIONS_DIR.glob("*.py"))
    for migration in migrations:
        findings.extend(find_destructive_operations(migration))

    if findings:
        print("migration safety: destructive schema upgrades are banned in production v1", file=sys.stderr)
        for finding in findings:
            print(f"   {finding.render()}", file=sys.stderr)
        return 1

    print(f"migration safety ok ({len(migrations)} migrations, no destructive upgrades)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
