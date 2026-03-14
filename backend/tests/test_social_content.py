from pathlib import Path
import json

import pytest

from backend.services.social.content import build_platform_prefill, extract_hashtags, resolve_viral_metadata


def test_extract_hashtags_deduplicates_and_normalizes():
    text = "Hello #Viral #viral #Trend #Türkiye"
    tags = extract_hashtags(text)
    assert tags == ["Viral", "Trend", "Türkiye"]


def test_build_platform_prefill_applies_x_limit():
    viral = {
        "ui_title": "Başlık",
        "hook_text": "HOOK",
        "social_caption": "Bu bir test metni " + "x" * 320 + " #a #b #c #d #e #f",
        "viral_score": 80,
    }

    payload = build_platform_prefill(viral)
    assert len(payload["x"]["text"]) <= 280
    assert len(payload["x"]["hashtags"]) == 5


def test_resolve_viral_metadata_falls_back_to_viral_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    project_root = tmp_path / "projects"
    project_dir = project_root / "proj_x"
    project_dir.mkdir(parents=True, exist_ok=True)

    viral_json = {
        "segments": [
            {
                "start_time": 0,
                "end_time": 10,
                "ui_title": "İlk Segment",
                "hook_text": "HOOK1",
                "social_caption": "Caption 1 #one",
                "viral_score": 70,
            },
            {
                "start_time": 10,
                "end_time": 20,
                "ui_title": "İkinci Segment",
                "hook_text": "HOOK2",
                "social_caption": "Caption 2 #two",
                "viral_score": 90,
            },
        ]
    }
    (project_dir / "viral.json").write_text(json.dumps(viral_json), encoding="utf-8")

    clip_meta = {
        "transcript": [],
        "viral_metadata": None,
        "render_metadata": {
            "start_time": 11,
            "end_time": 19,
        },
    }

    monkeypatch.setattr("backend.config.PROJECTS_DIR", project_root)
    resolved = resolve_viral_metadata("proj_x", "short_1_test.mp4", clip_meta)

    assert resolved is not None
    assert resolved["ui_title"] == "İkinci Segment"
