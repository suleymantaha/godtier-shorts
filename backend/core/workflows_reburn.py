"""Subtitle reburn workflow implementation."""

from __future__ import annotations

import os
import time

from loguru import logger

from backend.config import TEMP_DIR, ProjectPaths
from backend.core.media_ops import analyze_transcript_segments
from backend.core.render_quality import (
    build_debug_environment,
    compute_render_quality_score,
    merge_transcript_quality,
)
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import (
    TempArtifactManager,
    load_json_dict,
    persist_debug_artifacts,
    run_blocking,
    write_json_atomic,
    write_reburn_metadata,
)


class ReburnWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        clip_name: str,
        transcript: list,
        project_id: str | None = None,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
    ) -> str:
        from backend.core.workflow_runtime import (
            create_subtitle_renderer,
            resolve_subtitle_render_plan,
        )
        from backend.services.subtitle_styles import StyleManager

        from backend.core.workflow_runtime import resolve_output_video_path

        input_video = resolve_output_video_path(clip_name, project_id)
        if not os.path.exists(input_video):
            raise FileNotFoundError(f"Video bulunamadı: {input_video}")

        raw_video = input_video.replace(".mp4", "_raw.mp4")
        source_video = raw_video if os.path.exists(raw_video) else input_video
        if source_video == raw_video:
            logger.info(f"♻️ Ham video kullanılıyor (çift altyazı önlenir): {raw_video}")

        temp_output = input_video.replace(".mp4", "_temp_reburn.mp4")
        ass_file = str(TEMP_DIR / f"{clip_name.replace('.mp4', '')}.ass")
        meta_path = input_video.replace(".mp4", ".json")
        existing_metadata = load_json_dict(meta_path)
        debug_environment = build_debug_environment(
            model_identifier=os.path.basename(str(self.ctx.video_processor._model_path)),
            model_path=str(self.ctx.video_processor._model_path),
        )
        existing_render_metadata = (existing_metadata or {}).get("render_metadata") if existing_metadata else None
        requested_layout = (
            existing_render_metadata.get("resolved_layout") or existing_render_metadata.get("layout") or "single"
        ) if isinstance(existing_render_metadata, dict) else "single"

        self.ctx._update_status("Altyazı haritası güncelleniyor...", 30)
        render_plan = resolve_subtitle_render_plan(
            video_processor=self.ctx.video_processor,
            source_video=source_video,
            start_t=0.0,
            end_t=1.0,
            requested_layout=requested_layout,
            cut_as_short=False,
            manual_center_x=None,
        )
        resolved_style = StyleManager.resolve_style(style_name, animation_type)
        subtitle_engine = create_subtitle_renderer(
            style_name,
            animation_type=animation_type,
            canvas_width=render_plan.canvas_width,
            canvas_height=render_plan.canvas_height,
            layout=render_plan.resolved_layout,
            safe_area_profile=render_plan.safe_area_profile,
            lower_third_detection={
                "lower_third_collision_detected": render_plan.lower_third_collision_detected,
                "lower_third_band_height_ratio": render_plan.lower_third_band_height_ratio,
            },
        )
        normalized_transcript = self.ctx._normalize_transcript_payload(transcript)
        base_transcript_quality = analyze_transcript_segments(normalized_transcript)

        temp_json = str(TEMP_DIR / f"reburn_{int(time.time())}.json")
        with TempArtifactManager(temp_json, ass_file) as _artifacts:
            write_json_atomic(temp_json, normalized_transcript)
            subtitle_engine.generate_ass_file(temp_json, ass_file, max_words_per_screen=3)

            self.ctx._update_status("Videonun makyajı tazeleniyor...", 60)
            await run_blocking(
                subtitle_engine.burn_subtitles_to_video,
                source_video,
                ass_file,
                temp_output,
                cancel_event=self.ctx.cancel_event,
            )

        os.replace(temp_output, input_video)
        subtitle_layout_quality = dict(getattr(subtitle_engine, "last_render_report", {}) or {})
        transcript_quality = merge_transcript_quality(
            base_quality=base_transcript_quality,
            subtitle_layout_quality=subtitle_layout_quality,
            snapping_report=None,
        )
        render_quality_score = compute_render_quality_score(
            tracking_quality=(existing_render_metadata or {}).get("tracking_quality") if isinstance(existing_render_metadata, dict) else None,
            transcript_quality=transcript_quality,
            debug_timing=(existing_render_metadata or {}).get("debug_timing") if isinstance(existing_render_metadata, dict) else None,
            subtitle_layout_quality=subtitle_layout_quality,
        )
        resolved_project_id = (
            project_id
            or (existing_render_metadata.get("project_id") if isinstance(existing_render_metadata, dict) else None)
        )
        debug_artifacts = persist_debug_artifacts(
            project=ProjectPaths(resolved_project_id),
            clip_name=clip_name,
            render_report={"debug_artifacts_status": "partial"},
            subtitle_layout_quality=subtitle_layout_quality,
            snap_report=None,
            debug_timing=(existing_render_metadata or {}).get("debug_timing") if isinstance(existing_render_metadata, dict) else None,
        ) if resolved_project_id else None

        write_reburn_metadata(
            ctx=self.ctx,
            meta_path=meta_path,
            transcript=normalized_transcript,
            existing_metadata=existing_metadata,
            existing_render_metadata=existing_render_metadata if isinstance(existing_render_metadata, dict) else None,
            style_name=style_name,
            animation_type=animation_type,
            resolved_animation_type=resolved_style.animation_type,
            resolved_layout=render_plan.resolved_layout,
            layout_fallback_reason=render_plan.layout_fallback_reason,
            transcript_quality=transcript_quality,
            subtitle_layout_quality=subtitle_layout_quality,
            debug_environment=debug_environment,
            render_quality_score=render_quality_score,
            debug_artifacts=debug_artifacts,
        )

        self.ctx._update_status("Klip başarıyla güncellendi!", 100)
        return input_video
