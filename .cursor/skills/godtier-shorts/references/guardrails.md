# Guardrails

Use these contracts to avoid refactors that pass locally but break repo conventions.

## Workflow Decomposition

`backend/tests/test_workflows_refactor_guardrails.py` enforces:

- `backend/core/workflows.py` stays at or below 50 lines.
- `workflows_pipeline.py` stays at or below 300 lines.
- `workflows_manual.py` stays at or below 220 lines.
- `workflows_batch.py` stays at or below 220 lines.
- `workflows_reburn.py` stays at or below 150 lines.
- `backend.core.workflows.__all__` keeps the expected public exports.

Keep small compatibility aliases in workflow modules when tests or stable callers monkeypatch module-level symbols directly.

## Orchestrator Facade

`backend/tests/test_orchestrator_refactor_guardrails.py` enforces:

- `backend/core/orchestrator.py` stays at or below 350 lines.
- These async facade methods stay present and short:
  - `run_pipeline_async`
  - `run_manual_clip_async`
  - `run_manual_clips_from_cut_points_async`
  - `run_batch_manual_clips_async`
  - `reburn_subtitles_async`

## Legacy Import Guard

`python scripts/check_orphan_legacy.py` fails if:

- A top-level `subtitle_renderer.py` reappears.
- Any Python file imports `subtitle_renderer` through the legacy top-level path.

Always import `backend.services.subtitle_renderer`.

## Import Smoke

`backend/tests/test_route_imports_smoke.py` verifies that route modules and `create_app()` still import cleanly with lightweight stubs.

## Test Harness Stability

- `backend/tests/compat_testclient.py` is the repo-compatible HTTP client for local test stability.
- `backend/tests/conftest.py` patches thread-offload helpers inline during tests to avoid local deadlocks.
- WebSocket tests intentionally use a direct ASGI harness instead of `TestClient`.
