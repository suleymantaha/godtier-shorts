# Commands

Use the smallest command set that proves the change.

## Full Verification

- `bash scripts/verify.sh`
  - Runs toolchain validation, runtime config validation, frontend lint, frontend tests, backend pytest, and frontend build.

## Repo Contracts

- `python scripts/check_toolchain.py`
  - Verifies pinned Python, Node, npm, and config alignment with CI.
- `python scripts/check_runtime_config.py`
  - Verifies `.env`-driven runtime settings and hard limits.
- `python scripts/check_orphan_legacy.py`
  - Blocks legacy `subtitle_renderer.py` entrypoints and imports.

## Backend

- `pytest backend/tests -q`
  - Broad backend regression sweep.
- `pytest backend/tests/test_api_security.py -q`
  - HTTP auth and policy checks.
- `pytest backend/tests/test_websocket_auth.py -q`
  - WebSocket auth behavior.
- `pytest backend/tests/test_social_crypto.py -q`
  - Social encryption and startup hardening.
- `pytest backend/tests/test_workflows_refactor_guardrails.py -q`
  - Workflow decomposition budgets and exports.
- `pytest backend/tests/test_orchestrator_refactor_guardrails.py -q`
  - Orchestrator facade size and method budgets.
- `pytest backend/tests/test_subtitle_styles.py -q`
  - Subtitle preset regression coverage.

## Frontend

- `bash -lc "cd frontend && npm run lint"`
- `bash -lc "cd frontend && npm run test -- --reporter=dot"`
- `bash -lc "cd frontend && npm run build"`
- `bash -lc "cd frontend && npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx --reporter=dot"`
  - Targeted subtitle preview and config coverage.

## Helper Scripts

- `python scripts/test_subtitle_styles.py [PROJECT_DIR]`
  - Generates or burns subtitle outputs against a real project transcript.
- `python scripts/reburn_clip.py --project ID --clip NAME [--layout split] [--style HORMOZI]`
  - Fast CLI path for reburn checks.
- `python scripts/benchmark_render_stability.py --project ID --clip NAME [--runs 3 --samples 5]`
  - Determinism ve throughput benchmark'ı üretir; raporu `workspace/logs/render_benchmarks/` altına yazar.

## Debug Artifacts

- `DEBUG_RENDER_ARTIFACTS=1`
  - Render sırasında proje içine `debug/<clip_stem>/` bundle'ı yazar ve clip metadata altında `render_metadata.debug_artifacts` alanını doldurur.
