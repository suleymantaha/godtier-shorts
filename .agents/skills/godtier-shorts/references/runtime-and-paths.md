# Runtime and Paths

This repo has strict runtime validation and a canonical workspace layout.

## Workspace and Paths

`backend/config.py` is the path source of truth.

- `workspace/downloads`
- `workspace/temp`
- `workspace/outputs`
- `workspace/metadata`
- `workspace/logs`
- `workspace/projects/<project_id>/`

`ProjectPaths` expects:

- `master.mp4`
- `master.wav`
- `transcript.json`
- `viral.json`
- `shorts/`

## Path Safety

- Always route project names through `sanitize_project_name()`.
- Always route clip names through `sanitize_clip_name()` when handling user input.
- Use `get_project_path()` or `ProjectPaths` instead of hand-building project paths.

## Runtime Validation

`backend/runtime_validation.py` enforces:

- positive integer limits for ports and scheduler settings
- `REQUEST_BODY_HARD_LIMIT_BYTES >= UPLOAD_MAX_FILE_SIZE`
- absolute `http(s)` URLs for `FRONTEND_URL`, `PUBLIC_APP_URL`, and `POSTIZ_API_BASE_URL`
- comma-separated `CORS_ORIGINS` values must all be valid origins

## App Startup Coupling

`backend/api/server.py` runs runtime, auth, and social validation at startup. Changes to env handling should be tested against startup behavior, not only helper functions.

## Useful Checks

- `python scripts/check_runtime_config.py`
- `pytest backend/tests/test_runtime_validation.py -q`
- `pytest backend/tests/test_api_security.py -q`
