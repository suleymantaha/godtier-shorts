import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.workflows_reburn import ReburnWorkflow


@pytest.mark.parametrize("fail_stage", ["none", "encode", "metadata", "publish_metadata"])
def test_reburn_encode_holds_gpu_stage_and_blocks_competing_job(monkeypatch, tmp_path, fail_stage):
    import backend.core.workflow_runtime as runtime
    import backend.core.workflows_reburn as reburn

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"old")
    raw = tmp_path / "clip_raw.mp4"
    raw.write_bytes(b"raw")
    metadata = tmp_path / "clip.json"
    metadata.write_text('{"old": true}', encoding="utf-8")
    events = []
    lock = asyncio.Lock()

    @asynccontextmanager
    async def stage(**kwargs):
        async with lock:
            events.append("enter")
            try:
                yield
            finally:
                events.append("exit")

    class Renderer:
        def generate_ass_file(self, *args, **kwargs):
            pass

        def burn_subtitles_to_video(self, source, ass, output, **kwargs):
            assert lock.locked(), "encode must retain the shared GPU stage"
            events.append("encode")
            if fail_stage == "encode":
                Path(output).write_bytes(b"partial")
                raise RuntimeError("encode failed")
            Path(output).write_bytes(b"new")

    async def blocking(func, *args, **kwargs):
        async def competing_job():
            async with lock:
                events.append("competitor")
        task = asyncio.create_task(competing_job())
        await asyncio.sleep(0)
        try:
            return func(*args, **kwargs)
        finally:
            competitors.append(task)

    competitors = []
    ctx = SimpleNamespace(video_processor=SimpleNamespace(_model_path="fake.pt"), cancel_event=None,
                          _normalize_transcript_payload=lambda payload: payload,
                          _update_status=lambda *args: None, acquire_gpu_stage=stage)
    plan = SimpleNamespace(canvas_width=1080, canvas_height=1920, resolved_layout="single",
                           safe_area_profile="default", lower_third_collision_detected=False,
                           lower_third_band_height_ratio=0, layout_fallback_reason=None)
    monkeypatch.setattr(runtime, "resolve_output_video_path", lambda *args: str(video))
    monkeypatch.setattr(runtime, "resolve_subtitle_render_plan", lambda **kwargs: plan)
    monkeypatch.setattr(runtime, "create_subtitle_renderer", lambda *args, **kwargs: Renderer())
    monkeypatch.setattr(reburn, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(reburn, "run_blocking", blocking)
    def write_metadata(**kwargs):
        Path(kwargs["meta_path"]).write_text('{"new": true}', encoding="utf-8")
        if fail_stage == "metadata":
            raise RuntimeError("metadata failed")

    real_replace = reburn.os.replace

    def replace(source, destination):
        if fail_stage == "publish_metadata" and str(destination) == str(metadata):
            raise RuntimeError("publish_metadata failed")
        return real_replace(source, destination)

    monkeypatch.setattr(reburn, "write_reburn_metadata", write_metadata)
    monkeypatch.setattr(reburn.os, "replace", replace)

    async def run():
        try:
            if fail_stage != "none":
                with pytest.raises(RuntimeError, match=f"{fail_stage} failed"):
                    await ReburnWorkflow(ctx).run("clip.mp4", [])
            else:
                await ReburnWorkflow(ctx).run("clip.mp4", [])
        finally:
            await asyncio.gather(*competitors)
        assert not lock.locked()

    asyncio.run(run())
    assert events == ["enter", "encode", "exit", "competitor"]
    assert video.read_bytes() == (b"new" if fail_stage == "none" else b"old")
    assert metadata.read_text(encoding="utf-8") == ('{"new": true}' if fail_stage == "none" else '{"old": true}')
    assert raw.read_bytes() == b"raw"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["clip.json", "clip.mp4", "clip_raw.mp4"]
