"""Explicit full-source composition contracts and real media regression."""
from __future__ import annotations

import subprocess
import threading

import numpy as np
import pytest

from backend.core.external_tools import ffmpeg
from backend.core.media_ops import cut_and_burn_clip
from backend.core.render_quality import extract_media_stream_metrics, probe_media
from backend.core.workflow_runtime import create_subtitle_renderer, resolve_subtitle_render_plan
from backend.models.schemas import JobRequest, ManualJobRequest
from backend.services.video_processor import VideoProcessor


def test_fit_is_explicit_and_skips_subject_detection(monkeypatch):
    processor = VideoProcessor(device="cpu")
    monkeypatch.setattr(processor, "_ensure_model_loaded", lambda: pytest.fail("fit must not load YOLO"))
    assert ManualJobRequest(start_time=0, end_time=12, layout="fit").layout == "fit"
    assert JobRequest(layout="fit").layout == "fit"
    assert ManualJobRequest(start_time=0, end_time=12).layout == "auto"
    plan = resolve_subtitle_render_plan(video_processor=processor, source_video="unused",
        start_t=0, end_t=12, requested_layout="fit", cut_as_short=True)
    assert plan.resolved_layout == "fit"
    assert (plan.canvas_width, plan.canvas_height) == (1080, 1920)
    assert not plan.layout_auto_fix_applied
    opening = processor.analyze_opening_shot(input_video="unused", start_time=0, end_time=12, resolved_layout="fit")
    assert opening["suggested_start_time"] == 0
    assert opening["layout_validation_status"] == "source_preserved"
    renderer = create_subtitle_renderer("MINIMALIST", layout="fit")
    assert renderer is not None


@pytest.mark.integration
def test_fit_real_media_preserves_frame_audio_duration_and_subtitle_path(tmp_path, monkeypatch):
    processor = VideoProcessor(device="cpu")
    monkeypatch.setattr(processor, "_ensure_model_loaded", lambda: pytest.fail("fit must not track"))
    source = tmp_path / "source.mp4"
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=320x180:rate=30:duration=2", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=48000:duration=2", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    ass = tmp_path / "caption.ass"
    transcript = tmp_path / "transcript.json"
    transcript.write_text('[{"start":0,"end":1,"text":"FULL SOURCE","words":[{"word":"FULL","start":0,"end":0.5},{"word":"SOURCE","start":0.5,"end":1}]}]')
    renderer = create_subtitle_renderer("MINIMALIST", layout="fit")
    renderer.generate_ass_file(str(transcript), str(ass))
    output = tmp_path / "output.mp4"
    report = cut_and_burn_clip(video_processor=processor, cancel_event=threading.Event(),
        master_video=str(source), start_t=0.2, end_t=1.4, temp_cropped=str(tmp_path / "raw.mp4"),
        final_output=str(output), ass_file=str(ass), subtitle_engine=renderer, layout="fit",
        center_x=None, cut_as_short=True, require_audio=True)
    metrics = extract_media_stream_metrics(probe_media(str(output)))
    video = next(s for s in probe_media(str(output))["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert metrics["video_duration"] == pytest.approx(1.2, abs=0.04)
    assert metrics["has_audio"]
    assert report["debug_timing"]["merged_output_drift_ms"] <= 150
    assert report["tracking_quality"]["mode"] == "source_preserved"
    assert "subtitle_layout_quality" in report
    raw = output.with_name("output_raw.mp4")
    decoded = subprocess.run([ffmpeg(), "-v", "error", "-i", str(raw), "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    frame = np.frombuffer(decoded, np.uint8).reshape(1920, 1080, 3)
    assert frame[:650].mean() < 1
    assert frame[1270:].mean() < 1
    reference = subprocess.run([ffmpeg(), "-v", "error", "-ss", "0.2", "-i", str(source),
        "-frames:v", "1", "-vf", "scale=1080:608", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    expected = np.frombuffer(reference, np.uint8).reshape(608, 1080, 3)
    assert np.abs(frame[656:1264].astype(float) - expected).mean() < 12
    burned = subprocess.run([ffmpeg(), "-v", "error", "-ss", "0.5", "-i", str(output), "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    burned_frame = np.frombuffer(burned, np.uint8).reshape(1920, 1080, 3)
    assert np.count_nonzero(burned_frame[1300:].max(axis=2) > 30) > 500
    audio_args = ["-t", "1.2", "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"]
    reference_audio = np.frombuffer(subprocess.run([ffmpeg(), "-v", "error", "-ss", "0.2", "-i", str(source),
        *audio_args], check=True, capture_output=True).stdout, dtype="<f4")
    output_audio = np.frombuffer(subprocess.run([ffmpeg(), "-v", "error", "-i", str(output),
        *audio_args], check=True, capture_output=True).stdout, dtype="<f4")
    count = min(len(reference_audio), len(output_audio))
    assert np.corrcoef(reference_audio[:count], output_audio[:count])[0, 1] > 0.99



@pytest.mark.integration
@pytest.mark.parametrize("sar,content_height", [(1, 608), (2, 304)])
def test_fit_filter_on_production_ffmpeg_image(sar, content_height):
    import os
    from backend.services.video_processor import SOURCE_FIT_FILTER
    image = os.environ.get("GODTIER_TEST_GPU_IMAGE")
    if not image:
        pytest.skip("Set GODTIER_TEST_GPU_IMAGE to exercise the production FFmpeg image")
    result = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "ffmpeg", image,
        "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=1:duration=1",
        "-vf", f"setsar={sar},{SOURCE_FIT_FILTER}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=30)
    frame = np.frombuffer(result.stdout, np.uint8).reshape(1920, 1080, 3)
    top = (1920 - content_height) // 2
    assert frame[:top].max() == 0
    assert frame[top:top + content_height].mean() > 20
    assert frame[top + content_height:].max() == 0

def test_paid_fit_reaches_distributed_admission_with_real_pricing(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4
    from backend.api.routes import production_jobs
    from backend.db.models import Plan, SourceType, SubscriptionStatus

    user_id, project_id, submitted_id = uuid4(), uuid4(), uuid4()
    plan = Plan(code="creator", name="Creator", monthly_price_minor=9900, currency="TRY",
        monthly_compute_credits=1000, max_source_minutes_per_job=60, max_clips_per_job=10,
        max_active_jobs=2, retention_days=30, priority=0, active=True)
    project = SimpleNamespace(duration_seconds=600, source_type=SourceType.UPLOAD)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[project, uuid4(), None, None]),
        execute=AsyncMock(return_value=SimpleNamespace(first=lambda: (
            SimpleNamespace(status=SubscriptionStatus.ACTIVE, entitlement_grace_until=None), plan))))
    submit = AsyncMock(return_value=production_jobs.SubmittedJob(submitted_id))
    monkeypatch.setattr(production_jobs, "DistributedJobService", lambda *args: SimpleNamespace(submit=submit))
    payload = production_jobs.ProductionStartJobRequest(project_id=project_id, num_clips=3, layout="fit")
    result = asyncio.run(production_jobs.ProductionJobGateway(session, SimpleNamespace()).start(
        user_id=user_id, project_id=project_id, payload=payload, idempotency_key="fit-admission"))
    assert result.id == submitted_id
    kwargs = submit.call_args.kwargs
    assert kwargs["request"]["layout"] == "fit"
    assert kwargs["estimated_credits"] == 45
    assert kwargs["user_id"] == user_id
