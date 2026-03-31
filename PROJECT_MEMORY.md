# Project Memory

This file is the canonical handoff memory for AI work in this repository.

Last Updated: 2026-03-30

## Current Objective

- Switch the machine-local auth setup from temporary static tokens to the real Clerk flow.

## Current State

- The canonical AI instruction set lives under `.agents/`.
- Python 3.13.12 is installed at `C:\Users\baba\AppData\Local\Programs\Python\Python313\python.exe`.
- Node.js 22.22.2 is installed under the local WinGet package directory and frontend dependencies are installed.
- Repo-local `.venv` exists and backend dependencies from `requirements.txt` are installed into it.
- Root `.env` now uses Clerk issuer/audience/JWT-template settings for local development.
- `frontend/.env.local` now uses the real Clerk publishable key plus the `godtier-backend` JWT template.
- Backend compatibility package `backend/models/schemas.py` now exists again and exposes the request schemas expected by the route modules and tests.
- The temporary frontend static-dev auth fallback has been removed; the app now expects Clerk again.
- Backend is responding on `http://127.0.0.1:8000/docs`.
- Frontend dev server is responding on `http://127.0.0.1:5173`.

## Decisions In Force

- `PROJECT_MEMORY.md` remains the single canonical progress-memory file for ongoing AI work.
- `.agents` instructions must stay workspace-relative and must not hardcode machine-specific Linux paths.
- On Windows hosts without `bash`, `.agents/references/commands.md` is the source of truth for PowerShell verification fallbacks.
- Canonical rule files live under `.agents/rules/`; `.cursor/rules/` should mirror them when compatibility updates are needed.
- Local auth on this machine should use Clerk JWTs with template `godtier-backend` and audience `godtier-shorts-api`.

## Open Work / Next Steps

1. Sign into the frontend once and verify browser-issued Clerk JWTs contain `aud=godtier-shorts-api` and non-empty `roles`.
2. Remove or rotate any Clerk secrets that were exposed during setup discussion.
3. If `.cursor/` should stay behaviorally identical to `.agents/`, mirror the same Windows-focused guidance there as a follow-up.

## Validation Status

- Passed: `& .\.venv\Scripts\python.exe scripts\check_runtime_config.py`
- Passed: `& .\.venv\Scripts\python.exe -m pytest backend\tests\test_job_request.py -q`
- Passed: `& .\.venv\Scripts\python.exe -m pytest backend\tests\test_runtime_validation.py -q`
- Passed: frontend build via Node 22 `npm run build`
- Passed: `& .\.venv\Scripts\python.exe -c "from backend.api.server import create_app; create_app(); print('app factory ok')"`
- Passed: `Invoke-WebRequest http://127.0.0.1:8000/docs`
- Passed: `Invoke-WebRequest http://127.0.0.1:5173`
- Partial blocker: `scripts/check_toolchain.py` still fails on this shell because its internal subprocess lookup for `npm` does not see the WinGet-installed Node path unless the session PATH is explicitly amended.
- Pending manual validation: a real browser login is still required to confirm Clerk token issuance and `/api/auth/whoami` over JWT.

## Key References

- `.agents/SKILL.md`
- `.agents/rules/godtier-shorts-exit-protocol.mdc`
- `.agents/rules/godtier-shorts.mdc`
- `.agents/rules/godtier-shorts-docs.mdc`
- `.agents/rules/godtier-shorts-progress.mdc`
- `.agents/rules/godtier-shorts-testing.mdc`
- `.cursor/rules/godtier-shorts-progress.mdc`
- `docs/operations/ai-session-exit-protocol.md`

## Session Log

### 2026-03-29

- Removed the temporary static bearer token env settings from `.env` and `frontend/.env.local`.
- Removed the temporary frontend static-dev auth fallback from the codebase and restored mandatory ClerkProvider usage.
- Configured local Clerk envs around issuer `https://helping-jawfish-35.clerk.accounts.dev`, audience `godtier-shorts-api`, and JWT template `godtier-backend`.
- Verified runtime config, frontend production build, and backend app factory creation after the Clerk switch.
- Installed Python 3.13.12 via WinGet and created the repo-local `.venv`.
- Installed Node.js 22.22.2 via WinGet and installed frontend dependencies with the explicit WinGet Node path on `PATH`.
- Added root `.env` and `frontend/.env.local` for local static-token development on `localhost`.
- Recreated `backend.models.schemas` with the request models expected by backend routes/tests.
- Added a narrow frontend static-dev auth fallback so the app can run without Clerk on this machine when `VITE_API_KEY` is set.
- Verified backend auth locally through `/api/auth/whoami` using the static bearer token.
- Verified backend docs at `http://127.0.0.1:8000/docs` and frontend dev server at `http://127.0.0.1:5173`.
- Updated `.agents/settings.json` to use a workspace-relative Windows virtualenv interpreter path and a PowerShell default terminal profile.
- Updated `.agents/agents/openai.yaml` to remove the hardcoded Linux repo path and to reference Windows/PowerShell-safe verification guidance.
- Updated `.agents/references/commands.md` with Windows shell notes plus PowerShell fallback commands for repo validation, frontend checks, and helper scripts.
- Updated `.agents/references/api-contracts.md` and `.agents/references/subtitle-style-parity.md` with PowerShell frontend test equivalents.
- Updated `.agents/rules/godtier-shorts.mdc`, `.agents/rules/godtier-shorts-testing.mdc`, and `.agents/rules/godtier-shorts-exit-protocol.mdc` so they no longer assume `bash` is available.
- Verified by inspection that `.agents` no longer contains the old `/home/arch/godtier-shorts` or `.conda/bin/python` hardcoded paths.

### 2026-03-21

- Added `.agents/rules/godtier-shorts-exit-protocol.mdc` to combine memory, test, and documentation closeout into one checklist.
- Added `docs/operations/ai-session-exit-protocol.md` as the human-readable version of the closeout flow.
- Updated `docs/README.md` to link the new protocol doc.
- Updated `.agents/rules/godtier-shorts.mdc` to require the combined exit protocol.
- Added `.agents/rules/godtier-shorts-docs.mdc` to make relevant documentation updates mandatory.
- Updated `.agents/rules/godtier-shorts.mdc` to point the main rule at the documentation policy.
- Added `.agents/rules/godtier-shorts-testing.mdc` to make relevant verification mandatory after code changes.
- Updated `.agents/rules/godtier-shorts.mdc` to point the main rule at the mandatory test policy.
- Updated `.agents/rules/godtier-shorts.mdc` so the main always-on rule explicitly reads and updates `PROJECT_MEMORY.md`.
- Added `.agents/rules/godtier-shorts-progress.mdc` to require persistent progress tracking.
- Created `PROJECT_MEMORY.md` as the canonical AI handoff file.
- Created `.cursor/rules/godtier-shorts-progress.mdc` as the compatibility mirror for the new rule.
