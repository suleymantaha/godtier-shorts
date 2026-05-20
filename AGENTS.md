## Learned User Preferences
- Respond in Turkish and keep answers terse unless depth is needed.
- Use MCP-backed tools for browser, auth, and library workflows when available, especially for Playwright and Clerk style integrations.
- Before starting or restarting the app, confirm required environment and config values are in place without exposing secret values; start backend and frontend together unless asked otherwise.
- Actively monitor long-running downloads, render jobs, transcription, and backend restarts; report concrete status from logs or process state.
- For bugs, diagnose likely causes with evidence before fixing; the user values root-cause clarity over quick guesses.
- Treat video output quality as production-critical: anticipate varied real-world scenarios and avoid artifacts that could harm brand trust.
- Auto-cut and speaker framing should preserve semantic and visual continuity across segment boundaries; manual/cut-points flows should keep parity with pipeline safeguards (boundary snap, opening-shot validation).

## Learned Workspace Facts
- Godtier Shorts is a short-video generation workspace with a Python backend and frontend app.
- The render pipeline includes 9:16 portrait output, YOLO/person tracking, active speaker framing, subtitle placement, and split/stacked handling for multi-person scenes.
- Whisper and transcription assets are part of the video workflow; GPU acceleration for transcription, tracking, and NVENC encode is expected—unexpected CPU fallback during render is a regression to investigate.
- Clerk authentication integration is used or being added; keep auth keys in environment/config only and do not repeat secret values.
- Environment configuration is managed through `.env`, `.env.example`, and `backend/config.py`; never record real secret values in memory.
- Supported Python runtime is `3.13.x` (see `.python-version`); toolchain checks expect that version.
- YOLO weights are selected via `YOLO_MODEL_PATH` in environment config (default `yolo11x.pt` at repo root).
- Optional pyannote speaker diarization labels transcript segments (`SPEAKER_*`) for active-speaker alignment during render.
- Dialogue handling uses scenario buckets: A clear speech (labels+YOLO), B ambiguous speaker (review/split, avoid hard follow), C non-dialogue scenes (visual tracking without speaker identity claims).
