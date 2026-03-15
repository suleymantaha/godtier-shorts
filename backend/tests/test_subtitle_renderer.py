from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.subtitle_styles import StyleManager


def _write_transcript(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_generate_ass_file_escapes_ass_control_chars(tmp_path: Path) -> None:
    transcript = [
        {
            "text": r"{boom} slash\word",
            "start": 0.0,
            "end": 1.0,
            "words": [
                {"word": r"{boom}", "start": 0.0, "end": 0.5},
                {"word": r"slash\word", "start": 0.5, "end": 1.0},
            ],
        }
    ]
    transcript_path = _write_transcript(tmp_path / "transcript.json", transcript)
    output_path = tmp_path / "out.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert r"\{" in content
    assert r"\}" in content
    assert r"slash\\word" in content


def test_generate_ass_file_prefers_real_word_timestamps_when_segment_text_mismatches(tmp_path: Path) -> None:
    transcript = [
        {
            "text": "hello world",
            "start": 0.0,
            "end": 1.0,
            "words": [
                {"word": "hello", "start": 0.0, "end": 0.4},
                {"word": "planet", "start": 0.4, "end": 1.0},
            ],
        }
    ]
    transcript_path = _write_transcript(tmp_path / "mismatch.json", transcript)
    output_path = tmp_path / "mismatch.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert "planet" in content
    assert "world" not in content


def test_generate_ass_file_uses_split_safe_area_header(tmp_path: Path) -> None:
    transcript_path = _write_transcript(
        tmp_path / "split.json",
        [{"text": "hello there", "start": 0.0, "end": 1.0, "words": [{"word": "hello", "start": 0.0, "end": 0.5}, {"word": "there", "start": 0.5, "end": 1.0}]}],
    )
    output_path = tmp_path / "split.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("TIKTOK"), layout="split")
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert ",8,86,86,888,1" in content


def test_generate_ass_file_clamps_word_animation_to_word_duration(tmp_path: Path) -> None:
    transcript = [
        {
            "text": "go",
            "start": 0.0,
            "end": 0.05,
            "words": [{"word": "go", "start": 0.0, "end": 0.05}],
        }
    ]
    transcript_path = _write_transcript(tmp_path / "short.json", transcript)
    output_path = tmp_path / "short.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert r"\t(0,25," in content
    assert r"\t(25,50," in content
    assert r"\t(25,100," not in content


def test_generate_ass_file_records_chunk_metrics_and_overflow_status(tmp_path: Path) -> None:
    transcript = [
        {
            "text": "supercalifragilisticexpialidocious antidisestablishmentarianism pneumonoultramicroscopicsilicovolcanoconiosis",
            "start": 0.0,
            "end": 2.4,
            "words": [
                {"word": "supercalifragilisticexpialidocious", "start": 0.0, "end": 0.8},
                {"word": "antidisestablishmentarianism", "start": 0.8, "end": 1.6},
                {"word": "pneumonoultramicroscopicsilicovolcanoconiosis", "start": 1.6, "end": 2.4},
            ],
        }
    ]
    transcript_path = _write_transcript(tmp_path / "overflow.json", transcript)
    output_path = tmp_path / "overflow.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    assert renderer.last_render_report["chunk_count"] >= 1
    assert renderer.last_render_report["avg_words_per_chunk"] > 0
    assert "subtitle_overflow_detected" in renderer.last_render_report


def test_generate_ass_file_rejects_non_list_json(tmp_path: Path) -> None:
    transcript_path = _write_transcript(tmp_path / "bad.json", {"text": "not-a-list"})
    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))

    with pytest.raises(ValueError, match="Transcript JSON"):
        renderer.generate_ass_file(str(transcript_path), str(tmp_path / "bad.ass"))


def test_burn_subtitles_to_video_escapes_filter_path(monkeypatch, tmp_path: Path) -> None:
    observed: dict[str, object] = {}
    ass_path = tmp_path / "sub's,1.ass"
    ass_path.write_text("dummy", encoding="utf-8")

    def fake_run(cmd: list[str], *, timeout: float, cancel_event=None):
        observed["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    monkeypatch.setattr(renderer, "_run_command_with_cancel", fake_run)

    renderer.burn_subtitles_to_video("input.mp4", str(ass_path), str(tmp_path / "out.mp4"))

    filter_arg = observed["cmd"][7]  # type: ignore[index]
    assert filter_arg.startswith("ass='")
    assert r"\'" in filter_arg
    assert r"\," in filter_arg
