from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from backend.workers.production_runner import (
    GpuObjectLifecycleRunner,
    ProductionJobContext,
)


class FakeRepository:
    def __init__(self, context: ProductionJobContext) -> None:
        self.context = context
        self.outputs = []
        self.metrics = []

    async def load_context(self, _request):
        return self.context

    async def record_output(self, **kwargs):
        self.outputs.append(kwargs)

    async def record_metrics(self, **kwargs):
        self.metrics.append(kwargs)


class FakeObjectStore:
    def __init__(self) -> None:
        self.downloads = []
        self.uploads = []

    async def download(self, key: str, destination: Path) -> None:
        self.downloads.append((key, destination))
        destination.write_bytes(b"source-video")

    async def upload(self, key: str, source: Path, content_type: str) -> None:
        self.uploads.append((key, source.name, content_type, source.read_bytes()))


class FakePipeline:
    async def run(self, context, source, scratch_dir, request, report):
        assert source.read_bytes() == b"source-video"
        await report(55, "rendering")
        first = scratch_dir / "clip-1.mp4"
        second = scratch_dir / "clip-2.mp4"
        first.write_bytes(b"clip-one")
        second.write_bytes(b"clip-two")
        return [first, second]


def test_gpu_runner_downloads_source_uploads_outputs_and_cleans_scratch(tmp_path) -> None:
    job_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    context = ProductionJobContext(
        job_id=job_id,
        user_id=user_id,
        project_id=project_id,
        source_url=None,
        source_storage_key=f"uploads/{user_id}/source.mp4",
    )
    repository = FakeRepository(context)
    store = FakeObjectStore()
    progress = []
    runner = GpuObjectLifecycleRunner(
        repository=repository,
        object_store=store,
        pipeline=FakePipeline(),
        scratch_root=tmp_path,
        gpu_probe=lambda: ("RTX Test", 128),
    )

    asyncio.run(runner({"_job_id": str(job_id)}, lambda value, message: _report(progress, value, message)))

    assert store.downloads[0][0] == context.source_storage_key
    assert [upload[0] for upload in store.uploads] == [
        f"outputs/{user_id}/{job_id}/clip-1.mp4",
        f"outputs/{user_id}/{job_id}/clip-2.mp4",
    ]
    assert len(repository.outputs) == 2
    assert repository.metrics[0]["gpu_model"] == "RTX Test"
    assert repository.metrics[0]["peak_vram_mb"] == 128
    assert not (tmp_path / str(job_id)).exists()
    assert progress == [(5, "source_download"), (55, "rendering"), (95, "output_upload")]


def test_gpu_runner_cleans_scratch_when_pipeline_fails(tmp_path) -> None:
    job_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    context = ProductionJobContext(
        job_id=job_id,
        user_id=user_id,
        project_id=project_id,
        source_url=None,
        source_storage_key=f"uploads/{user_id}/source.mp4",
    )

    class FailingPipeline:
        async def run(self, *_args, **_kwargs):
            raise RuntimeError("render failed")

    runner = GpuObjectLifecycleRunner(
        repository=FakeRepository(context),
        object_store=FakeObjectStore(),
        pipeline=FailingPipeline(),
        scratch_root=tmp_path,
        gpu_probe=lambda: ("RTX Test", None),
    )

    with pytest.raises(RuntimeError, match="render failed"):
        asyncio.run(runner({"_job_id": str(job_id)}, _noop_report))

    assert not (tmp_path / str(job_id)).exists()


async def _report(events, value, message):
    events.append((value, message))


async def _noop_report(_value, _message):
    return None
