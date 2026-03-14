from __future__ import annotations

import threading
from pathlib import Path

from backend.core.media_ops import cut_and_burn_clip


class _DummyVideoProcessor:
    def __init__(self, cropped_bytes: bytes = b"cropped-video") -> None:
        self.cropped_bytes = cropped_bytes
        self.cut_calls = 0
        self.short_calls = 0
        self.cleanup_calls = 0

    def create_viral_short(self, **kwargs) -> None:
        self.short_calls += 1
        Path(kwargs["output_filename"]).write_bytes(self.cropped_bytes)

    def cut_segment_only(self, **kwargs) -> None:
        self.cut_calls += 1
        Path(kwargs["output_filename"]).write_bytes(self.cropped_bytes)

    def cleanup_gpu(self) -> None:
        self.cleanup_calls += 1


class _DummySubtitleEngine:
    def __init__(self, burned_bytes: bytes = b"burned-video") -> None:
        self.burned_bytes = burned_bytes
        self.calls: list[tuple[str, str, str]] = []

    def burn_subtitles_to_video(self, input_video: str, ass_file: str, output_video: str, **_kwargs) -> None:
        self.calls.append((input_video, ass_file, output_video))
        Path(output_video).write_bytes(self.burned_bytes)


def test_cut_and_burn_clip_saves_raw_copy_before_burn(tmp_path: Path) -> None:
    processor = _DummyVideoProcessor(cropped_bytes=b"raw-before-burn")
    subtitle_engine = _DummySubtitleEngine(burned_bytes=b"final-with-subs")
    ass_file = tmp_path / "subs.ass"
    ass_file.write_text("dummy ass", encoding="utf-8")
    final_output = tmp_path / "clip.mp4"

    cut_and_burn_clip(
        video_processor=processor,
        cancel_event=threading.Event(),
        master_video=str(tmp_path / "master.mp4"),
        start_t=0.0,
        end_t=5.0,
        temp_cropped=str(tmp_path / "temp.mp4"),
        final_output=str(final_output),
        ass_file=str(ass_file),
        subtitle_engine=subtitle_engine,
        layout="single",
        center_x=None,
        cut_as_short=False,
    )

    raw_output = tmp_path / "clip_raw.mp4"
    assert processor.cut_calls == 1
    assert subtitle_engine.calls == [(str(tmp_path / "temp.mp4"), str(ass_file), str(final_output))]
    assert raw_output.read_bytes() == b"raw-before-burn"
    assert final_output.read_bytes() == b"final-with-subs"


def test_cut_and_burn_clip_moves_final_output_when_subtitles_are_skipped(tmp_path: Path) -> None:
    processor = _DummyVideoProcessor(cropped_bytes=b"cropped-no-subs")
    final_output = tmp_path / "clip.mp4"

    cut_and_burn_clip(
        video_processor=processor,
        cancel_event=threading.Event(),
        master_video=str(tmp_path / "master.mp4"),
        start_t=0.0,
        end_t=5.0,
        temp_cropped=str(tmp_path / "temp.mp4"),
        final_output=str(final_output),
        ass_file=str(tmp_path / "missing.ass"),
        subtitle_engine=None,
        layout="single",
        center_x=None,
        cut_as_short=False,
    )

    assert processor.cut_calls == 1
    assert final_output.read_bytes() == b"cropped-no-subs"
    assert not (tmp_path / "clip_raw.mp4").exists()
    assert not (tmp_path / "temp.mp4").exists()
