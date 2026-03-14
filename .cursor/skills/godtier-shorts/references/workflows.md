# Workflow Map

Prefer existing route, orchestrator, and workspace conventions over inventing new paths.

## Primary Entry Points

- `POST /api/start-job`
  - Route module: `backend/api/routes/jobs.py`
  - Orchestrator call: `GodTierShortsCreator.run_pipeline()`
  - Workflow: `PipelineWorkflow`
- `POST /api/upload`
  - Route module: `backend/api/routes/clips.py`
  - Key helpers: `prepare_uploaded_project()`, `ensure_project_transcript()`
- `POST /api/manual-cut-upload`
  - Route module: `backend/api/routes/editor.py`
  - Uses upload preparation, transcript generation, then manual or cut-point workflows.
- `POST /api/process-manual`
  - Route module: `backend/api/routes/editor.py`
  - Orchestrator call: `run_manual_clip_async()`
- `POST /api/process-batch`
  - Route module: `backend/api/routes/editor.py`
  - Orchestrator call: `run_batch_manual_clips_async()`
- `POST /api/reburn`
  - Route module: `backend/api/routes/editor.py`
  - Workflow: `ReburnWorkflow`

## Orchestrator Structure

- Keep `backend/core/orchestrator.py` as the external facade.
- Put workflow-specific logic in `backend/core/workflows_pipeline.py`, `workflows_manual.py`, `workflows_batch.py`, and `workflows_reburn.py`.
- Keep shared media operations in `backend/core/media_ops.py` when logic is reused across workflows.

## Workspace Layout

- Project root: `workspace/projects/<project_id>/`
- Common files:
  - `transcript.json`
  - master video path resolved from `ProjectPaths`
  - `shorts/*.mp4`
  - `shorts/*.json`
- Existing scripts and routes assume this layout. Change it only with a coordinated migration.

## Useful Docs

- `docs/flows/` and `docs/operations/` describe end-user flow variants.
- `docs/architecture/` describes service boundaries and canonical modules.
