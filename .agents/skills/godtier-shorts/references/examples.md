# Example Tasks

## Add a Subtitle Style

- Start from `backend/services/subtitle_styles.py` and `frontend/src/config/subtitleStyles.ts`.
- Keep the preset key identical across backend and frontend if the style should be selectable in the UI.
- Update preview and style tests in the same change.

## Debug Manual Cut or Reburn

- Start from `backend/api/routes/editor.py`.
- Follow the handoff into `backend/core/orchestrator.py` and the relevant workflow module.
- Use `scripts/reburn_clip.py` when a CLI repro is faster than the UI.
- If the issue is timing, crop stability, or subtitle mismatch, enable `DEBUG_RENDER_ARTIFACTS=1` and inspect the per-clip debug bundle.

## Debug Progress WebSocket or Auth

- Start from `backend/api/server.py`, `backend/api/websocket.py`, and `frontend/src/hooks/useWebSocket.helpers.ts`.
- Check both bearer subprotocol auth and query-token fallback behavior.

## Adjust Social Publishing

- Start from `backend/api/routes/social.py` and `backend/services/social/`.
- Keep `SOCIAL_ENCRYPTION_SECRET` requirements and startup validation intact.

## Refactor Workflow Code

- Preserve thin facade modules and existing public exports.
- Run guardrail tests before broad refactors.
- Keep compatibility aliases if tests or external callers still patch workflow module symbols directly.
