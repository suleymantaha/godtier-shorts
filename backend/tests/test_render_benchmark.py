from __future__ import annotations

import runpy
import sys
from pathlib import Path

from backend.core import render_benchmark


def test_select_sample_times_spreads_across_duration() -> None:
    assert render_benchmark.select_sample_times(10.0, sample_count=5) == [1.667, 3.333, 5.0, 6.667, 8.333]


def test_compare_benchmark_runs_detects_matching_payloads() -> None:
    comparison = render_benchmark.compare_benchmark_runs(
        [
            {"frame_hashes": {"1.000": "abc"}, "normalized_metadata": {"render_quality_score": 90}},
            {"frame_hashes": {"1.000": "abc"}, "normalized_metadata": {"render_quality_score": 90}},
        ]
    )

    assert comparison == {
        "deterministic": True,
        "frame_hash_matches": True,
        "metadata_matches": True,
    }


def test_run_benchmark_writes_report_and_cleans_outputs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(render_benchmark, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(render_benchmark, "TEMP_DIR", tmp_path / "temp")
    render_benchmark.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    render_benchmark.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(render_benchmark, "read_peak_rss_mb", lambda: 12.5)

    created_outputs: list[Path] = []

    def fake_render_existing_clip_to_temp_output(*, output_path: str, **_: object) -> dict:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
        created_outputs.append(path)
        return {
            "output_path": output_path,
            "render_metadata": {
                "start_time": 0.0,
                "end_time": 10.0,
                "render_quality_score": 91,
                "debug_environment": {"ffmpeg_version": "test"},
                "debug_timing": {"normalized_fps": 30.0},
            },
        }

    monkeypatch.setattr(render_benchmark, "render_existing_clip_to_temp_output", fake_render_existing_clip_to_temp_output)
    monkeypatch.setattr(
        render_benchmark,
        "compute_video_frame_hashes",
        lambda video_path, sample_times: {f"{sample:.3f}": f"hash:{Path(video_path).name}" for sample in sample_times},
    )

    report = render_benchmark.run_benchmark(project_id="proj_1", clip_name="clip_1.mp4", run_count=2, sample_count=3)

    assert report["deterministic"] is False
    assert report["frame_hash_matches"] is False
    assert report["metadata_matches"] is True
    assert Path(report["report_path"]).exists()
    assert all(not output.exists() for output in created_outputs)


def test_benchmark_script_smoke(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "render_benchmark.json"

    def fake_run_benchmark(*, project_id: str, clip_name: str, run_count: int, sample_count: int, keep_outputs: bool) -> dict:
        assert project_id == "proj_1"
        assert clip_name == "clip_1.mp4"
        assert run_count == 3
        assert sample_count == 5
        assert keep_outputs is False
        report_path.write_text("{}", encoding="utf-8")
        return {
            "deterministic": True,
            "report_path": str(report_path),
        }

    monkeypatch.setattr(render_benchmark, "run_benchmark", fake_run_benchmark)
    monkeypatch.setattr(sys, "argv", ["benchmark_render_stability.py", "--project", "proj_1", "--clip", "clip_1.mp4"])

    try:
        runpy.run_path(str(Path("scripts/benchmark_render_stability.py").resolve()), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0

    assert report_path.exists()
