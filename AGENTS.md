## Learned User Preferences
- Respond in Turkish and keep answers terse unless depth is needed.
- Use MCP-backed tools for browser, auth, and library workflows when available, especially for Playwright and Clerk style integrations.
- Before starting or restarting the app, confirm required environment and config values are in place without exposing secret values.
- Actively monitor long-running downloads, render jobs, transcription, and backend restarts; report concrete status from logs or process state.
- For bugs, diagnose likely causes with evidence before fixing; the user values root-cause clarity over quick guesses.
- Treat video output quality as production-critical: anticipate varied real-world scenarios and avoid artifacts that could harm brand trust.

## Learned Workspace Facts
- Godtier Shorts is a short-video generation workspace with a Python backend and frontend app.
- The render pipeline includes 9:16 portrait output, YOLO/person tracking, active speaker framing, subtitle placement, and split/stacked handling for multi-person scenes.
- Whisper and transcription assets are part of the video workflow, and GPU acceleration is important for acceptable processing time.
- Clerk authentication integration is used or being added; keep auth keys in environment/config only and do not repeat secret values.
- Environment configuration is managed through `.env`, `.env.example`, and `backend/config.py`; never record real secret values in memory.
