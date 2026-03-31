# API Contracts

Keep backend schemas, frontend types, and API client behavior aligned.

## Backend Sources of Truth

- `backend/models/schemas.py`
  - `JobRequest`
  - `ManualAutoCutRequest`
  - `BatchJobRequest`
  - `ManualJobRequest`
  - `ReburnRequest`
- `backend/api/routes/social.py`
  - social credential, draft, publish, and scheduling payload validators

## Frontend Sources of Truth

- `frontend/src/types/index.ts`
  - request payloads, clip metadata, social types, and WebSocket-facing job types
- `frontend/src/api/client.ts`
  - actual endpoint usage, upload form field names, and JSON request shapes

## Change Checklist

1. If you change a backend request model, update the matching frontend payload type.
2. If you rename or constrain a field, update the API client and relevant UI callers in the same patch.
3. Keep upload form keys aligned with backend form parameter names.
4. Keep social scheduling fields aligned across route validators, frontend types, and client calls.

## High-Risk Fields

- `style_name`
- `project_id`
- `clip_name`
- `resolution`
- `num_clips`
- `scheduled_at`
- `timezone`
- `cut_points`
- `cut_as_short`
- `render_metadata`
- `render_quality_score`

## Render Metadata Notes

- `Clip` ve `/api/clips` listesi kalite alanı taşımaz.
- `ClipTranscriptResponse` clip-level kalite ve debug alanlarının ana taşıyıcısıdır.
- `ProjectTranscriptResponse` proje transcript durumunu taşır; clip kalite alanlarını taşımaz.
- `ClipTranscriptResponse.render_metadata` additive kalite alanları taşıyabilir:
  - `tracking_quality`
  - `transcript_quality`
  - `audio_validation`
  - `subtitle_layout_quality`
  - `debug_timing`
  - `debug_artifacts`
  - `render_quality_score`
- Batch workflow `output_paths` sonucunu `render_quality_score` azalan sırada döndürür; bu liste davranışını değiştirirken frontend galeriyi etkilememeye dikkat et.
- Yeni alanlarda `null` yerine alanın hiç yazılmaması tercih edilir.

## Useful Checks

- `pytest backend/tests/test_job_request.py -q`
- `pytest backend/tests/test_social_routes.py -q`
- `pytest backend/tests/test_jobs_api_serialization.py -q`
- `bash -lc "cd frontend && npm run test -- --reporter=dot"`
- `Set-Location frontend; npm run test -- --reporter=dot; Set-Location ..`
