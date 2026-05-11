from __future__ import annotations

import os
from pathlib import Path

from backend.core.runtime_env import load_runtime_env


def test_runtime_env_prefers_dotenv_for_render_critical_settings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "YOLO_MODEL_PATH=yolo11x.pt",
                "LAYOUT_SAFETY_MODE=enforce",
                "ACTIVE_SPEAKER_MIN_MOTION_SCORE=0.42",
                "API_PORT=9000",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("YOLO_MODEL_PATH", "yolo11s.pt")
    monkeypatch.setenv("LAYOUT_SAFETY_MODE", "shadow")
    monkeypatch.setenv("ACTIVE_SPEAKER_MIN_MOTION_SCORE", "0.99")
    monkeypatch.setenv("API_PORT", "8000")

    applied = load_runtime_env(dotenv_path=dotenv_path)

    assert applied == {
        "ACTIVE_SPEAKER_MIN_MOTION_SCORE": "0.42",
        "LAYOUT_SAFETY_MODE": "enforce",
        "YOLO_MODEL_PATH": "yolo11x.pt",
    }
    assert os.environ["YOLO_MODEL_PATH"] == "yolo11x.pt"
    assert os.environ["LAYOUT_SAFETY_MODE"] == "enforce"
    assert os.environ["ACTIVE_SPEAKER_MIN_MOTION_SCORE"] == "0.42"
    assert os.environ["API_PORT"] == "8000"
    assert applied.get("API_PORT") is None
