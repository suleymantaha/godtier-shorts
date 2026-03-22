from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from backend.core.media_ops import (
    DOWNLOAD_ACTIVITY_TIMEOUT_SECONDS,
    DOWNLOAD_TOTAL_TIMEOUT_SECONDS,
    build_shifted_transcript_segments,
    build_shifted_transcript_segments_with_report,
    download_full_video_async,
    parse_ytdlp_progress_line,
    cut_and_burn_clip,
)


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


def test_build_shifted_transcript_segments_rebuilds_text_from_retained_words() -> None:
    shifted = build_shifted_transcript_segments(
        [
            {
                "text": "alpha beta gamma",
                "start": 8.0,
                "end": 12.0,
                "speaker": "A",
                "words": [
                    {"word": "alpha", "start": 8.0, "end": 9.0, "score": 0.9},
                    {"word": "beta", "start": 9.0, "end": 10.0, "score": 0.9},
                    {"word": "gamma", "start": 10.0, "end": 11.0, "score": 0.9},
                ],
            }
        ],
        start_time=9.0,
        end_time=11.0,
    )

    assert shifted == [
        {
            "text": "beta gamma",
            "start": 0,
            "end": 2.0,
            "speaker": "A",
            "words": [
                {"word": "beta", "start": 0, "end": 1.0, "score": 0.9},
                {"word": "gamma", "start": 1.0, "end": 2.0, "score": 0.9},
            ],
        }
    ]


def test_build_shifted_transcript_segments_preserves_overlapping_segments_without_words() -> None:
    shifted = build_shifted_transcript_segments(
        [
            {
                "text": "kelime zaman damgasi yok",
                "start": 4.0,
                "end": 6.0,
                "speaker": "B",
                "words": [],
            }
        ],
        start_time=5.0,
        end_time=7.0,
    )

    assert shifted == [
        {
            "text": "damgasi yok",
            "start": 0,
            "end": 1.0,
            "speaker": "B",
            "words": [
                {"word": "damgasi", "start": 0.0, "end": 0.5, "score": 1.0},
                {"word": "yok", "start": 0.5, "end": 1.0, "score": 1.0},
            ],
        }
    ]


def test_build_shifted_transcript_segments_with_report_tracks_quality_fields() -> None:
    shifted, report = build_shifted_transcript_segments_with_report(
        [
            {
                "text": "alpha beta gamma",
                "start": 8.0,
                "end": 12.0,
                "speaker": "A",
                "words": [
                    {"word": "alpha", "start": 7.8, "end": 9.0, "score": 0.9},
                    {"word": "beta", "start": 9.0, "end": 10.0, "score": 0.9},
                    {"word": "gamma", "start": 10.0, "end": 11.2, "score": 0.9},
                ],
            }
        ],
        start_time=9.0,
        end_time=11.0,
    )

    assert shifted[0]["text"] == "alpha beta gamma" or shifted[0]["text"] == "beta gamma"
    assert report["clamped_words_count"] >= 1
    assert report["word_coverage_ratio"] > 0
    assert report["status"] in {"good", "partial"}


def test_build_shifted_transcript_segments_with_report_syncs_edited_text_before_shifting() -> None:
    shifted, report = build_shifted_transcript_segments_with_report(
        [
            {
                "text": "hello universe",
                "start": 0.0,
                "end": 2.0,
                "speaker": "A",
                "words": [
                    {"word": "hello", "start": 0.0, "end": 1.0, "score": 0.9},
                    {"word": "world", "start": 1.0, "end": 2.0, "score": 0.9},
                ],
            }
        ],
        start_time=0.0,
        end_time=2.0,
    )

    assert shifted == [
        {
            "text": "hello universe",
            "start": 0,
            "end": 2.0,
            "speaker": "A",
            "words": [
                {"word": "hello", "start": 0.0, "end": 1.0, "score": 0.9},
                {"word": "universe", "start": 1.0, "end": 2.0, "score": 0.9},
            ],
        }
    ]
    assert report["text_word_mismatches"] == 0


def test_parse_ytdlp_progress_line_uses_byte_counts_for_message_and_progress() -> None:
    parsed = parse_ytdlp_progress_line("GTS_DL|1048576|2097152|NA| 50.0%| 1.00MiB/s| 00:03|downloading")

    assert parsed == (
        "YouTube indiriliyor: 1.0 MiB / 2.0 MiB (50.0%, 1.00MiB/s, ETA 00:03, downloading)",
        15,
        {
            "phase": "download",
            "downloaded_bytes": 1048576,
            "total_bytes": 2097152,
            "total_bytes_estimate": None,
            "percent": 50.0,
            "speed_text": "1.00MiB/s",
            "eta_text": "00:03",
            "status": "downloading",
        },
    )


def test_download_full_video_async_streams_yt_dlp_progress_and_uses_activity_timeout(tmp_path: Path) -> None:
    statuses: list[tuple[str, int]] = []
    master_video = tmp_path / "master.mp4"
    master_audio = tmp_path / "master.wav"

    class _DummyProjectPaths:
        def __init__(self) -> None:
            self.master_video = master_video
            self.master_audio = master_audio

    class _DummyRunner:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def run_async(self, cmd, *, timeout, error_message, activity_timeout=None, on_output=None):
            self.calls.append(
                {
                    "cmd": cmd,
                    "timeout": timeout,
                    "error_message": error_message,
                    "activity_timeout": activity_timeout,
                }
            )
            if cmd and cmd[0] == "yt-dlp":
                if on_output is not None:
                    on_output("stderr", "GTS_DL|1048576|2097152|NA| 50.0%| 1.00MiB/s| 00:03|downloading")
                master_video.write_bytes(b"video")
                return 0, "", ""
            master_audio.write_bytes(b"audio")
            return 0, "", ""

    runner = _DummyRunner()

    video_file, audio_file = asyncio.run(
        download_full_video_async(
            url="https://youtube.com/watch?v=test1234567A",
            project_paths=_DummyProjectPaths(),
            resolution="best",
            validate_url=lambda _url: None,
            update_status=lambda message, progress, extra=None: statuses.append((message, progress, extra)),
            command_runner=runner,
        )
    )

    assert video_file == str(master_video)
    assert audio_file == str(master_audio)
    assert statuses[0] == ("YouTube'dan orijinal video indiriliyor...", 10, None)
    assert statuses[1] == (
        "YouTube indiriliyor: 1.0 MiB / 2.0 MiB (50.0%, 1.00MiB/s, ETA 00:03, downloading)",
        15,
        {
            "download_progress": {
                "phase": "download",
                "downloaded_bytes": 1048576,
                "total_bytes": 2097152,
                "total_bytes_estimate": None,
                "percent": 50.0,
                "speed_text": "1.00MiB/s",
                "eta_text": "00:03",
                "status": "downloading",
            },
            "status": "processing",
        },
    )
    assert statuses[2] == ("Video içinden ses ayrıştırılıyor...", 20, None)
    assert runner.calls[0]["cmd"][:3] == ["yt-dlp", "--newline", "--progress-template"]
    assert runner.calls[0]["timeout"] == DOWNLOAD_TOTAL_TIMEOUT_SECONDS
    assert runner.calls[0]["activity_timeout"] == DOWNLOAD_ACTIVITY_TIMEOUT_SECONDS
