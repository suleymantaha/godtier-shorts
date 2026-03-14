# Subtitle Style Parity

Keep backend subtitle presets and frontend preview behavior aligned.

## Sources of Truth

- Backend preset definitions live in `backend/services/subtitle_styles.py`.
- Frontend selectable names, labels, and preview mapping live in `frontend/src/config/subtitleStyles.ts`.

## Change Checklist

1. Add or update the preset in `StyleManager._PRESETS`.
2. Mirror the exact preset key in `STYLE_OPTIONS` and `STYLE_LABELS` if the style is user-selectable.
3. Update `SUBTITLE_INLINE_STYLES` so the browser preview remains close to backend output.
4. Update any editor or form defaults if the change affects default styles.
5. Update tests in the same patch.

## Tests to Touch

- Backend: `backend/tests/test_subtitle_styles.py`
- Frontend:
  - `frontend/src/test/config/subtitleStyles.test.ts`
  - `frontend/src/test/components/SubtitlePreview.test.tsx`

## Verification

- `pytest backend/tests/test_subtitle_styles.py -q`
- `bash -lc "cd frontend && npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx --reporter=dot"`
- `python scripts/test_subtitle_styles.py [PROJECT_DIR]`

## Notes

- Avoid backend-only preset keys unless the style is intentionally hidden from the UI.
- Keep color conversions consistent with ASS color semantics when changing preview logic.
