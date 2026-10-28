import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.workflows_reburn import ReburnWorkflow


@pytest.fixture
def legacy_clip(monkeypatch, tmp_path):
    import backend.core.workflow_runtime as runtime
    import backend.core.workflows_reburn as reburn

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"original")
    metadata = tmp_path / "clip.json"
    sources = []
    lock = asyncio.Lock()

    @asynccontextmanager
    async def stage(**kwargs):
        async with lock:
            yield

    class Renderer:
        def generate_ass_file(self, *args, **kwargs):
            pass

        def burn_subtitles_to_video(self, source, ass, output, **kwargs):
            sources.append(source)
            Path(output).write_bytes(b"subtitled")

    async def blocking(func, *args, **kwargs):
        await asyncio.sleep(0)
        return func(*args, **kwargs)

    ctx = SimpleNamespace(
        video_processor=SimpleNamespace(_model_path="fake.pt"),
        cancel_event=None,
        _normalize_transcript_payload=lambda payload: payload,
        _build_clip_metadata=lambda transcript, **kwargs: {"transcript": transcript, **kwargs},
        _update_status=lambda *args: None,
        acquire_gpu_stage=stage,
    )
    plan = SimpleNamespace(
        canvas_width=1080, canvas_height=1920, resolved_layout="single",
        safe_area_profile="default", lower_third_collision_detected=False,
        lower_third_band_height_ratio=0, layout_fallback_reason=None,
    )
    monkeypatch.setattr(runtime, "resolve_output_video_path", lambda *args: str(video))
    monkeypatch.setattr(runtime, "resolve_subtitle_render_plan", lambda **kwargs: plan)
    monkeypatch.setattr(runtime, "create_subtitle_renderer", lambda *args, **kwargs: Renderer())
    monkeypatch.setattr(reburn, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(reburn, "run_blocking", blocking)
    return ReburnWorkflow(ctx), video, metadata, sources


@pytest.mark.parametrize("render_metadata", [None, {}, {"skip_subtitles": False}, {"skip_subtitles": "true"}])
def test_missing_raw_rejects_subtitled_or_unknown_source_without_modifying_clip(legacy_clip, render_metadata):
    workflow, video, metadata, sources = legacy_clip
    metadata.write_text(json.dumps({"render_metadata": render_metadata}), encoding="utf-8")
    original_metadata = metadata.read_bytes()

    with pytest.raises(ValueError, match="Ham video"):
        asyncio.run(workflow.run("clip.mp4", []))

    assert sources == []
    assert video.read_bytes() == b"original"
    assert metadata.read_bytes() == original_metadata
    assert sorted(path.name for path in video.parent.iterdir()) == ["clip.json", "clip.mp4"]


def test_missing_raw_allows_explicitly_subtitle_free_clip_once(legacy_clip):
    workflow, video, metadata, sources = legacy_clip
    metadata.write_text(json.dumps({"render_metadata": {"skip_subtitles": True}}), encoding="utf-8")

    assert asyncio.run(workflow.run("clip.mp4", [])) == str(video)

    assert sources == [str(video)]
    assert video.read_bytes() == b"subtitled"
    updated = json.loads(metadata.read_text(encoding="utf-8"))
    assert updated["render_metadata"]["skip_subtitles"] is False
    with pytest.raises(ValueError, match="Ham video"):
        asyncio.run(workflow.run("clip.mp4", []))
    assert sources == [str(video)]


def test_raw_source_is_used_even_when_public_clip_has_subtitles(legacy_clip):
    workflow, video, metadata, sources = legacy_clip
    raw = video.with_name("clip_raw.mp4")
    raw.write_bytes(b"raw")
    metadata.write_text('{"render_metadata": {"skip_subtitles": false}}', encoding="utf-8")

    asyncio.run(workflow.run("clip.mp4", []))

    assert sources == [str(raw)]
    assert raw.read_bytes() == b"raw"


def test_queued_subtitle_free_reburn_rechecks_source_after_gpu_wait(legacy_clip):
    workflow, video, metadata, sources = legacy_clip
    metadata.write_text('{"render_metadata": {"skip_subtitles": true}}', encoding="utf-8")

    async def run():
        return await asyncio.gather(
            workflow.run("clip.mp4", []), workflow.run("clip.mp4", []),
            return_exceptions=True,
        )

    results = asyncio.run(run())
    assert results[0] == str(video)
    assert isinstance(results[1], ValueError)
    assert sources == [str(video)]
