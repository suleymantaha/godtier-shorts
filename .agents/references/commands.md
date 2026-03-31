# Commands

Use the smallest command set that proves the change.

## Windows Shell Notes

- This machine uses PowerShell and may not have `bash`, `python`, `py`, `node`, or `npm` on `PATH` yet.
- Prefer PowerShell-native commands from the repo root when bash is unavailable.
- If `.venv` exists, use `.\.venv\Scripts\python.exe`; otherwise install or activate the repo's expected Python/Node toolchain before running verification.

## Full Verification

- `bash scripts/verify.sh`
  - Runs toolchain validation, runtime config validation, frontend lint, frontend tests, backend pytest, and frontend build.
- `& .\.venv\Scripts\python.exe scripts\check_toolchain.py`
- `& .\.venv\Scripts\python.exe scripts\check_runtime_config.py`
- `Set-Location frontend; npm run lint; npm run test -- --reporter=dot; npm run build; Set-Location ..`
- `& .\.venv\Scripts\python.exe -m pytest backend/tests -q`
  - PowerShell fallback when `bash` is unavailable.

## Repo Contracts

- `python scripts/check_toolchain.py`
  - Verifies pinned Python, Node, npm, and config alignment with CI.
- `& .\.venv\Scripts\python.exe scripts\check_toolchain.py`
  - PowerShell fallback using the repo-local virtual environment.
- `python scripts/check_runtime_config.py`
  - Verifies `.env`-driven runtime settings and hard limits.
- `& .\.venv\Scripts\python.exe scripts\check_runtime_config.py`
- `python scripts/check_orphan_legacy.py`
  - Blocks legacy `subtitle_renderer.py` entrypoints and imports.
- `& .\.venv\Scripts\python.exe scripts\check_orphan_legacy.py`

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
- `pytest backend/tests/test_subtitle_timing.py -q`
  - Boundary snap, word coverage, and chunk duration rules.
- `pytest backend/tests/test_workflow_helpers.py -q`
  - Debug artifact persistence and helper behavior.
- `pytest backend/tests/test_render_quality.py -q`
  - Render quality score and transcript-quality merge rules.
- `pytest backend/tests/test_render_benchmark.py -q`
  - Determinism benchmark helper and script smoke coverage.
- `pytest backend/tests/test_clip_transcript_routes.py -q`
  - Clip transcript/detail metadata and recovery behavior.

## Frontend

- `bash -lc "cd frontend && npm run lint"`
- `bash -lc "cd frontend && npm run test -- --reporter=dot"`
- `bash -lc "cd frontend && npm run build"`
- `Set-Location frontend; npm run lint; Set-Location ..`
- `Set-Location frontend; npm run test -- --reporter=dot; Set-Location ..`
- `Set-Location frontend; npm run build; Set-Location ..`
- `bash -lc "cd frontend && npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx --reporter=dot"`
  - Targeted subtitle preview and config coverage.
- `Set-Location frontend; npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx --reporter=dot; Set-Location ..`
- `bash -lc "cd frontend && npm run test -- src/test/components/VideoOverlay.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot"`
  - Targeted clip preview parity and quality-summary coverage.
- `Set-Location frontend; npm run test -- src/test/components/VideoOverlay.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot; Set-Location ..`

## Helper Scripts

- `python scripts/test_subtitle_styles.py [PROJECT_DIR]`
- `& .\.venv\Scripts\python.exe scripts\test_subtitle_styles.py [PROJECT_DIR]`
  - Generates or burns subtitle outputs against a real project transcript.
- `python scripts/reburn_clip.py --project ID --clip NAME [--layout split] [--style HORMOZI]`
- `& .\.venv\Scripts\python.exe scripts\reburn_clip.py --project ID --clip NAME [--layout split] [--style HORMOZI]`
  - Fast CLI path for reburn checks.
- `python scripts/benchmark_render_stability.py --project ID --clip NAME [--runs 3 --samples 5]`
- `& .\.venv\Scripts\python.exe scripts\benchmark_render_stability.py --project ID --clip NAME [--runs 3 --samples 5]`
  - Determinism ve throughput benchmark'ı üretir; raporu `workspace/logs/render_benchmarks/` altına yazar.

## Debug Artifacts

- `DEBUG_RENDER_ARTIFACTS=1`
  - Render sırasında proje içine `debug/<clip_stem>/` bundle'ı yazar ve clip metadata altında `render_metadata.debug_artifacts` alanını doldurur.
