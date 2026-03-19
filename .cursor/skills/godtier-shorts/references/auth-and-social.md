# Auth and Social Constraints

Auth, WebSocket progress, and social publishing are coupled through startup validation and shared contracts.

## Startup Validation

`backend/api/server.py` validates all of these during app startup:

- `validate_runtime_configuration()`
- `validate_auth_configuration()`
- `validate_social_security_configuration()`

If one fails, the app should not boot.

## HTTP Auth Contract

- Protected routes use `require_policy(...)`.
- Static bearer tokens come from `API_BEARER_TOKENS`.
- Clerk-based auth requires `CLERK_ISSUER_URL` and `CLERK_AUDIENCE`.
- Keep error payload shape consistent with existing auth tests.
- Account purge route lives in `backend/api/routes/account.py` and is subject-scoped.
- Account deletion must only purge the caller's projects, jobs, websocket connections, grants, and social rows.

## WebSocket Contract

- Progress socket path: `/ws/progress`
- Backend accepts bearer auth through the WebSocket subprotocol header first.
- Backend falls back to `?token=` query auth if no subprotocol token is present.
- Frontend helper `frontend/src/hooks/useWebSocket.helpers.ts` currently sends `['bearer', token]`.
- Connection manager isolates broadcasts by subject; auth changes must preserve per-subject visibility.
- In tests, prefer the direct ASGI websocket harness in `backend/tests/test_websocket_auth.py`; `CompatTestClient` intentionally does not implement websocket support.

## Social Publishing Constraints

- Social credentials rely on `SOCIAL_ENCRYPTION_SECRET`.
- Startup should fail when social encryption requirements are missing.
- Social route and service changes usually touch `backend/api/routes/social.py` and `backend/services/social/`.
- Social account normalization and publish targets are subject-scoped; do not leak cross-subject credentials or jobs.
- Signed social export tokens are validated in `backend/services/social/service.py`; token shape and signature checks are part of the contract.

## Checks

- `pytest backend/tests/test_api_security.py -q`
- `pytest backend/tests/test_websocket_auth.py -q`
- `pytest backend/tests/test_social_crypto.py -q`
- `pytest backend/tests/test_social_routes.py -q`
- `pytest backend/tests/test_account_deletion_api.py -q`
- `pytest backend/tests/test_subject_purge.py -q`
