"""Manual clip workflows (single + cut-points)."""
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Optional

from backend.config import TEMP_DIR
from backend.core.media_ops import build_shifted_transcript_segments_with_report
from backend.core.render_quality import (
    build_debug_environment,
    compute_render_quality_score,
    merge_transcript_quality,
)
from backend.core.workflow_context import OrchestratorContext
from backend.core.exceptions import RenderReviewRequiredError
from backend.core.workflow_helpers import (
    TempArtifactManager,
    assess_layout_safety,
    build_layout_review_item,
    build_quarantine_output_path,
    cleanup_render_bundle,
    commit_render_bundle,
    persist_debug_artifacts,
    resolve_initial_slot_centers,
    run_blocking,
    run_cut_points_workflow,
    write_json_atomic,
    resolve_layout_safety_mode,
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
        from backend.core.workflow_runtime import create_subtitle_renderer, resolve_project_master_video
        from backend.core.workflow_render_ops import resolve_segment_window_for_render
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

        clip_filename = (output_name or f"manual_{job_id}.mp4")
        if not clip_filename.endswith(".mp4"):
            clip_filename = f"{clip_filename}.mp4"
        if self.ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")
        quarantine_output = str(build_quarantine_output_path(self.ctx.project, clip_filename))
        debug_environment = build_debug_environment(model_identifier=os.path.basename(str(self.ctx.video_processor._model_path)), model_path=str(self.ctx.video_processor._model_path))
        layout_safety_mode = resolve_layout_safety_mode()

        with TempArtifactManager(temp_json, shifted_json, temp_cropped) as artifacts:
            if not skip_subtitles:
                artifacts.add(ass_file)
            artifacts.add(quarantine_output)
            artifacts.add(str(Path(quarantine_output).with_name(f"{Path(quarantine_output).stem}_raw.mp4")))

            write_json_atomic(temp_json, normalized_transcript, indent=4)
            async with self.ctx.acquire_gpu_stage(
                wait_message="Manuel klip için GPU render sırası bekleniyor...",
                active_message="Manuel klip için GPU render slotu alındı.",
                wait_progress=40,
                active_progress=45,
            ):
                resolved_start_t, resolved_end_t, snap_report, render_plan, opening_report = resolve_segment_window_for_render(
                    video_processor=self.ctx.video_processor,
                    transcript_source=normalized_transcript,
                    source_video=master_video,
                    start_t=float(start_t),
                    end_t=float(end_t),
                    requested_layout=layout,
                    cut_as_short=cut_as_short,
                    manual_center_x=center_x,
                )
                resolved_style = StyleManager.resolve_style(style_name, animation_type)
                shifted_segments, shifted_quality = build_shifted_transcript_segments_with_report(normalized_transcript, resolved_start_t, resolved_end_t)
                write_json_atomic(shifted_json, shifted_segments, indent=4)

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

                initial_slot_centers = resolve_initial_slot_centers(opening_report)

                render_report = await run_blocking(
                    self.ctx._cut_and_burn_clip,
                    master_video,
                    resolved_start_t,
                    resolved_end_t,
                    temp_cropped,
                    quarantine_output,
                    ass_file,
                    subtitle_engine,
                    render_plan.resolved_layout,
                    center_x,
                    initial_slot_centers,
                    cut_as_short,
                    False,
                )
            render_payload = render_report if isinstance(render_report, dict) else {}
            safety_metadata = assess_layout_safety(
                render_plan=render_plan,
                requested_layout=layout,
                tracking_quality=render_payload.get("tracking_quality") if isinstance(render_payload.get("tracking_quality"), dict) else None,
                manual_center_x=center_x,
            )

            if (
                cut_as_short
                and center_x is None
                and layout_safety_mode == "enforce"
                and render_plan.resolved_layout == "split"
                and safety_metadata["layout_safety_status"] == "unsafe"
            ):
                cleanup_render_bundle(quarantine_output)
                resolved_start_t, resolved_end_t, snap_report, render_plan, opening_report = (
                    resolve_segment_window_for_render(
                        video_processor=self.ctx.video_processor,
                        transcript_source=normalized_transcript,
                        source_video=master_video,
                        start_t=float(resolved_start_t),
                        end_t=float(resolved_end_t),
                        requested_layout="single",
                        cut_as_short=cut_as_short,
                        manual_center_x=None,
                    )
                )
                shifted_segments, shifted_quality = build_shifted_transcript_segments_with_report(normalized_transcript, resolved_start_t, resolved_end_t)
                write_json_atomic(shifted_json, shifted_segments, indent=4)
                subtitle_engine = None
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
                    resolved_start_t,
                    resolved_end_t,
                    temp_cropped,
                    quarantine_output,
                    ass_file,
                    subtitle_engine,
                    render_plan.resolved_layout,
                    center_x,
                    None,
                    cut_as_short,
                    False,
                )
                render_payload = render_report if isinstance(render_report, dict) else {}
                safety_metadata = assess_layout_safety(
                    render_plan=render_plan,
                    requested_layout=layout,
                    tracking_quality=render_payload.get("tracking_quality") if isinstance(render_payload.get("tracking_quality"), dict) else None,
                    manual_center_x=center_x,
                    layout_auto_fix_reason_override="split_runtime_degraded",
                    layout_auto_fix_applied_override=True,
                )

            if render_payload:
                artifacts.add(render_payload.get("debug_overlay_temp_path"))

            subtitle_layout_quality = render_payload.get("subtitle_layout_quality")
            transcript_quality = merge_transcript_quality(
                base_quality=shifted_quality,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snapping_report=snap_report,
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
                snap_report=snap_report,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
            )
            clip_metadata = self.ctx._build_clip_metadata(
                shifted_segments,
                viral_metadata=None,
                render_metadata={
                    "mode": "manual_auto" if center_x is None else "manual_custom_crop",
                    "project_id": self.ctx.project.root.name,
                    "clip_name": clip_filename,
                    "start_time": resolved_start_t,
                    "end_time": resolved_end_t,
                    "crop_mode": "auto" if center_x is None else "manual",
                    "center_x": center_x,
                    "layout": layout,
                    "resolved_layout": render_plan.resolved_layout,
                    "layout_fallback_reason": render_plan.layout_fallback_reason,
                    "safe_area_profile": getattr(render_plan, "safe_area_profile", "default"),
                    "lower_third_collision_detected": bool(getattr(render_plan, "lower_third_collision_detected", False)),
                    "lower_third_band_height_ratio": float(getattr(render_plan, "lower_third_band_height_ratio", 0.0) or 0.0),
                    "layout_auto_fix_applied": safety_metadata["layout_auto_fix_applied"],
                    "layout_auto_fix_reason": safety_metadata["layout_auto_fix_reason"],
                    "layout_safety_status": safety_metadata["layout_safety_status"],
                    "layout_safety_mode": safety_metadata["layout_safety_mode"],
                    "layout_safety_contract_version": safety_metadata["layout_safety_contract_version"],
                    "scene_class": safety_metadata["scene_class"],
                    "speaker_count_peak": safety_metadata["speaker_count_peak"],
                    "dominant_speaker_confidence": safety_metadata["dominant_speaker_confidence"],
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
            if layout_safety_mode == "enforce" and safety_metadata["layout_safety_status"] not in {"safe", "degraded"}:
                cleanup_render_bundle(quarantine_output)
                raise RenderReviewRequiredError(
                    "Render sonucu manuel inceleme gerektiriyor.",
                    review_items=[
                        build_layout_review_item(
                            start_time=start_t,
                            end_time=end_t,
                            requested_layout=layout,
                            attempted_layout=render_plan.resolved_layout,
                            layout_auto_fix_reason=str(safety_metadata["layout_auto_fix_reason"] or "split_runtime_degraded"),
                            suggested_layout="single",
                        )
                    ],
                    output_paths=[],
                    project_id=self.ctx.project.root.name,
                    num_clips=0,
                )

            final_output = commit_render_bundle(
                project=self.ctx.project,
                quarantine_output=quarantine_output,
                clip_filename=clip_filename,
                clip_metadata=clip_metadata,
                subject=self.ctx.subject,
                job_id=job_id,
                project_id=self.ctx.project.root.name,
                ui_title=None,
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
