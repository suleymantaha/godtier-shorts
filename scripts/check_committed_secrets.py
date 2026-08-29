"""Fails the build when a credential-looking literal is tracked in Git.

Production secrets must only ever arrive through the environment or the
deployment platform. This scan is deliberately conservative: it looks for
provider-shaped tokens and for non-placeholder assignments to known secret
variable names, and it ignores documentation placeholders such as
``IYZICO_API_KEY=`` in ``.env.example``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SKIPPED_SUFFIXES = frozenset({".lock", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".pt", ".woff2"})
SKIPPED_PATH_PARTS = frozenset({"node_modules", "dist", "build", "coverage", "__pycache__"})

TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("clerk secret key", re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("openrouter key", re.compile(r"sk-or-v1-[A-Za-z0-9]{24,}")),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)

SECRET_VARIABLE = re.compile(
    r"\b(?P<name>[A-Z0-9_]*(?:SECRET|PASSWORD|API_KEY|ACCESS_KEY|TOKEN|DSN))\s*[:=]\s*"
    r"(?P<quote>['\"]?)(?P<value>[^\s'\"#]{12,})(?P=quote)"
)

# Values that are obviously not live credentials.
PLACEHOLDER = re.compile(
    r"^(?:\$\{|\$\(|<|your[-_]|change[-_]?me|replace[-_]|example|placeholder|dummy|test[-_]|fake[-_]|"
    r"xxx|\.{3}|secrets\.|process\.env|os\.environ|None$|null$|true$|false$)",
    re.IGNORECASE,
)


ALLOWLIST_PRAGMA = "pragma: allowlist secret"

# ``${VAR:?msg}`` / ``$(cmd)`` expansions are indirection, never a literal.
SHELL_EXPANSION = re.compile(r"\$+\{[^}]*\}|\$\([^)]*\)")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    reason: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}"


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    )
    paths: list[Path] = []
    for entry in result.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        path = Path(entry)
        if path.suffix.lower() in SKIPPED_SUFFIXES:
            continue
        if SKIPPED_PATH_PARTS & set(path.parts):
            continue
        paths.append(path)
    return paths


def scan_text(relative_path: str, text: str) -> list[Finding]:
    """Return credential-looking literals found in ``text``."""

    findings: list[Finding] = []
    is_placeholder_file = relative_path.endswith((".example", ".md", ".sample"))

    for number, raw_line in enumerate(text.splitlines(), start=1):
        if ALLOWLIST_PRAGMA in raw_line:
            continue

        line = SHELL_EXPANSION.sub("", raw_line)
        for label, pattern in TOKEN_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(relative_path, number, f"{label} literal"))

        if is_placeholder_file:
            continue

        match = SECRET_VARIABLE.search(line)
        if match and not PLACEHOLDER.match(match.group("value")):
            findings.append(
                Finding(relative_path, number, f"hardcoded value for {match.group('name')}")
            )

    return findings


def main() -> int:
    findings: list[Finding] = []
    for path in _tracked_files():
        absolute = PROJECT_ROOT / path
        try:
            text = absolute.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(path.as_posix(), text))

    if findings:
        print("secret scan: credential-looking literals are tracked in git", file=sys.stderr)
        for finding in findings:
            print(f"   {finding.render()}", file=sys.stderr)
        return 1

    print("secret scan ok (no credential literals tracked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
