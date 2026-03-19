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
    assert ",8,86,86,900,1" in content


def test_generate_ass_file_split_layout_uses_line_break_before_overflow(tmp_path: Path) -> None:
    transcript_path = _write_transcript(
        tmp_path / "split_break.json",
        [{
            "text": "mekanlarımızda, makamlarımızda",
            "start": 0.0,
            "end": 2.0,
            "words": [
                {"word": "mekanlarımızda,", "start": 0.0, "end": 0.9},
                {"word": "makamlarımızda", "start": 0.95, "end": 1.9},
            ],
        }],
    )
    output_path = tmp_path / "split_break.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"), layout="split")
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert r"\N" in content
    assert renderer.last_render_report["overflow_strategy"] == "split_line_break"
    assert renderer.last_render_report["subtitle_overflow_detected"] is False
    assert renderer.last_render_report["safe_area_violation_count"] == 0


def test_generate_ass_file_split_layout_rechunks_unbreakable_heavy_words(tmp_path: Path) -> None:
    transcript_path = _write_transcript(
        tmp_path / "split_rechunk.json",
        [{
            "text": "pneumonoultramicroscopicsilicovolcanoconiosis antidisestablishmentarianism",
            "start": 0.0,
            "end": 2.0,
            "words": [
                {"word": "pneumonoultramicroscopicsilicovolcanoconiosis", "start": 0.0, "end": 0.9},
                {"word": "antidisestablishmentarianism", "start": 0.95, "end": 1.9},
            ],
        }],
    )
    output_path = tmp_path / "split_rechunk.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"), layout="split")
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    dialogue_lines = [
        line for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert len(dialogue_lines) == 2
    assert renderer.last_render_report["overflow_strategy"] == "split_rechunk_1_word"


def test_generate_ass_file_split_layout_clamps_long_single_word_font(tmp_path: Path) -> None:
    transcript_path = _write_transcript(
        tmp_path / "split_long_word.json",
        [{
            "text": "motivasyonumuzda",
            "start": 0.0,
            "end": 1.4,
            "words": [
                {"word": "motivasyonumuzda", "start": 0.0, "end": 1.4},
            ],
        }],
    )
    output_path = tmp_path / "split_long_word.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"), layout="split")
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert r"\fs" in content
    assert renderer.last_render_report["subtitle_overflow_detected"] is False
    assert renderer.last_render_report["safe_area_violation_count"] == 0
    assert renderer.last_render_report["chunk_dump"][0]["font_scale"] < 1.0


def test_generate_ass_file_single_layout_clamps_long_single_word_font(tmp_path: Path) -> None:
    transcript_path = _write_transcript(
        tmp_path / "single_long_word.json",
        [{
            "text": "motivasyonumuzda",
            "start": 0.0,
            "end": 1.4,
            "words": [
                {"word": "motivasyonumuzda", "start": 0.0, "end": 1.4},
            ],
        }],
    )
    output_path = tmp_path / "single_long_word.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"), layout="single")
    renderer.generate_ass_file(str(transcript_path), str(output_path))

    assert renderer.last_render_report["overflow_strategy"] == "single_font_clamp"
    assert renderer.last_render_report["subtitle_overflow_detected"] is False
    assert renderer.last_render_report["safe_area_violation_count"] == 0
    assert renderer.last_render_report["font_clamp_count"] >= 1
    assert renderer.last_render_report["chunk_dump"][0]["font_scale"] < 1.0


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
    assert renderer.last_render_report["resolved_safe_area_profile"] == "default"


def test_generate_ass_file_does_not_overlap_dialogue_events_for_multi_chunk_segment(tmp_path: Path) -> None:
    transcript = [
        {
            "text": "one two three four five six",
            "start": 0.0,
            "end": 4.0,
            "words": [
                {"word": "one", "start": 0.0, "end": 0.4, "segment_end": 4.0},
                {"word": "two", "start": 0.4, "end": 0.8, "segment_end": 4.0},
                {"word": "three", "start": 0.8, "end": 1.2, "segment_end": 4.0},
                {"word": "four", "start": 1.2, "end": 1.6, "segment_end": 4.0},
                {"word": "five", "start": 1.6, "end": 2.0, "segment_end": 4.0},
                {"word": "six", "start": 2.0, "end": 2.4, "segment_end": 4.0},
            ],
        }
    ]
    transcript_path = _write_transcript(tmp_path / "overlap.json", transcript)
    output_path = tmp_path / "overlap.ass"

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    renderer.generate_ass_file(str(transcript_path), str(output_path), max_words_per_screen=3)

    dialogue_lines = [
        line for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert len(dialogue_lines) >= 2
    assert renderer.last_render_report["simultaneous_event_overlap_count"] == 0
    assert renderer.last_render_report["max_simultaneous_events"] == 1

    previous_end = 0.0
    for line in dialogue_lines:
        parts = line.split(",")
        start_seconds = _parse_ass_time(parts[1])
        end_seconds = _parse_ass_time(parts[2])
        assert start_seconds >= previous_end
        assert end_seconds > start_seconds
        previous_end = end_seconds


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


def test_burn_subtitles_to_video_records_nvenc_fallback_forensics(monkeypatch, tmp_path: Path) -> None:
    ass_path = tmp_path / "subs.ass"
    ass_path.write_text("dummy", encoding="utf-8")
    output_path = tmp_path / "out.mp4"
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *, timeout: float, cancel_event=None):
        calls.append(cmd)
        if len(calls) == 1:
            return subprocess.CompletedProcess(cmd, 1, b"", b"[h264_nvenc] CUDA error: driver mismatch")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    renderer = SubtitleRenderer(
        StyleManager.get_preset("HORMOZI"),
        safe_area_profile="lower_third_safe",
        lower_third_detection={"lower_third_collision_detected": True, "lower_third_band_height_ratio": 0.11},
    )
    monkeypatch.setattr(renderer, "_run_command_with_cancel", fake_run)
    monkeypatch.setattr("backend.services.subtitle_renderer.probe_media", lambda _path: {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "avg_frame_rate": "30/1"}], "format": {"duration": "12.0"}})

    renderer.burn_subtitles_to_video("input.mp4", str(ass_path), str(output_path))

    assert len(calls) == 2
    assert renderer.last_render_report["burn_encoder"] == "libx264"
    assert renderer.last_render_report["nvenc_fallback_used"] is True
    assert renderer.last_render_report["nvenc_failure_reason"] == "cuda_error"
    assert "driver mismatch" in str(renderer.last_render_report["nvenc_failure_stderr_tail"])
    assert renderer.last_render_report["resolved_safe_area_profile"] == "lower_third_safe"
    assert renderer.last_render_report["lower_third_collision_detected"] is True


def test_burn_subtitles_to_video_can_require_nvenc(monkeypatch, tmp_path: Path) -> None:
    ass_path = tmp_path / "subs.ass"
    ass_path.write_text("dummy", encoding="utf-8")

    def fake_run(cmd: list[str], *, timeout: float, cancel_event=None):
        return subprocess.CompletedProcess(cmd, 1, b"", b"[h264_nvenc] CUDA error")

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    monkeypatch.setattr(renderer, "_run_command_with_cancel", fake_run)
    monkeypatch.setenv("REQUIRE_NVENC_FOR_BURN", "1")

    with pytest.raises(RuntimeError, match="NVENC zorunlu"):
        renderer.burn_subtitles_to_video("input.mp4", str(ass_path), str(tmp_path / "out.mp4"))


def _parse_ass_time(value: str) -> float:
    hours_raw, minutes_raw, seconds_raw = value.split(":")
    seconds_int, centiseconds_raw = seconds_raw.split(".")
    return (
        (int(hours_raw) * 3600)
        + (int(minutes_raw) * 60)
        + int(seconds_int)
        + (int(centiseconds_raw) / 100.0)
    )
