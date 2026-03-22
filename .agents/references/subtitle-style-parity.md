# Subtitle Style Parity

Keep backend subtitle presets and frontend preview behavior aligned.

## Sources of Truth

- Backend preset definitions live in `backend/services/subtitle_styles.py`.
- Frontend selectable names, labels, and preview mapping live in `frontend/src/config/subtitleStyles.ts`.
- Backend subtitle timing and chunking rules live in `backend/core/subtitle_timing.py`.
- Frontend preview timing parity lives in `frontend/src/utils/subtitleTiming.ts`.

## Change Checklist

1. Add or update the preset in `StyleManager._PRESETS`.
2. Mirror the exact preset key in `STYLE_OPTIONS` and `STYLE_LABELS` if the style is user-selectable.
3. Update `SUBTITLE_INLINE_STYLES` so the browser preview remains close to backend output.
4. Keep preview chunking and active-word timing aligned with backend subtitle timing helpers.
5. Update any editor or form defaults if the change affects default styles.
6. Update tests in the same patch.

## Tests to Touch

- Backend: `backend/tests/test_subtitle_styles.py`
- Backend timing/parity: `backend/tests/test_subtitle_timing.py`
- Backend renderer safety: `backend/tests/test_subtitle_renderer.py`
- Frontend:
  - `frontend/src/test/config/subtitleStyles.test.ts`
  - `frontend/src/test/components/SubtitlePreview.test.tsx`
  - `frontend/src/test/components/VideoOverlay.test.tsx`
  - `frontend/src/test/components/SubtitleEditor.clip.test.tsx`

## Verification

- `pytest backend/tests/test_subtitle_styles.py -q`
- `pytest backend/tests/test_subtitle_timing.py -q`
- `pytest backend/tests/test_subtitle_renderer.py -q`
- `bash -lc "cd frontend && npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx --reporter=dot"`
- `bash -lc "cd frontend && npm run test -- src/test/components/VideoOverlay.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot"`
- `python scripts/test_subtitle_styles.py [PROJECT_DIR]`

## Notes

- Avoid backend-only preset keys unless the style is intentionally hidden from the UI.
- Keep color conversions consistent with ASS color semantics when changing preview logic.
- In v2.1, overflow fallback should prefer re-chunking or conservative line breaks; do not silently swap styles.
- Split layout now uses layout-specific typography and chunk planning in the shared renderer/parity path:
  - split font sizing is more conservative than single
  - split defaults to `max_words=2`
  - split may force a line break before reporting overflow
  - if a split chunk still overflows after rechunking, renderer and preview apply a final long-word font clamp instead of silently degrading
  - frontend preview and overlay should use the same chunk-end and line-break rules as backend ASS generation
