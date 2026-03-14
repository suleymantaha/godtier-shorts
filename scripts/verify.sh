#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_step() {
  local label="$1"
  shift

  echo "[verify] $label"
  "$@"
}

cd "$PROJECT_ROOT"

run_step "toolchain" python scripts/check_toolchain.py
run_step "runtime config" python scripts/check_runtime_config.py
run_step "frontend lint" bash -lc "cd frontend && npm run lint"
run_step "frontend test" bash -lc "cd frontend && npm run test -- --reporter=dot"
run_step "backend pytest" pytest backend/tests -q
run_step "frontend build" bash -lc "cd frontend && npm run build"

echo "[verify] all checks passed"
