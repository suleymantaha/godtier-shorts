"""Manual clip workflows (single + cut-points)."""
from __future__ import annotations
import asyncio
import json
import os
import time
from typing import Optional

from backend.config import TEMP_DIR
from backend.core.media_ops import build_shifted_transcript_segments_with_report
from backend.core.render_quality import (
    build_debug_environment,
    compute_render_quality_score,
    merge_transcript_quality,
)
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import (
    TempArtifactManager,
    persist_debug_artifacts,
    run_blocking,
    run_cut_points_workflow,
)
from backend.services.subtitle_renderer import SubtitleRenderer
class ManualClipWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        start_t: float,
        end_t: float,
        transcript_data: Optional[list],
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        project_id: Optional[str] = None,
        center_x: Optional[float] = None,
        layout: str = "single",
        output_name: Optional[str] = None,
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> str:
        from backend.core.workflow_runtime import (
            create_subtitle_renderer,
            resolve_project_master_video,
            resolve_subtitle_render_plan,
        )
        from backend.services.subtitle_styles import StyleManager

        self.ctx.project, master_video = resolve_project_master_video(
            project_id,
            generated_prefix="manual",
            owner_subject=self.ctx.subject,
        )
        if not os.path.exists(master_video):
            raise FileNotFoundError(f"Orijinal video bulunamadı: {master_video}")

        self.ctx._update_status(f"Manuel klip: {start_t} - {end_t} sn", 10)
        normalized_transcript = (
            self.ctx._normalize_transcript_payload(transcript_data)
            if transcript_data
            else self.ctx._load_project_transcript()
        )

        job_id = f"manual_{int(time.time())}"
        temp_json = str(TEMP_DIR / f"manual_{job_id}.json")
        shifted_json = str(TEMP_DIR / f"shifted_{job_id}.json")
        ass_file = str(TEMP_DIR / f"subs_{job_id}.ass")
        temp_cropped = str(TEMP_DIR / f"cropped_{job_id}.mp4")

        clip_filename = output_name or f"manual_{job_id}.mp4"
        if not clip_filename.endswith(".mp4"):
            clip_filename = f"{clip_filename}.mp4"

        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")
        final_output = str(self.ctx.project.outputs / clip_filename)
        debug_environment = build_debug_environment(
            model_identifier=os.path.basename(str(self.ctx.video_processor._model_path)),
            model_path=str(self.ctx.video_processor._model_path),
        )

        with TempArtifactManager(temp_json, shifted_json, temp_cropped) as artifacts:
            if not skip_subtitles:
                artifacts.add(ass_file)

            with open(temp_json, "w", encoding="utf-8") as f:
                json.dump(normalized_transcript, f, ensure_ascii=False, indent=4)

            shifted_segments, shifted_quality = build_shifted_transcript_segments_with_report(normalized_transcript, start_t, end_t)
            with open(shifted_json, "w", encoding="utf-8") as shifted_handle:
                json.dump(shifted_segments, shifted_handle, ensure_ascii=False, indent=4)
            render_plan = resolve_subtitle_render_plan(
                video_processor=self.ctx.video_processor,
                source_video=master_video,
                start_t=start_t,
                end_t=end_t,
                requested_layout=layout,
                cut_as_short=cut_as_short,
                manual_center_x=center_x,
            )
            resolved_style = StyleManager.resolve_style(style_name, animation_type)

            subtitle_engine: Optional[SubtitleRenderer] = None
            if not skip_subtitles:
                subtitle_engine = create_subtitle_renderer(
                    style_name,
                    animation_type=animation_type,
                    canvas_width=render_plan.canvas_width,
                    canvas_height=render_plan.canvas_height,
                    layout=render_plan.resolved_layout,
                )
                subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

            render_report = await run_blocking(
                self.ctx._cut_and_burn_clip,
                master_video,
                start_t,
                end_t,
                temp_cropped,
                final_output,
                ass_file,
                subtitle_engine,
                render_plan.resolved_layout,
                center_x,
                cut_as_short,
                False,
            )
            if isinstance(render_report, dict):
                artifacts.add(render_report.get("debug_overlay_temp_path"))

            meta_path = final_output.replace(".mp4", ".json")
            subtitle_layout_quality = render_report.get("subtitle_layout_quality") if isinstance(render_report, dict) else None
            transcript_quality = merge_transcript_quality(
                base_quality=shifted_quality,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snapping_report=None,
            )
            tracking_quality = render_report.get("tracking_quality") if isinstance(render_report, dict) else None
            debug_timing = render_report.get("debug_timing") if isinstance(render_report, dict) else None
            render_quality_score = compute_render_quality_score(
                tracking_quality=tracking_quality if isinstance(tracking_quality, dict) else None,
                transcript_quality=transcript_quality,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
            )
            debug_artifacts = persist_debug_artifacts(
                project=self.ctx.project,
                clip_name=clip_filename,
                render_report=render_report if isinstance(render_report, dict) else None,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snap_report=None,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
            )
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.ctx._build_clip_metadata(
                        shifted_segments,
                        viral_metadata=None,
                        render_metadata={
                            "mode": "manual_auto" if center_x is None else "manual_custom_crop",
                            "project_id": self.ctx.project.root.name,
                            "clip_name": clip_filename,
                            "start_time": start_t,
                            "end_time": end_t,
                            "crop_mode": "auto" if center_x is None else "manual",
                            "center_x": center_x,
                            "layout": layout,
                            "resolved_layout": render_plan.resolved_layout,
                            "layout_fallback_reason": render_plan.layout_fallback_reason,
                            "style_name": style_name,
                            "animation_type": animation_type,
                            "resolved_animation_type": resolved_style.animation_type,
                            "cut_as_short": cut_as_short,
                            "tracking_quality": tracking_quality,
                            "transcript_quality": transcript_quality,
                            "debug_timing": debug_timing,
                            "debug_tracking": render_report.get("debug_tracking") if isinstance(render_report, dict) else None,
                            "debug_environment": debug_environment,
                            "render_quality_score": render_quality_score,
                            "audio_validation": render_report.get("audio_validation") if isinstance(render_report, dict) else None,
                            "subtitle_layout_quality": subtitle_layout_quality,
                            **({"debug_artifacts": debug_artifacts} if debug_artifacts else {}),
                        },
                    ),
                    f,
                    ensure_ascii=False,
                    indent=4,
                )

        self.ctx._update_status(f"Manuel klip hazır: {final_output}", 100)
        return final_output


class CutPointsWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        cut_points: list[float],
        transcript_data: list,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        project_id: Optional[str] = None,
        layout: str = "single",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        return await run_cut_points_workflow(
            self.ctx,
            cut_points=cut_points,
            transcript_data=transcript_data,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            layout=layout,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )
