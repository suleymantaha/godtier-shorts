"""Exercise subtitle safe margins through FFmpeg/libass, including animation peaks."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.core.external_tools import ffmpeg as resolve_ffmpeg
from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.subtitle_styles import StyleManager


def _render_frames(tmp_path: Path, *, layout: str, words: list[str]) -> bytes:
    executable = resolve_ffmpeg()
    if not shutil.which(executable):
        pytest.skip("FFmpeg is required for the libass pixel regression")
    filters = subprocess.run(
        [executable, "-hide_banner", "-filters"], capture_output=True, check=True,
    )
    if b"subtitles" not in filters.stdout:
        pytest.skip("FFmpeg subtitles/libass filter is required")

    transcript = tmp_path / "transcript.json"
    transcript.write_text(json.dumps([{
        "text": " ".join(words), "start": 0.0, "end": 1.0,
        "words": [
            {"word": word, "start": index / len(words), "end": (index + 1) / len(words)}
            for index, word in enumerate(words)
        ],
    }]), encoding="utf-8")
    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"), layout=layout)
    renderer.generate_ass_file(str(transcript), str(tmp_path / "subtitle.ass"))
    # Render all frames across the pop's growth, peak, and settled size. Using a
    # relative ASS path also avoids platform-specific drive/colon filter escaping.
    rendered = subprocess.run([
        executable, "-v", "error", "-f", "lavfi", "-i",
        "color=c=black:s=1080x1920:r=20:d=1", "-vf", "subtitles=subtitle.ass",
        "-an", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ], cwd=tmp_path, capture_output=True, check=True, timeout=30)
    assert len(rendered.stdout) == 1080 * 1920 * 20
    return rendered.stdout


@pytest.mark.integration
@pytest.mark.parametrize("layout", ["split", "single"])
def test_long_turkish_word_stays_inside_frame_at_animation_peak(
    tmp_path: Path, layout: str,
) -> None:
    frames = _render_frames(tmp_path, layout=layout, words=["Döndüremiyorum"])
    frame_bytes = 1080 * 1920
    visible_frames = 0
    for offset in range(0, len(frames), frame_bytes):
        frame = frames[offset:offset + frame_bytes]
        # Black source is zero; a threshold excludes nearly transparent fade
        # edges while retaining antialiased white/yellow subtitle glyphs.
        columns = [index % 1080 for index, value in enumerate(frame) if value > 32]
        if not columns:
            continue
        visible_frames += 1
        assert min(columns) >= 86, f"left glyph edge {min(columns)} at frame {offset // frame_bytes}"
        assert max(columns) < 994, f"right glyph edge {max(columns)} at frame {offset // frame_bytes}"
    assert visible_frames >= 5, "Expected visible subtitles across the animation"


@pytest.mark.integration
@pytest.mark.parametrize("words", [["insanların", "nasıl"], ["Merhaba"]])
def test_split_subtitles_stay_inside_vertical_gutter_at_each_word_peak(
    tmp_path: Path, words: list[str],
) -> None:
    frames = _render_frames(tmp_path, layout="split", words=words)
    if len(words) == 2:
        assert r"\N" in (tmp_path / "subtitle.ass").read_text(encoding="utf-8")
    frame_bytes = 1080 * 1920
    visible_frames = 0
    largest_height = 0
    for offset in range(0, len(frames), frame_bytes):
        frame = frames[offset:offset + frame_bytes]
        rows = [index // 1080 for index, value in enumerate(frame) if value > 32]
        if not rows:
            continue
        visible_frames += 1
        largest_height = max(largest_height, max(rows) - min(rows) + 1)
        assert min(rows) >= 864, f"top glyph edge {min(rows)} at frame {offset // frame_bytes}"
        assert max(rows) < 1056, f"bottom glyph edge {max(rows)} at frame {offset // frame_bytes}"
    assert visible_frames >= 15
    if len(words) == 1:
        assert largest_height >= 70, "One-line subtitles must retain their readable size"
