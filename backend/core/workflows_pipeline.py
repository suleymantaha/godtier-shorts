"""Pipeline workflow implementation."""

from __future__ import annotations

import asyncio
import json
import os
import time

from loguru import logger

from backend.config import TEMP_DIR, ProjectPaths
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import ProgressStepMapper, TempArtifactManager, build_hook_slug
from backend.core.workflow_runtime import create_subtitle_renderer
from backend.services.transcription import release_whisper_models, run_transcription


class PipelineWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        youtube_url: str,
        style_name: str = "HORMOZI",
        layout: str = "single",
        skip_subtitles: bool = False,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        resolution: str = "best",
    ) -> None:
        self.ctx._validate_youtube_url(youtube_url)
        global_start = time.time()
        self.ctx._check_cancelled()

        self.ctx.project = await self._prepare_project(youtube_url)
        master_video, master_audio = await self._ensure_master_assets(youtube_url, resolution)
        metadata_file = await self._ensure_transcript(master_audio)
        viral_results = await self._analyze_segments(
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

        await self._render_segments(
            segments,
            metadata_file=metadata_file,
            master_video=master_video,
            style_name=style_name,
            layout=layout,
            skip_subtitles=skip_subtitles,
        )

        elapsed = round(time.time() - global_start, 2)
        self.ctx._update_status("TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!", 100)
        logger.success(f"🎉 {elapsed}s içinde {len(segments)} video üretildi!")

    async def _prepare_project(self, youtube_url: str) -> ProjectPaths:
        self.ctx._update_status("Video ID alınıyor...", 5)
        try:
            rc, stdout, stderr = await self.ctx._run_command_with_cancel_async(
                ["yt-dlp", "--get-id", youtube_url],
                timeout=120,
                error_message="Video ID alma işlemi timeout oldu",
            )
            if rc != 0:
                raise RuntimeError(stderr or "Video ID alınamadı")
            video_id = stdout.strip()
            project = ProjectPaths(f"yt_{video_id}")
            logger.info(f"📁 Proje klasörü: {project.root}")
            return project
        except Exception as exc:
            logger.error(f"Video ID alınamadı: {exc}")
            return ProjectPaths(f"fallback_{int(time.time())}")

    async def _ensure_master_assets(self, youtube_url: str, resolution: str) -> tuple[str, str]:
        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")

        master_video = str(self.ctx.project.master_video)
        master_audio = str(self.ctx.project.master_audio)

        if os.path.exists(master_video):
            self.ctx._update_status("✅ Video kütüphanede bulundu, indirme atlanıyor.", 25)
            logger.info(f"♻️ Video zaten mevcut: {master_video}")
            return master_video, master_audio

        self.ctx._check_cancelled()
        self.ctx._update_status("Orijinal video indiriliyor...", 10)
        try:
            return await self.ctx.download_full_video_async(youtube_url, self.ctx.project, resolution)
        except RuntimeError as exc:
            logger.error(f"Pipeline durduruldu: {exc}")
            self.ctx._update_status(f"HATA: {exc}", -1)
            raise

    async def _ensure_transcript(self, master_audio: str) -> str:
        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")

        metadata_file = str(self.ctx.project.transcript)
        if os.path.exists(metadata_file):
            self.ctx._update_status("✅ Transkript kütüphanede bulundu, analiz atlanıyor.", 45)
            logger.info(f"♻️ Transkript zaten mevcut: {metadata_file}")
            return metadata_file

        self.ctx._check_cancelled()
        self.ctx._update_status("faster-whisper ses haritası çıkarıyor...", 30)
        try:
            metadata_file = await asyncio.to_thread(
                run_transcription,
                master_audio,
                str(self.ctx.project.transcript),
                lambda msg, pct: self.ctx._update_status(msg, pct),
                self.ctx.cancel_event,
            )
            await asyncio.to_thread(release_whisper_models)
            return metadata_file
        except Exception as exc:
            logger.error(f"❌ faster-whisper hatası: {exc}")
            self.ctx._update_status(f"faster-whisper hatası: {exc}", -1)
            raise RuntimeError(f"faster-whisper hatası: {exc}") from exc

    async def _analyze_segments(
        self,
        metadata_file: str,
        *,
        num_clips: int,
        duration_min: float,
        duration_max: float,
    ) -> dict:
        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")

        self.ctx._update_status("LLM viral klipleri seçiyor...", 50)
        self.ctx._check_cancelled()
        viral_results = await asyncio.to_thread(
            self.ctx.analyzer.analyze_metadata,
            metadata_file,
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
            ui_callback=self.ctx.ui_callback,
            cancel_event=self.ctx.cancel_event,
        )
        if not viral_results or "segments" not in viral_results:
            logger.error("❌ LLM viral kısım bulamadı!")
            self.ctx._update_status("HATA: Viral klip secimi basarisiz.", -1)
            raise RuntimeError("Viral klip seçimi başarısız oldu.")

        with open(self.ctx.project.viral_meta, "w", encoding="utf-8") as f:
            json.dump(viral_results, f, ensure_ascii=False, indent=4)
        return viral_results

    async def _render_segments(
        self,
        segments: list[dict],
        *,
        metadata_file: str,
        master_video: str,
        style_name: str,
        layout: str,
        skip_subtitles: bool,
    ) -> None:
        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")

        total = len(segments)
        self.ctx._update_status(f"{total} adet viral short üretimine başlandı!", 60)

        subtitle_engine = None if skip_subtitles else create_subtitle_renderer(style_name)

        progress = ProgressStepMapper(start=60, end=95, total_steps=total)

        for idx, seg in enumerate(segments):
            self.ctx._check_cancelled()
            clip_num = idx + 1
            start_t = seg["start_time"]
            end_t = seg["end_time"]
            hook = seg.get("hook_text", "")

            clip_name = f"short_{clip_num}_{build_hook_slug(hook, max_length=30)}"
            logger.info(f"🎬 Klip {clip_num}/{total} kurgulanıyor: {clip_name}")

            render_pct = progress.map(idx)
            self.ctx._update_status(
                f"Klip {clip_num}/{total} hazırlanıyor: {seg.get('ui_title', 'Viral Klip')}...",
                render_pct,
            )

            shifted_json = str(TEMP_DIR / f"shifted_{clip_num}.json")
            ass_file = str(TEMP_DIR / f"subs_{clip_num}.ass")
            temp_cropped = str(TEMP_DIR / f"cropped_{clip_num}.mp4")
            final_output = str(self.ctx.project.outputs / f"{clip_name}.mp4")

            transcript_data: list[dict] = []
            with TempArtifactManager(shifted_json, ass_file) as artifacts:
                if temp_cropped != final_output:
                    artifacts.add(temp_cropped)

                if not skip_subtitles and subtitle_engine is not None:
                    self.ctx._update_status(
                        f"Klip {clip_num}/{total} - Altyazılar oluşturuluyor...",
                        render_pct + 1,
                    )
                    self.ctx._shift_timestamps(metadata_file, start_t, end_t, shifted_json)
                    subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)
                    with open(shifted_json, "r", encoding="utf-8") as f:
                        transcript_data = json.load(f)

                clip_full_metadata = self.ctx._build_clip_metadata(
                    transcript_data,
                    viral_metadata={
                        "hook_text": seg.get("hook_text", ""),
                        "ui_title": seg.get("ui_title", ""),
                        "social_caption": seg.get("social_caption", ""),
                        "viral_score": seg.get("viral_score", 0),
                    },
                    render_metadata={
                        "mode": "pipeline_auto",
                        "project_id": self.ctx.project.root.name,
                        "clip_name": f"{clip_name}.mp4",
                        "start_time": start_t,
                        "end_time": end_t,
                        "crop_mode": "auto",
                        "center_x": None,
                        "layout": layout,
                        "style_name": style_name,
                        "skip_subtitles": skip_subtitles,
                    },
                )
                with open(final_output.replace(".mp4", ".json"), "w", encoding="utf-8") as f:
                    json.dump(clip_full_metadata, f, ensure_ascii=False, indent=4)

                self.ctx._update_status(
                    f"Klip {clip_num}/{total} - Video kesiliyor (YOLO + NVENC)...",
                    render_pct + 2,
                )
                if not skip_subtitles and subtitle_engine is not None:
                    self.ctx._update_status(
                        f"Klip {clip_num}/{total} - Altyazılar videoya gömülüyor...",
                        render_pct + 3,
                    )

                await asyncio.to_thread(
                    self.ctx._cut_and_burn_clip,
                    master_video,
                    start_t,
                    end_t,
                    temp_cropped,
                    final_output,
                    ass_file,
                    subtitle_engine,
                    layout=layout,
                    center_x=None,
                    cut_as_short=True,
                )
