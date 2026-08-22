from __future__ import annotations

import asyncio
import hashlib
import json
import math
import mimetypes
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.db.models import Asset, AssetKind, Job, JobEvent, Project, SourceType
from backend.db.session import get_session_factory
from backend.workers.gpu_tasks import DeterministicJobError, TransientJobError


ProgressReporter = Callable[[int, str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ProductionJobContext:
    job_id: UUID
    user_id: UUID
    project_id: UUID
    source_url: str | None
    source_storage_key: str | None


class ProductionJobRepository(Protocol):
    async def load_context(self, request: dict[str, Any]) -> ProductionJobContext: ...

    async def record_output(
        self,
        *,
        context: ProductionJobContext,
        storage_key: str,
        source: Path,
        sha256: str,
        content_type: str,
    ) -> None: ...

    async def record_metrics(
        self,
        *,
        job_id: UUID,
        gpu_model: str,
        gpu_seconds: int,
        peak_vram_mb: int | None,
    ) -> None: ...


class WorkerObjectStore(Protocol):
    async def download(self, key: str, destination: Path) -> None: ...

    async def upload(self, key: str, source: Path, content_type: str) -> None: ...


class ProductionPipeline(Protocol):
    async def run(
        self,
        context: ProductionJobContext,
        source: str | Path,
        scratch_dir: Path,
        request: dict[str, Any],
        report: ProgressReporter,
    ) -> list[Path]: ...


class GpuObjectLifecycleRunner:
    def __init__(
        self,
        *,
        repository: ProductionJobRepository,
        object_store: WorkerObjectStore,
        pipeline: ProductionPipeline,
        scratch_root: Path,
        gpu_probe: Callable[[], tuple[str, int | None]],
    ) -> None:
        self._repository = repository
        self._object_store = object_store
        self._pipeline = pipeline
        self._scratch_root = scratch_root
        self._gpu_probe = gpu_probe

    async def __call__(
        self, request: dict[str, Any], report: ProgressReporter
    ) -> None:
        context = await self._repository.load_context(request)
        scratch_dir = self._scratch_root / str(context.job_id)
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir)
        scratch_dir.mkdir(parents=True)
        started = time.monotonic()
        try:
            source = await self._resolve_source(context, scratch_dir, report)
            output_paths = await self._pipeline.run(
                context, source, scratch_dir, request, report
            )
            if not output_paths:
                raise DeterministicJobError("Pipeline produced no outputs")
            await report(95, "output_upload")
            for output_path in output_paths:
                await self._publish_output(context, scratch_dir, output_path)
            gpu_model, peak_vram_mb = self._gpu_probe()
            try:
                await self._repository.record_metrics(
                    job_id=context.job_id,
                    gpu_model=gpu_model,
                    gpu_seconds=max(1, math.ceil(time.monotonic() - started)),
                    peak_vram_mb=peak_vram_mb,
                )
            except Exception as exc:
                raise TransientJobError("GPU metrics persistence failed") from exc
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    async def _resolve_source(
        self,
        context: ProductionJobContext,
        scratch_dir: Path,
        report: ProgressReporter,
    ) -> str | Path:
        if context.source_storage_key:
            await report(5, "source_download")
            suffix = Path(context.source_storage_key).suffix.lower() or ".mp4"
            destination = scratch_dir / f"source{suffix}"
            try:
                await self._object_store.download(
                    context.source_storage_key, destination
                )
            except Exception as exc:
                raise TransientJobError("R2 source download failed") from exc
            if not destination.is_file() or destination.stat().st_size <= 0:
                raise DeterministicJobError("Downloaded source is empty")
            return destination
        if context.source_url:
            return context.source_url
        raise DeterministicJobError("Job has no usable source")

    async def _publish_output(
        self,
        context: ProductionJobContext,
        scratch_dir: Path,
        output_path: Path,
    ) -> None:
        resolved_scratch = scratch_dir.resolve()
        resolved_output = output_path.resolve()
        if not resolved_output.is_relative_to(resolved_scratch):
            raise DeterministicJobError("Pipeline output escaped job scratch")
        if not resolved_output.is_file() or resolved_output.stat().st_size <= 0:
            raise DeterministicJobError("Pipeline output is missing or empty")
        content_type = mimetypes.guess_type(resolved_output.name)[0] or "video/mp4"
        storage_key = (
            f"outputs/{context.user_id}/{context.job_id}/{resolved_output.name}"
        )
        try:
            await self._object_store.upload(
                storage_key, resolved_output, content_type
            )
        except Exception as exc:
            raise TransientJobError("R2 output upload failed") from exc
        digest = await asyncio.to_thread(_sha256_file, resolved_output)
        try:
            await self._repository.record_output(
                context=context,
                storage_key=storage_key,
                source=resolved_output,
                sha256=digest,
                content_type=content_type,
            )
        except Exception as exc:
            raise TransientJobError("Output metadata persistence failed") from exc


class SqlAlchemyProductionJobRepository:
    async def load_context(self, request: dict[str, Any]) -> ProductionJobContext:
        try:
            job_id = UUID(str(request["_job_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise DeterministicJobError("Worker request has no valid job id") from exc
        factory = get_session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    select(Job, Project).join(Project, Job.project_id == Project.id).where(
                        Job.id == job_id,
                        Job.user_id == Project.user_id,
                    )
                )
            ).first()
            if row is None:
                raise DeterministicJobError("Job project was not found")
            job, project = row
            source_key = await session.scalar(
                select(Asset.storage_key)
                .where(
                    Asset.user_id == job.user_id,
                    Asset.project_id == job.project_id,
                    Asset.kind == AssetKind.SOURCE,
                )
                .order_by(Asset.created_at.desc())
                .limit(1)
            )
            source_url = (
                project.source_ref if project.source_type is SourceType.YOUTUBE else None
            )
            if project.source_type is SourceType.UPLOAD and source_key is None:
                raise DeterministicJobError("Upload project has no source asset")
            return ProductionJobContext(
                job_id=job.id,
                user_id=job.user_id,
                project_id=job.project_id,
                source_url=source_url,
                source_storage_key=source_key,
            )

    async def record_output(self, **kwargs) -> None:
        context: ProductionJobContext = kwargs["context"]
        source: Path = kwargs["source"]
        factory = get_session_factory()
        async with factory() as session, session.begin():
            existing = await session.scalar(
                select(Asset.id).where(Asset.storage_key == kwargs["storage_key"])
            )
            if existing is not None:
                return
            session.add(
                Asset(
                    id=uuid4(),
                    user_id=context.user_id,
                    project_id=context.project_id,
                    job_id=context.job_id,
                    kind=AssetKind.SHORT,
                    storage_key=kwargs["storage_key"],
                    mime_type=kwargs["content_type"],
                    size_bytes=source.stat().st_size,
                    sha256=kwargs["sha256"],
                )
            )

    async def record_metrics(self, **kwargs) -> None:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            job = await session.get(Job, kwargs["job_id"], with_for_update=True)
            if job is None:
                raise DeterministicJobError("Job was not found for GPU metrics")
            job.gpu_model = kwargs["gpu_model"]
            job.gpu_seconds = kwargs["gpu_seconds"]
            session.add(
                JobEvent(
                    job_id=job.id,
                    status=job.status,
                    progress=job.progress,
                    message=json.dumps(
                        {
                            "gpu_model": kwargs["gpu_model"],
                            "gpu_seconds": kwargs["gpu_seconds"],
                            "peak_vram_mb": kwargs["peak_vram_mb"],
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    source="gpu-worker-metrics",
                )
            )


class Boto3WorkerObjectStore:
    def __init__(self, client: Any, bucket_name: str) -> None:
        self._client = client
        self._bucket_name = bucket_name

    async def download(self, key: str, destination: Path) -> None:
        await asyncio.to_thread(
            self._client.download_file,
            self._bucket_name,
            key,
            str(destination),
        )

    async def upload(self, key: str, source: Path, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.upload_file,
            str(source),
            self._bucket_name,
            key,
            {"ContentType": content_type},
        )


class LegacyProductionPipeline:
    async def run(
        self,
        context: ProductionJobContext,
        source: str | Path,
        scratch_dir: Path,
        request: dict[str, Any],
        report: ProgressReporter,
    ) -> list[Path]:
        from backend.core.orchestrator import GodTierShortsCreator
        from backend.core.workflow_pipeline_ops import prepare_pipeline_project

        subject = hashlib.sha256(context.user_id.bytes).hexdigest()[:32]
        pending_reports: list[asyncio.Task] = []

        def status_callback(payload: dict[str, Any]) -> None:
            progress = int(payload.get("progress") or 0)
            message = str(payload.get("message") or "processing")
            pending_reports.append(asyncio.create_task(report(progress, message)))

        creator = GodTierShortsCreator(
            ui_callback=status_callback,
            subject=subject,
        )
        project_root: Path | None = None
        try:
            pipeline_source = str(source)
            if isinstance(source, Path):
                video_id = context.project_id.hex[:11]
                pipeline_source = f"https://youtu.be/{video_id}"
                project = await prepare_pipeline_project(creator, pipeline_source)
                project_root = project.root
                shutil.copy2(source, project.master_video)
            await creator.run_pipeline_async(
                pipeline_source,
                style_name=str(request.get("style_name") or "TIKTOK"),
                animation_type=str(request.get("animation_type") or "default"),
                layout=str(request.get("layout") or "auto"),
                skip_subtitles=bool(request.get("skip_subtitles", False)),
                num_clips=int(request.get("num_clips") or 1),
                duration_min=30,
                duration_max=60,
                resolution=str(request.get("resolution") or "1080p"),
            )
            if creator.project is None:
                raise DeterministicJobError("Pipeline project was not created")
            project_root = creator.project.root
            output_dir = scratch_dir / "outputs"
            output_dir.mkdir()
            copied = []
            for output in sorted(creator.project.outputs.glob("*.mp4")):
                destination = output_dir / output.name
                shutil.copy2(output, destination)
                copied.append(destination)
            return copied
        finally:
            if pending_reports:
                await asyncio.gather(*pending_reports, return_exceptions=True)
            creator.cleanup_gpu()
            if project_root is not None:
                shutil.rmtree(project_root, ignore_errors=True)


def build_production_runner() -> GpuObjectLifecycleRunner:
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    return GpuObjectLifecycleRunner(
        repository=SqlAlchemyProductionJobRepository(),
        object_store=Boto3WorkerObjectStore(client, os.environ["R2_BUCKET_NAME"]),
        pipeline=LegacyProductionPipeline(),
        scratch_root=Path(os.getenv("GPU_SCRATCH_ROOT", "/scratch/jobs")),
        gpu_probe=_probe_gpu,
    )


def _probe_gpu() -> tuple[str, int | None]:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA became unavailable while recording metrics")
    peak = int(torch.cuda.max_memory_allocated(0) / (1024 * 1024))
    return torch.cuda.get_device_name(0), peak


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
