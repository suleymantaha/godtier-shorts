"""Real FFmpeg cut acceptance cases; no model download or tracking required."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from backend.core.external_tools import ffmpeg, ffprobe
from backend.core.render_quality import extract_media_stream_metrics, probe_media
from backend.services.video_processor import VideoProcessor


def _run(*args: str) -> bytes:
    return subprocess.run(args, check=True, capture_output=True, timeout=30).stdout


@pytest.fixture(scope="module")
def media_sources(tmp_path_factory):
    directory = tmp_path_factory.mktemp("cut_media")
    for name in ("cfr", "silent", "vfr", "long_audio"):
        duration = "2" if name == "long_audio" else "4"
        command = [ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                   f"testsrc2=size=160x90:rate=30:duration={duration}"]
        if name != "silent":
            command += ["-f", "lavfi", "-i", "aevalsrc=sin(2*PI*(220*t+30*t*t)):s=48000:d=4"]
        if name == "vfr":
            command += ["-vf", "select='if(lt(t,2),not(mod(n,2)),1)'", "-fps_mode", "vfr"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(directory / f"{name}.mp4")]
        _run(*command)
    return directory


@pytest.mark.integration
@pytest.mark.parametrize("name,start,end", [
    ("cfr", 0.43, 1.63), ("cfr", 3.57, 4.0),
    ("silent", 0.0, 1.0), ("vfr", 1.43, 3.63),
])
def test_real_cut_preserves_window_frames_and_audio(media_sources, tmp_path, name, start, end):
    source = str(media_sources / f"{name}.mp4")
    output = str(tmp_path / "cut.mp4")
    processor = VideoProcessor(device="cpu")
    report = processor.cut_segment_only(source, start, end, output)
    metrics = extract_media_stream_metrics(probe_media(output))
    frame_period = 1 / metrics["fps"]
    assert abs(metrics["video_duration"] - (end - start)) <= frame_period + 0.01
    assert metrics["has_audio"] == (name != "silent")
    assert report["debug_timing"]["merged_output_drift_ms"] <= 150
    frames = _run(ffmpeg(), "-v", "error", "-i", output, "-f", "rawvideo", "-pix_fmt", "rgb24", "-")
    decoded = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 90, 160, 3)
    assert len(decoded) > 0
    assert min(decoded.mean(axis=(1, 2, 3))) > 20  # No empty/black head or tail.
    reference = _run(ffmpeg(), "-v", "error", "-ss", str(start), "-i", source,
                     "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-")
    expected = np.frombuffer(reference, dtype=np.uint8).reshape(90, 160, 3)
    assert np.abs(decoded[0].astype(float) - expected).mean() < 12
    if metrics["has_audio"]:
        audio_args = ["-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"]
        expected_audio = np.frombuffer(_run(ffmpeg(), "-v", "error", "-ss", str(start), "-i", source,
                                           "-t", str(end - start), *audio_args), dtype="<f4")
        actual_audio = np.frombuffer(_run(ffmpeg(), "-v", "error", "-i", output, *audio_args), dtype="<f4")
        samples = min(len(expected_audio), len(actual_audio), 9600)
        assert np.corrcoef(expected_audio[:samples], actual_audio[:samples])[0, 1] > 0.97
    details = json.loads(_run(ffprobe(), "-v", "error", "-show_streams", "-of", "json", output))
    assert next(s for s in details["streams"] if s["codec_type"] == "video")["codec_name"] == "h264"


@pytest.mark.integration
def test_long_audio_does_not_extend_cuttable_video_window(media_sources, tmp_path):
    with pytest.raises(ValueError, match="source duration"):
        VideoProcessor(device="cpu").cut_segment_only(
            str(media_sources / "long_audio.mp4"), 3.0, 3.08, str(tmp_path / "empty.mp4"),
        )
    assert not (tmp_path / "empty.mp4").exists()


@pytest.mark.integration
def test_subframe_eof_cut_cannot_publish_audio_only_file(media_sources, tmp_path):
    output = tmp_path / "existing.mp4"
    output.write_bytes(b"old output")
    with pytest.raises(RuntimeError, match="no video frames"):
        VideoProcessor(device="cpu").cut_segment_only(
            str(media_sources / "cfr.mp4"), 3.99, 4.02, str(output),
        )
    assert output.read_bytes() == b"old output"
    assert list(tmp_path.iterdir()) == [output]


def test_cancelled_cut_preserves_existing_output(monkeypatch, tmp_path):
    import backend.services.video_processor as video_processor

    output = tmp_path / "existing.mp4"
    output.write_bytes(b"old output")
    processor = VideoProcessor(device="cpu")
    monkeypatch.setattr(video_processor, "probe_media", lambda _: {"format": {"duration": "4"}})

    def cancelled(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial")
        raise RuntimeError("Job cancelled by user")

    monkeypatch.setattr(processor, "_run_command_with_cancel", cancelled)
    with pytest.raises(RuntimeError, match="cancelled"):
        processor.cut_segment_only("source.mp4", 0, 1, str(output))
    assert output.read_bytes() == b"old output"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.integration
def test_real_nvenc_failure_retries_cpu_encode(media_sources, tmp_path, monkeypatch):
    processor = VideoProcessor(device="cpu")
    real_run = processor._run_command_with_cancel
    encoders = []

    def unavailable_gpu(command, **kwargs):
        encoder = command[command.index("-c:v") + 1]
        encoders.append(encoder)
        if encoder == "h264_nvenc":
            command = [*command[:-1], "-gpu", "99", command[-1]]
        return real_run(command, **kwargs)

    monkeypatch.setattr(processor, "_run_command_with_cancel", unavailable_gpu)
    output = tmp_path / "fallback.mp4"
    processor.cut_segment_only(str(media_sources / "cfr.mp4"), 0.5, 1.5, str(output))
    assert encoders == ["h264_nvenc", "libx264"]
    assert extract_media_stream_metrics(probe_media(str(output)))["video_duration"] == pytest.approx(1.0)
