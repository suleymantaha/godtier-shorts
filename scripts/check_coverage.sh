#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "[coverage] backend"
pytest backend/tests \
  --cov=backend \
  --cov-report=term-missing \
  --cov-report=xml:coverage/backend/coverage.xml \
  --cov-report=html:coverage/backend/html \
  --cov-report=json:coverage/backend/coverage.json

echo "[coverage] frontend"
bash -lc "cd frontend && npm run test:coverage -- --reporter=dot"
