---
name: godtier-shorts
description: Repository-grounded workflow for the God-Tier Shorts app. Use when working in this repo on the FastAPI backend, React/Vite frontend, subtitle styles, transcription, viral segment selection, manual or batch clip generation, reburn flows, auth or WebSocket behavior, social publishing, workspace project files, or repo verification scripts.
---

# GodTier Shorts

Use this skill to stay aligned with the repo's existing workflows, file layout, and refactor guardrails.

## Start Here

- Read `README.md` first for the pipeline, runtime expectations, and directory layout.
- Prefer these canonical entry points:
  - API app: `backend/api/server.py`
  - Orchestrator facade: `backend/core/orchestrator.py`
  - Workflow modules: `backend/core/workflows_*.py`
  - Shared workflow helpers: `backend/core/workflow_helpers.py`
  - Render quality helpers: `backend/core/render_quality.py`
  - Subtitle timing logic: `backend/core/subtitle_timing.py`
  - Subtitle renderer: `backend/services/subtitle_renderer.py`
  - Subtitle presets: `backend/services/subtitle_styles.py`
  - Frontend subtitle config: `frontend/src/config/subtitleStyles.ts`
  - Frontend subtitle timing parity: `frontend/src/utils/subtitleTiming.ts`
- Assume the pinned toolchain: Python `3.13`, Node `22`, npm `10`.

## Workflow

1. Identify the surface area before editing: workflow, subtitle style, frontend parity, auth/WebSocket, social publishing, runtime config, or workspace project files.
2. Read the matching reference file from `references/`.
3. Preserve backend/frontend parity for shared names, payloads, message shapes, and subtitle timing behavior.
4. Run the smallest relevant checks first, then run broader verification before finishing.
5. Report any checks you could not run.

## Read These References

- `references/examples.md`: quick examples of common repo tasks.
- `references/commands.md`: canonical commands and what each check covers.
- `references/workflows.md`: API endpoints, orchestrator handoff, and project file layout.
- `references/api-contracts.md`: shared backend and frontend payload contracts.
- `references/runtime-and-paths.md`: workspace paths, sanitization helpers, and env validation rules.
- `references/subtitle-style-parity.md`: rules for subtitle preset and preview parity.
- `references/auth-and-social.md`: auth, WebSocket, startup, and social publishing constraints.
- `references/guardrails.md`: refactor budgets, export contracts, and legacy import guardrails.

## Repo-Specific Rules

- Treat `backend.services.subtitle_renderer` as the only valid subtitle renderer import path.
- If you add or rename a user-visible subtitle preset, update backend presets, frontend style maps, and relevant tests in the same change.
- Keep WebSocket auth compatible with both bearer subprotocol auth and the `?token=` fallback unless the task explicitly changes that contract.
- Keep static bearer token auth, Clerk validation, and social encryption startup checks aligned when touching auth or startup code.
- Preserve `workspace/projects/<project_id>/` layout and existing output conventions unless the task is an intentional migration.
- Clip quality fields live under clip-level `render_metadata`; keep `/api/clips` and `Clip` list payloads lightweight.
- Debug bundles live under `workspace/projects/<project_id>/debug/<clip_stem>/` and are gated by `DEBUG_RENDER_ARTIFACTS=1`.
- Preserve additive metadata semantics: omit unknown/unmeasured fields instead of writing `null` for new quality/debug keys.
- Prefer existing scripts in `scripts/` over one-off commands for reburn, subtitle checks, toolchain validation, and full verification.
- Use `scripts/benchmark_render_stability.py` when debugging determinism, throughput, or render reproducibility.
- Do not collapse workflow modules back into monolithic files; preserve facade and export boundaries.
- Keep compatibility aliases if tests or external callers monkeypatch workflow-module symbols directly.

## Deliverables

- Cite the docs, scripts, or tests used to guide the change.
- Call out missing environment prerequisites if they block verification.
