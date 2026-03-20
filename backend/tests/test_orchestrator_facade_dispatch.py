from __future__ import annotations

import asyncio

from backend.core import orchestrator as orchestrator_module


def _build_creator(monkeypatch) -> orchestrator_module.GodTierShortsCreator:
    class FakeCommandRunner:
        def __init__(self, *args, **kwargs):
            self.cancel_event = kwargs.get("cancel_event")

    class FakeViralAnalyzer:
        def __init__(self, *args, **kwargs):
            self.engine = kwargs.get("engine")

    class FakeVideoProcessor:
        def __init__(self, *args, **kwargs):
            self.model_version = kwargs.get("model_version")
            self.device = kwargs.get("device")

        def cleanup_gpu(self) -> None:
            return None

    monkeypatch.setattr(orchestrator_module, "CommandRunner", FakeCommandRunner)
    monkeypatch.setattr(orchestrator_module, "ViralAnalyzer", FakeViralAnalyzer)
    monkeypatch.setattr(orchestrator_module, "VideoProcessor", FakeVideoProcessor)
    return orchestrator_module.GodTierShortsCreator()


def test_run_pipeline_async_dispatches_to_pipeline_workflow(monkeypatch) -> None:
    creator = _build_creator(monkeypatch)
    observed: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, ctx):
            observed["ctx"] = ctx

        async def run(self, **kwargs):
            observed["kwargs"] = kwargs

    monkeypatch.setattr(orchestrator_module, "PipelineWorkflow", FakeWorkflow)

    asyncio.run(
        creator.run_pipeline_async(
            youtube_url="https://youtu.be/abcdefghijk",
            style_name="TIKTOK",
            animation_type="slide_up",
            layout="double",
            skip_subtitles=True,
            num_clips=3,
            duration_min=15.0,
            duration_max=45.0,
            resolution="720p",
        )
    )

    assert observed["ctx"] is creator
    assert observed["kwargs"] == {
        "youtube_url": "https://youtu.be/abcdefghijk",
        "style_name": "TIKTOK",
        "animation_type": "slide_up",
        "layout": "double",
        "skip_subtitles": True,
        "num_clips": 3,
        "duration_min": 15.0,
        "duration_max": 45.0,
        "resolution": "720p",
    }


def test_run_manual_clip_async_dispatches_to_manual_workflow(monkeypatch) -> None:
    creator = _build_creator(monkeypatch)
    observed: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, ctx):
            observed["ctx"] = ctx

        async def run(self, **kwargs):
            observed["kwargs"] = kwargs
            return "manual.mp4"

    monkeypatch.setattr(orchestrator_module, "ManualClipWorkflow", FakeWorkflow)

    result = asyncio.run(
        creator.run_manual_clip_async(
            start_t=10.0,
            end_t=20.0,
            transcript_data=[{"text": "clip"}],
            job_id="manualcut_123",
            style_name="PODCAST",
            animation_type="fade",
            project_id="proj_1",
            center_x=0.4,
            layout="single",
            output_name="custom.mp4",
            skip_subtitles=False,
            cut_as_short=False,
        )
    )

    assert result == "manual.mp4"
    assert observed["ctx"] is creator
    assert observed["kwargs"] == {
        "start_t": 10.0,
        "end_t": 20.0,
        "transcript_data": [{"text": "clip"}],
        "job_id": "manualcut_123",
        "style_name": "PODCAST",
        "animation_type": "fade",
        "project_id": "proj_1",
        "center_x": 0.4,
        "layout": "single",
        "output_name": "custom.mp4",
        "skip_subtitles": False,
        "cut_as_short": False,
    }


def test_run_manual_clips_from_cut_points_async_dispatches_to_cut_points_workflow(monkeypatch) -> None:
    creator = _build_creator(monkeypatch)
    observed: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, ctx):
            observed["ctx"] = ctx

        async def run(self, **kwargs):
            observed["kwargs"] = kwargs
            return ["cut1.mp4"]

    monkeypatch.setattr(orchestrator_module, "CutPointsWorkflow", FakeWorkflow)

    result = asyncio.run(
        creator.run_manual_clips_from_cut_points_async(
            cut_points=[0.0, 5.0, 8.0],
            transcript_data=[{"text": "segment"}],
            job_id="manualcut_456",
            style_name="HORMOZI",
            animation_type="pop",
            project_id="proj_2",
            layout="double",
            skip_subtitles=True,
            cut_as_short=True,
        )
    )

    assert result == ["cut1.mp4"]
    assert observed["ctx"] is creator
    assert observed["kwargs"] == {
        "cut_points": [0.0, 5.0, 8.0],
        "transcript_data": [{"text": "segment"}],
        "job_id": "manualcut_456",
        "style_name": "HORMOZI",
        "animation_type": "pop",
        "project_id": "proj_2",
        "layout": "double",
        "skip_subtitles": True,
        "cut_as_short": True,
    }


def test_run_batch_manual_clips_async_dispatches_to_batch_workflow(monkeypatch) -> None:
    creator = _build_creator(monkeypatch)
    observed: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, ctx):
            observed["ctx"] = ctx

        async def run(self, **kwargs):
            observed["kwargs"] = kwargs
            return ["batch1.mp4", "batch2.mp4"]

    monkeypatch.setattr(orchestrator_module, "BatchClipWorkflow", FakeWorkflow)

    result = asyncio.run(
        creator.run_batch_manual_clips_async(
            start_t=30.0,
            end_t=90.0,
            num_clips=2,
            transcript_data=[{"text": "segment"}],
            job_id="batch_789",
            duration_min=10.0,
            duration_max=25.0,
            style_name="TIKTOK",
            animation_type="shake",
            project_id="proj_3",
            layout="single",
            skip_subtitles=False,
            cut_as_short=True,
        )
    )

    assert result == ["batch1.mp4", "batch2.mp4"]
    assert observed["ctx"] is creator
    assert observed["kwargs"] == {
        "start_t": 30.0,
        "end_t": 90.0,
        "num_clips": 2,
        "transcript_data": [{"text": "segment"}],
        "job_id": "batch_789",
        "duration_min": 10.0,
        "duration_max": 25.0,
        "style_name": "TIKTOK",
        "animation_type": "shake",
        "project_id": "proj_3",
        "layout": "single",
        "skip_subtitles": False,
        "cut_as_short": True,
    }


def test_reburn_subtitles_async_dispatches_to_reburn_workflow(monkeypatch) -> None:
    creator = _build_creator(monkeypatch)
    observed: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, ctx):
            observed["ctx"] = ctx

        async def run(self, **kwargs):
            observed["kwargs"] = kwargs
            return "reburned.mp4"

    monkeypatch.setattr(orchestrator_module, "ReburnWorkflow", FakeWorkflow)

    result = asyncio.run(
        creator.reburn_subtitles_async(
            clip_name="clip.mp4",
            transcript=[{"text": "updated"}],
            project_id="proj_4",
            style_name="HIGHCARE",
            animation_type="none",
        )
    )

    assert result == "reburned.mp4"
    assert observed["ctx"] is creator
    assert observed["kwargs"] == {
        "clip_name": "clip.mp4",
        "transcript": [{"text": "updated"}],
        "project_id": "proj_4",
        "style_name": "HIGHCARE",
        "animation_type": "none",
    }
