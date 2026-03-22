"""Pipeline workflow implementation."""

from __future__ import annotations

import os
import time

from loguru import logger

from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import (
    analyze_pipeline_segments,
    build_pipeline_cache_identity,
    build_segments_signature,
    ensure_pipeline_master_assets,
    extract_pipeline_segments,
    load_cached_pipeline_analysis,
    load_pipeline_render_cache_hit,
    prepare_pipeline_project,
    record_pipeline_analysis_cache,
    record_pipeline_render_cache,
    render_pipeline_segments,
    resolve_video_model_identifier,
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
        force_reanalyze: bool = False,
        force_rerender: bool = False,
    ) -> None:
        self.ctx._validate_youtube_url(youtube_url)
        global_start = time.time()
        self.ctx._check_cancelled()

        self.ctx.project = await prepare_pipeline_project(self.ctx, youtube_url)
        project = self.ctx.project
        if project is None:
            raise RuntimeError("Pipeline proje bağlamı hazırlanamadı.")
        master_video, master_audio = await ensure_pipeline_master_assets(self.ctx, youtube_url, resolution)
        metadata_file = await self._ensure_transcript(master_audio)
        cache_identity = build_pipeline_cache_identity(
            project=project,
            ai_engine=str(getattr(self.ctx.analyzer, "engine", "local") or "local"),
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
            style_name=style_name,
            animation_type=animation_type,
            layout=layout,
            skip_subtitles=skip_subtitles,
            video_model_identifier=resolve_video_model_identifier(getattr(self.ctx.video_processor, "_model_path", None)),
        )
        viral_results = None if force_reanalyze else load_cached_pipeline_analysis(
            project,
            analysis_key=cache_identity.analysis_key,
        )
        if viral_results is not None:
            self.ctx._update_status("✅ Viral analiz kütüphanede bulundu, yeniden hesaplama atlandı.", 50)
            logger.info("♻️ Viral analiz cache hit: {}", cache_identity.analysis_key)
        else:
            viral_results = await analyze_pipeline_segments(
                self.ctx,
                metadata_file,
                num_clips=num_clips,
                duration_min=duration_min,
                duration_max=duration_max,
            )
            record_pipeline_analysis_cache(
                project,
                identity=cache_identity,
                viral_results=viral_results,
            )

        segments = extract_pipeline_segments(viral_results, clip_limit=num_clips)
        if segments is None:
            logger.error("❌ Viral analiz sonucu geçersiz segment formatı döndürdü.")
            self.ctx._update_status("HATA: Viral analiz sonucu okunamadı.", -1)
            raise RuntimeError("Viral analiz sonucu okunamadı.")
        if not segments:
            logger.error("❌ Hiç viral segment üretilmedi.")
            self.ctx._update_status("HATA: Üretilecek viral segment bulunamadı.", -1)
            raise RuntimeError("Üretilecek viral segment bulunamadı.")

        segments_signature = build_segments_signature(segments)
        if not force_rerender:
            render_hit = load_pipeline_render_cache_hit(
                project,
                render_key=cache_identity.render_key,
                segments_signature=segments_signature,
            )
            if render_hit is not None:
                self.ctx._update_status("✅ Render cache bulundu, mevcut clip seti kullanılıyor.", 95)
                logger.info("♻️ Render cache hit: {}", cache_identity.render_key)
                elapsed = round(time.time() - global_start, 2)
                self.ctx._update_status("TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!", 100)
                logger.success(f"🎉 {elapsed}s içinde {render_hit.clip_count} cache'li video bulundu!")
                return

        rendered_clip_names = await render_pipeline_segments(
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
            analysis_key=cache_identity.analysis_key,
            render_key=cache_identity.render_key,
        )
        record_pipeline_render_cache(
            project,
            identity=cache_identity,
            segments_signature=segments_signature,
            clip_names=rendered_clip_names,
            skip_subtitles=skip_subtitles,
            clip_event_port=self.ctx.clip_event_port,
        )

        elapsed = round(time.time() - global_start, 2)
        self.ctx._update_status("TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!", 100)
        logger.success(f"🎉 {elapsed}s içinde {len(segments)} video üretildi!")

    async def _ensure_transcript(self, master_audio: str) -> str:
        project = self.ctx.project
        if project is None:
            raise RuntimeError("Pipeline proje bağlamı bulunamadı.")

        metadata_file = str(project.transcript)
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
