from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


RENDER_CRITICAL_ENV_KEYS = frozenset(
    {
        "YOLO_MODEL_PATH",
        "LAYOUT_SAFETY_MODE",
        "DEBUG_RENDER_ARTIFACTS",
        "ACTIVE_SPEAKER_MIN_MOTION_SCORE",
        "ACTIVE_SPEAKER_MOTION_MARGIN",
        "ACTIVE_SPEAKER_CONFIRMATION_FRAMES",
        "ACTIVE_SPEAKER_CATCHUP_FRAMES",
        "ACTIVE_SPEAKER_MAX_STEP_RATIO",
        "ACTIVE_SPEAKER_EMA_ALPHA",
    }
)


def load_runtime_env(dotenv_path: str | Path = ".env") -> dict[str, str]:
    """Load app env and let local .env own render-critical knobs."""
    path = Path(dotenv_path)
    load_dotenv(dotenv_path=path)

    values = dotenv_values(path) if path.exists() else {}
    applied: dict[str, str] = {}
    for key in sorted(RENDER_CRITICAL_ENV_KEYS):
        value = values.get(key)
        if value is None:
            continue
        os.environ[key] = value
        applied[key] = value
    return applied
