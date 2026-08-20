# Production Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-safe API runtime contract for PostgreSQL, Redis, private Cloudflare R2, iyzico, and Turnstile while preserving the existing local application behavior.

**Architecture:** Keep the existing `backend/config.py` constants and `backend/runtime_validation.py` startup validation pattern. Production mode adds fail-fast environment validation, while development remains permissive. The production Compose stack runs a CPU control-plane API from a GPU-free dependency manifest plus PostgreSQL and Redis; local mode retains the existing GPU routes. R2, iyzico, and Turnstile stay external and enter only through server-side environment values.

**Tech Stack:** Python 3.13, FastAPI, pytest, SQLAlchemy 2 asyncio, asyncpg, Redis/ARQ, boto3, httpx, Docker Compose, PostgreSQL, Cloudflare R2, iyzico, Cloudflare Turnstile.

**Spec:** `docs/superpowers/plans/2026-08-20-godtier-shorts-production-v1.md`

## Global Constraints

- Existing local behavior must remain available with `APP_ENV=development` and `WORKER_MODE=local` defaults.
- Production startup must fail before serving requests when a required runtime value is missing or malformed.
- R2 credentials, iyzico keys, Turnstile secret, database credentials, and Redis credentials must never be committed with real values.
- PostgreSQL is the future durable source of truth; Redis is dispatch and coordination only.
- The API process must not instantiate YOLO, Whisper, or GPU worker objects during startup.
- R2 remains private and is represented by an S3 endpoint, bucket, access key, and secret key.
- iyzico integration reuses the existing `httpx` client dependency; no card or CVV handling is introduced.

---

### Task 1: Runtime environment contract

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/runtime_validation.py`
- Modify: `backend/tests/test_runtime_validation.py`

**Interfaces:**
- Consumes: process environment variables.
- Produces: `APP_ENV`, `WORKER_MODE`, and `validate_runtime_configuration()` production fail-fast behavior.

- [x] **Step 1: Write failing tests for safe defaults and production requirements**

Add tests proving that absent `APP_ENV`/`WORKER_MODE` preserve development/local behavior, invalid enum values are rejected, production API mode rejects each missing required variable, and a complete literal test environment validates. Required production API variables are `DATABASE_URL`, `REDIS_URL`, `R2_ENDPOINT_URL`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `IYZICO_API_BASE_URL`, `IYZICO_API_KEY`, `IYZICO_SECRET_KEY`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CLERK_ISSUER_URL`, `CLERK_AUDIENCE`, `FRONTEND_URL`, and `SOCIAL_ENCRYPTION_SECRET`.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest backend/tests/test_runtime_validation.py -v`

Expected: the new production tests fail because the production contract is not implemented.

- [x] **Step 3: Implement the minimal runtime contract**

Add normalized `APP_ENV` and `WORKER_MODE` values to `backend/config.py`. Extend `validate_runtime_configuration()` with exact enum validation, PostgreSQL/Redis URL scheme checks, HTTPS-only external production endpoint checks, and a single error listing missing variable names without printing their values.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest backend/tests/test_runtime_validation.py -v`

Expected: all runtime validation tests pass.

### Task 2: Observable API health without GPU initialization

**Files:**
- Create: `backend/api/routes/health.py`
- Modify: `backend/api/routes/__init__.py`
- Modify: `backend/api/server.py`
- Create: `backend/tests/test_health_routes.py`

**Interfaces:**
- Consumes: FastAPI application lifecycle state.
- Produces: unauthenticated `GET /health/live` and `GET /health/ready` endpoints.

- [x] **Step 1: Write failing endpoint tests**

Test the real app with controlled authentication/social environment. Assert `/health/live` returns `200 {"status": "live"}` and `/health/ready` returns `200 {"status": "ready"}` only while startup has completed. Patch the GPU constructor symbol to raise if instantiated so application startup proves it does not create GPU work.

- [x] **Step 2: Run the health tests and verify RED**

Run: `python -m pytest backend/tests/test_health_routes.py -v`

Expected: `404` for the missing health routes.

- [x] **Step 3: Add minimal health routes and lifecycle state**

Register a small router outside `/api`, set `app.state.ready = True` only after startup validation and scheduler initialization, and clear it during shutdown. Liveness must not touch PostgreSQL, Redis, R2, iyzico, Turnstile, Torch, or YOLO.

- [x] **Step 4: Run health and existing startup tests**

Run: `python -m pytest backend/tests/test_health_routes.py backend/tests/test_runtime_validation.py backend/tests/test_route_imports_smoke.py -v`

Expected: all selected tests pass.

### Task 3: Dependency and production Compose foundation

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-api.txt`
- Modify: `.env.example`
- Create: `Dockerfile.api`
- Create: `compose.production.yml`
- Modify: `backend/tests/test_dependency_manifest.py`
- Create: `backend/tests/test_production_compose.py`

**Interfaces:**
- Consumes: Docker Compose environment interpolation and Python dependency imports.
- Produces: reproducible CPU API image contract and healthy `api`, `postgres`, and `redis` service graph.

- [x] **Step 1: Write failing behavior tests**

Extend the dependency manifest test with production modules imported by later tasks: `sqlalchemy`, `alembic`, `asyncpg`, `redis`, `arq`, and `boto3`. Add a Compose test that executes `docker compose --env-file .env.example -f compose.production.yml config` and asserts successful resolution, private internal database/Redis services, no GPU reservation on the API service, and an API healthcheck targeting `/health/ready`.

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest backend/tests/test_dependency_manifest.py backend/tests/test_production_compose.py -v`

Expected: failure because dependencies and Compose files are absent.

- [x] **Step 3: Add the minimal production artifacts**

Add bounded compatible requirements for SQLAlchemy asyncio, Alembic, asyncpg, redis, ARQ, and boto3; retain `httpx` for iyzico. Keep a separate `requirements-api.txt` without Torch, OpenCV, Ultralytics, CTranslate2, or faster-whisper. Document placeholders in `.env.example`. Build `Dockerfile.api` from Python 3.13 slim, run as a non-root user, set `WORKER_MODE=api`, expose port 8000, and healthcheck `/health/ready`. Compose PostgreSQL and Redis with healthchecks and persistent PostgreSQL storage; pass all external provider values only through environment interpolation.

- [x] **Step 4: Run focused tests and Compose validation**

Run: `python -m pytest backend/tests/test_dependency_manifest.py backend/tests/test_production_compose.py -v`

Run: `docker compose --env-file .env.example -f compose.production.yml config --quiet`

Expected: tests pass and Compose exits zero without printing secret values.

### Task 4: Regression verification and scoped commit

**Files:**
- Verify only; no new production behavior.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: evidence that local behavior and the new production contract coexist.

- [x] **Step 1: Run formatting and whitespace checks**

Run: `git diff --check`

- [x] **Step 2: Run the complete non-integration backend suite**

Run: `python -m pytest backend/tests -m "not integration" -v`

Observed baseline limitation: the suite passes except for the two pre-existing assertions in `backend/tests/test_toolchain_contract.py` that require the absent `.github/workflows/verify.yml`. The scoped green run excludes only that file and reports 384 passed, 1 skipped, 1 deselected.

- [x] **Step 3: Validate the Docker build when Docker is available**

Run: `docker build -f Dockerfile.api -t godtier-shorts-api:task1 .`

Run: `docker compose --env-file .env.example -f compose.production.yml config --quiet`

- [x] **Step 4: Review the exact diff and secret exposure**

Run: `git status --short`

Run: `git diff -- .env.example requirements.txt backend/config.py backend/runtime_validation.py backend/api/server.py backend/api/routes/health.py backend/tests Dockerfile.api compose.production.yml`

Run: `git diff --cached --check`

- [x] **Step 5: Commit the scoped implementation**

Stage the production skill, master plan, Task 1 plan, implementation, and tests. Commit with `chore: add production runtime foundation` only after all available verification gates pass; if Docker is unavailable, report that limitation instead of claiming a Docker build passed.
