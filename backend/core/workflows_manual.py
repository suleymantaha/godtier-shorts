"""Manual clip workflows (single + cut-points)."""
from __future__ import annotations
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
    publish_clip_ready_event,
    run_blocking,
    run_cut_points_workflow,
    write_json_atomic,
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
        job_id: str | None = None,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        project_id: Optional[str] = None,
        center_x: Optional[float] = None,
        layout: str = "auto",
        output_name: Optional[str] = None,
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> str:
        from backend.core.workflow_runtime import create_subtitle_renderer, resolve_project_master_video, resolve_subtitle_render_plan
        from backend.services.subtitle_styles import StyleManager

        self.ctx.project, master_video = resolve_project_master_video(
            project_id,
            generated_prefix="manual",
            owner_subject=self.ctx.subject,
        )
        if not os.path.exists(master_video):
            raise FileNotFoundError(f"Orijinal video bulunamadı: {master_video}")

        self.ctx._update_status(f"Manuel klip: {start_t} - {end_t} sn", 10)
        normalized_transcript = self.ctx._normalize_transcript_payload(transcript_data) if transcript_data else self.ctx._load_project_transcript()

        job_id = f"manual_{int(time.time())}"
        temp_json = str(TEMP_DIR / f"manual_{job_id}.json")
        shifted_json = str(TEMP_DIR / f"shifted_{job_id}.json")
        ass_file = str(TEMP_DIR / f"subs_{job_id}.ass")
        temp_cropped = str(TEMP_DIR / f"cropped_{job_id}.mp4")

        clip_filename = output_name or f"manual_{job_id}.mp4"
        clip_filename = clip_filename if clip_filename.endswith(".mp4") else f"{clip_filename}.mp4"

        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")
        final_output = str(self.ctx.project.outputs / clip_filename)
        debug_environment = build_debug_environment(model_identifier=os.path.basename(str(self.ctx.video_processor._model_path)), model_path=str(self.ctx.video_processor._model_path))

        with TempArtifactManager(temp_json, shifted_json, temp_cropped) as artifacts:
            if not skip_subtitles:
                artifacts.add(ass_file)

            write_json_atomic(temp_json, normalized_transcript, indent=4)
            shifted_segments, shifted_quality = build_shifted_transcript_segments_with_report(normalized_transcript, start_t, end_t)
            write_json_atomic(shifted_json, shifted_segments, indent=4)
            async with self.ctx.acquire_gpu_stage(
                wait_message="Manuel klip için GPU render sırası bekleniyor...",
                active_message="Manuel klip için GPU render slotu alındı.",
                wait_progress=40,
                active_progress=45,
            ):
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
                        safe_area_profile=render_plan.safe_area_profile,
                        lower_third_detection={
                            "lower_third_collision_detected": render_plan.lower_third_collision_detected,
                            "lower_third_band_height_ratio": render_plan.lower_third_band_height_ratio,
                        },
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
                    None,
                    cut_as_short,
                    False,
                )
            render_payload = render_report if isinstance(render_report, dict) else {}
            if render_payload:
                artifacts.add(render_payload.get("debug_overlay_temp_path"))

            meta_path = final_output.replace(".mp4", ".json")
            subtitle_layout_quality = render_payload.get("subtitle_layout_quality")
            transcript_quality = merge_transcript_quality(
                base_quality=shifted_quality,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snapping_report=None,
            )
            tracking_quality = render_payload.get("tracking_quality")
            debug_timing = render_payload.get("debug_timing")
            render_quality_score = compute_render_quality_score(
                tracking_quality=tracking_quality if isinstance(tracking_quality, dict) else None,
                transcript_quality=transcript_quality,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
            )
            debug_artifacts = persist_debug_artifacts(
                project=self.ctx.project,
                clip_name=clip_filename,
                render_report=render_payload or None,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snap_report=None,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
            )
            clip_metadata = self.ctx._build_clip_metadata(
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
                    "debug_tracking": render_payload.get("debug_tracking"),
                    "debug_environment": debug_environment,
                    "render_quality_score": render_quality_score,
                    "audio_validation": render_payload.get("audio_validation"),
                    "subtitle_layout_quality": subtitle_layout_quality,
                    **({"debug_artifacts": debug_artifacts} if debug_artifacts else {}),
                },
            )
            write_json_atomic(meta_path, clip_metadata, indent=4)
            publish_clip_ready_event(
                subject=self.ctx.subject,
                job_id=job_id,
                project_id=self.ctx.project.root.name,
                clip_name=clip_filename,
                message="Manuel klip hazır.",
                progress=99,
                clip_event_port=self.ctx.clip_event_port,
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
        job_id: str | None = None,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        project_id: Optional[str] = None,
        layout: str = "auto",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        return await run_cut_points_workflow(
            self.ctx,
            cut_points=cut_points,
            transcript_data=transcript_data,
            job_id=job_id,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            layout=layout,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )
