"""Pipeline workflow implementation."""

from __future__ import annotations

import os
import time

from loguru import logger

from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import (
    analyze_pipeline_segments,
    ensure_pipeline_master_assets,
    prepare_pipeline_project,
    render_pipeline_segments,
    run_blocking,
)


def run_transcription(*args, **kwargs):
    from backend.services.transcription import run_transcription as _run_transcription

    return _run_transcription(*args, **kwargs)


def release_whisper_models() -> None:
    from backend.services.transcription import release_whisper_models as _release_whisper_models

    _release_whisper_models()

class PipelineWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        youtube_url: str,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        layout: str = "auto",
        skip_subtitles: bool = False,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        resolution: str = "best",
    ) -> None:
        self.ctx._validate_youtube_url(youtube_url)
        global_start = time.time()
        self.ctx._check_cancelled()

        self.ctx.project = await prepare_pipeline_project(self.ctx, youtube_url)
        master_video, master_audio = await ensure_pipeline_master_assets(self.ctx, youtube_url, resolution)
        metadata_file = await self._ensure_transcript(master_audio)
        viral_results = await analyze_pipeline_segments(
            self.ctx,
            metadata_file,
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
        )

        segments = viral_results["segments"][:num_clips]
        if not segments:
            logger.error("❌ Hiç viral segment üretilmedi.")
            self.ctx._update_status("HATA: Üretilecek viral segment bulunamadı.", -1)
            raise RuntimeError("Üretilecek viral segment bulunamadı.")

        await render_pipeline_segments(
            self.ctx,
            segments,
            metadata_file=metadata_file,
            master_video=master_video,
            style_name=style_name,
            animation_type=animation_type,
            layout=layout,
            skip_subtitles=skip_subtitles,
            duration_min=duration_min,
            duration_max=duration_max,
        )

        elapsed = round(time.time() - global_start, 2)
        self.ctx._update_status("TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!", 100)
        logger.success(f"🎉 {elapsed}s içinde {len(segments)} video üretildi!")

    async def _ensure_transcript(self, master_audio: str) -> str:
        metadata_file = str(self.ctx.project.transcript)
        if os.path.exists(metadata_file):
            self.ctx._update_status("✅ Transkript kütüphanede bulundu, analiz atlanıyor.", 45)
            logger.info(f"♻️ Transkript zaten mevcut: {metadata_file}")
            return metadata_file

        self.ctx._check_cancelled()
        self.ctx._update_status("faster-whisper ses haritası çıkarıyor...", 30)
        try:
            metadata_file = await run_blocking(
                run_transcription,
                audio_file=master_audio,
                output_json=metadata_file,
                status_callback=lambda msg, pct: self.ctx._update_status(msg, pct),
                cancel_event=self.ctx.cancel_event,
            )
            await run_blocking(release_whisper_models)
            return metadata_file
        except Exception as exc:
            logger.error(f"❌ faster-whisper hatası: {exc}")
            self.ctx._update_status(f"faster-whisper hatası: {exc}", -1)
            raise RuntimeError(f"faster-whisper hatası: {exc}") from exc
