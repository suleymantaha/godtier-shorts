# Repo Deep Scan Report (2026-03-17)

## Scope
- Backend Python files: **116**
- Frontend source files (ts/tsx): **126**
- Total scanned code files: **242**

## Core Runtime Entry Points
- `backend/main.py` -> creates FastAPI app via `backend.api.server.create_app`
- `backend/api/server.py` -> mounts routes, websocket, startup validation, scheduler lifecycle
- `backend/core/orchestrator.py` -> facade that dispatches to workflow modules
- `frontend/src/main.tsx` -> React bootstrap + ClerkProvider
- `frontend/src/App.tsx` -> auth-gated shell + page controller routing

## Backend Layering (Observed)
- API layer: `backend/api/routes/*` (request validation, auth policy checks, queue orchestration).
- Core workflow layer: `backend/core/workflows_*`, `workflow_helpers`, `workflow_runtime`, `media_ops`.
- Service layer: `backend/services/*` (subtitle, transcription, video processing, viral analysis, social).
- Contracts/types: `backend/models/schemas.py`, `backend/core/render_contracts.py`.

## Route -> Orchestrator Method Usage (Static)
- `backend/api/routes/editor.py` -> `GodTierShortsCreator.cleanup_gpu()`
- `backend/api/routes/editor.py` -> `GodTierShortsCreator.reburn_subtitles_async()`
- `backend/api/routes/editor.py` -> `GodTierShortsCreator.run_batch_manual_clips()`
- `backend/api/routes/editor.py` -> `GodTierShortsCreator.run_batch_manual_clips_async()`
- `backend/api/routes/editor.py` -> `GodTierShortsCreator.run_manual_clip_async()`
- `backend/api/routes/editor.py` -> `GodTierShortsCreator.run_manual_clips_from_cut_points_async()`
- `backend/api/routes/jobs.py` -> `GodTierShortsCreator.cleanup_gpu()`
- `backend/api/routes/jobs.py` -> `GodTierShortsCreator.run_pipeline_async()`

## Most Referenced Backend Files
- `backend/config.py` referenced by **42** internal files
- `backend/services/ownership.py` referenced by **20** internal files
- `backend/api/routes/__init__.py` referenced by **14** internal files
- `backend/core/exceptions.py` referenced by **12** internal files
- `backend/api/security.py` referenced by **12** internal files
- `backend/api/websocket.py` referenced by **12** internal files
- `backend/services/subtitle_styles.py` referenced by **12** internal files
- `backend/api/error_handlers.py` referenced by **12** internal files
- `backend/core/render_contracts.py` referenced by **9** internal files
- `backend/core/media_ops.py` referenced by **8** internal files
- `backend/services/video_processor.py` referenced by **8** internal files
- `backend/models/schemas.py` referenced by **7** internal files
- `backend/services/subtitle_renderer.py` referenced by **7** internal files
- `backend/core/render_quality.py` referenced by **7** internal files
- `backend/core/workflow_helpers.py` referenced by **6** internal files
- `backend/services/transcription.py` referenced by **5** internal files
- `backend/services/social/store.py` referenced by **5** internal files
- `backend/core/workflow_runtime.py` referenced by **5** internal files
- `backend/core/workflow_context.py` referenced by **5** internal files
- `backend/core/log_sanitizer.py` referenced by **4** internal files

## Most Referenced Frontend Files
- `frontend/src/types/index.ts` imported by **36** internal files
- `frontend/src/config/subtitleStyles.ts` imported by **20** internal files
- `frontend/src/api/client.ts` imported by **16** internal files
- `frontend/src/config.ts` imported by **10** internal files
- `frontend/src/store/useJobStore.ts` imported by **10** internal files
- `frontend/src/auth/runtime.ts` imported by **9** internal files
- `frontend/src/auth/session.ts` imported by **9** internal files
- `frontend/src/api/errors.ts` imported by **8** internal files
- `frontend/src/components/ui/protectedMedia.ts` imported by **7** internal files
- `frontend/src/components/ui/Select.tsx` imported by **6** internal files
- `frontend/src/auth/useResilientAuth.ts` imported by **5** internal files
- `frontend/src/utils/storage.ts` imported by **5** internal files
- `frontend/src/app/helpers.ts` imported by **4** internal files
- `frontend/src/components/ui/IconButton.tsx` imported by **4** internal files
- `frontend/src/utils/subtitleTiming.ts` imported by **4** internal files
- `frontend/src/utils/time.ts` imported by **4** internal files
- `frontend/src/components/RangeSlider.tsx` imported by **4** internal files
- `frontend/src/components/TimeRangeHeader.tsx` imported by **4** internal files
- `frontend/src/components/ui/VideoControls.tsx` imported by **4** internal files
- `frontend/src/utils/url.ts` imported by **4** internal files

## Risk Hotspots by Coupling
- High coupling detected around orchestrator/workflow helper modules and subtitle style config maps.
- Changes to `backend/core/workflow_helpers.py`, `backend/core/workflow_runtime.py`, `backend/services/subtitle_renderer.py`, `frontend/src/config/subtitleStyles.ts` likely have broad blast radius.

## End-to-End Runtime Chains
- `POST /api/start-job` -> `jobs.run_gpu_job` -> `GodTierShortsCreator.run_pipeline_async` -> `PipelineWorkflow.run` -> `workflow_helpers.render_pipeline_segments` -> subtitle/video services.
- `POST /api/manual-cut-upload` -> `editor.manual_cut_upload` -> (`run_manual_clip_async` or `run_manual_clips_from_cut_points_async` or `run_batch_manual_clips_async`) -> `ManualClipWorkflow` / `CutPointsWorkflow` / `BatchClipWorkflow`.
- `POST /api/reburn` -> `editor.reburn_clip` -> `GodTierShortsCreator.reburn_subtitles_async` -> `ReburnWorkflow.run` -> `SubtitleRenderer.generate_ass_file` + `burn_subtitles_to_video`.
- `GET /api/styles` -> `StyleManager.list_presets` + `StyleManager.list_animation_options` (frontend subtitle selector contract).

## Documentation and Coverage Gaps (Scan Output)
- Backend Python files without module docstring: **54 / 116**.
- Backend non-test files with zero detected inbound reference: **8**.
- Frontend non-test source files with zero detected inbound import: **6**.
- Potential stale/orphan candidates (manual review required):
- Backend: `backend/core/exception_handlers.py`, `backend/core/render_benchmark.py`, `backend/api/schemas.py`.
- Frontend: `frontend/src/components/SubtitleEditor.tsx`, `frontend/src/components/ThreeCanvas.tsx`, `frontend/src/hooks/useWebSocket.helpers.ts`.
- Note: `__init__.py` and helper/test-only files may intentionally appear as “unused” in static import scans.

## Recommendations for Next Scan Iteration
- Add/standardize module-level docstrings for API route files and service entry modules.
- Add a lightweight dependency check in CI to flag newly orphaned modules.
- Keep subtitle backend/frontend parity contract tests synchronized whenever preset/motion mappings change.
- Track critical chain smoke tests per endpoint (`start-job`, `manual-cut-upload`, `reburn`) in CI to detect contract drift early.

## Detailed File Catalog
- Full per-file catalog: `docs/analysis/repo-deep-scan-2026-03-17-appendix.md`
- Visual diagrams: `docs/analysis/repo-deep-scan-2026-03-17-diagrams.md`
