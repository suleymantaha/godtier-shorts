"""Exercise the segment cut command against the installed FFmpeg."""

import shutil
import subprocess

import pytest

from backend.services.video_processor import VideoProcessor


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is unavailable")
def test_segment_cut_works_with_current_ffmpeg(tmp_path):
    source = tmp_path / "source.mp4"
    output = tmp_path / "cut.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "testsrc2=s=64x64:r=10:d=0.5", "-c:v", "libx264", str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    processor = VideoProcessor(device="cpu")
    command = processor._build_segment_cut_command(
        input_video=str(source),
        start_time=0.0,
        duration=0.3,
        source_fps=10.0,
        output_filename=str(output),
        has_audio=False,
        prefer_nvenc=False,
    )
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert output.stat().st_size > 0
