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

## WebSocket Contract

- Progress socket path: `/ws/progress`
- Backend accepts bearer auth through the WebSocket subprotocol header first.
- Backend falls back to `?token=` query auth if no subprotocol token is present.
- Frontend helper `frontend/src/hooks/useWebSocket.helpers.ts` currently sends `['bearer', token]`.

## Social Publishing Constraints

- Social credentials rely on `SOCIAL_ENCRYPTION_SECRET`.
- Startup should fail when social encryption requirements are missing.
- Social route and service changes usually touch `backend/api/routes/social.py` and `backend/services/social/`.

## Checks

- `pytest backend/tests/test_api_security.py -q`
- `pytest backend/tests/test_websocket_auth.py -q`
- `pytest backend/tests/test_social_crypto.py -q`
