#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"
if [[ ! -f requirements.lock ]]; then
  echo "requirements.lock missing; run scripts/update_requirements_lock.sh first" >&2
  exit 1
fi

IGNORE_ARGS=()
while read -r line; do
  line="${line%%#*}"
  line="${line// /}"
  [[ -n "$line" ]] && IGNORE_ARGS+=(--ignore-vuln "$line")
done < .pip-audit-ignore

python -m pip_audit -r requirements.lock --no-deps --disable-pip --progress-spinner off "${IGNORE_ARGS[@]}"
