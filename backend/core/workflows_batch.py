"""Batch clip workflow implementation."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from loguru import logger

from backend.config import TEMP_DIR
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import ProgressStepMapper, TempArtifactManager, build_hook_slug
from backend.core.workflow_runtime import create_subtitle_renderer, resolve_project_master_video
from backend.services.subtitle_renderer import SubtitleRenderer


class BatchClipWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        start_t: float,
        end_t: float,
        num_clips: int,
        transcript_data: list,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        style_name: str = "HORMOZI",
        project_id: Optional[str] = None,
        layout: str = "single",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        self.ctx.project, master_video = resolve_project_master_video(project_id, generated_prefix="batch")
        if not os.path.exists(master_video):
            raise FileNotFoundError(f"Orijinal video bulunamadı: {master_video}")

        self.ctx._update_status(f"AI Toplu Analiz başlıyor ({num_clips} klip)...", 10)

        sub_transcript = [s for s in transcript_data if s["start"] >= start_t and s["end"] <= end_t]
        viral_results = await asyncio.to_thread(
            self.ctx.analyzer.analyze_transcript_segment,
            transcript_data=sub_transcript,
            limit=num_clips,
            window_start=start_t,
            window_end=end_t,
            duration_min=duration_min,
            duration_max=duration_max,
            cancel_event=self.ctx.cancel_event,
        )

        if not viral_results or "segments" not in viral_results:
            logger.error("❌ AI bu aralıkta viral segment bulamadı!")
            self.ctx._update_status("HATA: AI viral segment bulamadı.", -1)
            return []

        segments = viral_results["segments"]
        total = len(segments)
        self.ctx._update_status(f"AI {total} adet viral an buldu, kurgu başlıyor...", 30)

        subtitle_engine: Optional[SubtitleRenderer] = None
        if not skip_subtitles:
            subtitle_engine = create_subtitle_renderer(style_name)

        progress = ProgressStepMapper(start=30, end=95, total_steps=total)
        results: list[str] = []

        for idx, seg in enumerate(segments):
            self.ctx._check_cancelled()
            clip_num = idx + 1
            s_t = seg["start_time"]
            e_t = seg["end_time"]
            hook = seg.get("hook_text", "")

            clip_name = f"batch_{clip_num}_{build_hook_slug(hook, max_length=25)}"
            render_pct = progress.map(idx)
            self.ctx._update_status(
                f"Klip {clip_num}/{total} hazırlanıyor: {seg.get('ui_title', 'Viral Klip')}...",
                render_pct,
            )

            shifted_json = str(TEMP_DIR / f"batch_s_{clip_num}.json")
            ass_file = str(TEMP_DIR / f"batch_a_{clip_num}.ass")
            temp_cropped = str(TEMP_DIR / f"batch_c_{clip_num}.mp4")
            final_output = str(self.ctx.project.outputs / f"{clip_name}.mp4") if self.ctx.project else ""
            temp_orig = str(TEMP_DIR / f"orig_{clip_num}.json")

            if not final_output:
                raise RuntimeError("Proje bağlamı bulunamadı.")

            with TempArtifactManager(temp_orig, shifted_json) as artifacts:
                if subtitle_engine is not None:
                    artifacts.add(ass_file)
                    artifacts.add(temp_cropped)

                with open(temp_orig, "w", encoding="utf-8") as f:
                    json.dump(transcript_data, f, ensure_ascii=False)

                self.ctx._shift_timestamps(temp_orig, s_t, e_t, shifted_json)
                if subtitle_engine is not None:
                    subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

                with open(shifted_json, "r", encoding="utf-8") as f:
                    t_data = json.load(f)

                clip_meta = self.ctx._build_clip_metadata(
                    t_data,
                    viral_metadata={
                        "hook_text": seg.get("hook_text", ""),
                        "ui_title": seg.get("ui_title", ""),
                        "social_caption": seg.get("social_caption", ""),
                        "viral_score": seg.get("viral_score", 0),
                    },
                    render_metadata={
                        "mode": "batch_auto",
                        "project_id": self.ctx.project.root.name,
                        "clip_name": f"{clip_name}.mp4",
                        "start_time": s_t,
                        "end_time": e_t,
                        "crop_mode": "auto",
                        "center_x": None,
                        "layout": layout,
                        "style_name": style_name,
                        "skip_subtitles": skip_subtitles,
                    },
                )
                with open(final_output.replace(".mp4", ".json"), "w", encoding="utf-8") as f:
                    json.dump(clip_meta, f, ensure_ascii=False, indent=4)

                self.ctx._update_status(f"Klip {clip_num}/{total} - Video kesiliyor...", render_pct + 1)
                if subtitle_engine is not None:
                    self.ctx._update_status(f"Klip {clip_num}/{total} - Altyazılar basılıyor...", render_pct + 2)

                await asyncio.to_thread(
                    self.ctx._cut_and_burn_clip,
                    master_video,
                    s_t,
                    e_t,
                    temp_cropped,
                    final_output,
                    ass_file,
                    subtitle_engine,
                    layout,
                    None,
                    cut_as_short,
                )
                results.append(final_output)

        self.ctx._update_status("TÜM TOPLU ÜRETİM TAMAMLANDI!", 100)
        logger.success(f"🎉 Toplu üretim bitti: {len(results)} klip.")
        return results
