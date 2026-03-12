#!/usr/bin/env bash
set -euo pipefail

PYRE_BIN="${PYRE_BIN:-pyre}"
PYRE_INTERPRETER="${PYRE_PYTHON_INTERPRETER:-}"
PYRE_SITE_PACKAGES="${PYRE_SITE_PACKAGES:-}"

args=()
if [[ -n "$PYRE_INTERPRETER" ]]; then
  args+=(--python-interpreter "$PYRE_INTERPRETER")
fi
if [[ -n "$PYRE_SITE_PACKAGES" ]]; then
  args+=(--search-path "$PYRE_SITE_PACKAGES")
fi

exec "$PYRE_BIN" "${args[@]}" check "$@"
