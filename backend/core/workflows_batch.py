"""Batch clip workflow implementation."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger

from backend.core.media_ops import analyze_transcript_segments
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import (
    render_batch_segments,
    run_blocking,
)


def resolve_project_master_video(*args, **kwargs):
    from backend.core.workflow_runtime import resolve_project_master_video as _resolve_project_master_video

    return _resolve_project_master_video(*args, **kwargs)


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
        animation_type: str = "default",
        project_id: Optional[str] = None,
        layout: str = "single",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        self.ctx.project, master_video = resolve_project_master_video(
            project_id,
            generated_prefix="batch",
            owner_subject=self.ctx.subject,
        )
        if not os.path.exists(master_video):
            raise FileNotFoundError(f"Orijinal video bulunamadı: {master_video}")

        self.ctx._update_status(f"AI Toplu Analiz başlıyor ({num_clips} klip)...", 10)

        sub_transcript = [
            segment
            for segment in transcript_data
            if "start" in segment
            and "end" in segment
            and float(segment["end"]) > start_t
            and float(segment["start"]) < end_t
        ]
        viral_results = await run_blocking(
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
        results = await render_batch_segments(
            self.ctx,
            segments,
            transcript_data=transcript_data,
            master_video=master_video,
            style_name=style_name,
            animation_type=animation_type,
            layout=layout,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )

        self.ctx._update_status("TÜM TOPLU ÜRETİM TAMAMLANDI!", 100)
        ordered_results = [
            output_path
            for output_path, _score, _index in sorted(
                results,
                key=lambda item: (-item[1], item[2]),
            )
        ]
        logger.success(f"🎉 Toplu üretim bitti: {len(ordered_results)} klip.")
        return ordered_results
