"""Render-phase helpers for pipeline and batch workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path

from loguru import logger

from backend.config import TEMP_DIR
from backend.core.exceptions import RenderReviewRequiredError
from backend.core.render_contracts import resolve_duration_validation_status
from backend.core.workflow_artifacts import (
    SAFE_PUBLIC_LAYOUT_STATUSES,
    ProgressStepMapper,
    assess_layout_safety,
    build_layout_review_item,
    build_quarantine_output_path,
    cleanup_render_bundle,
    commit_render_bundle,
    persist_debug_artifacts,
    resolve_initial_slot_centers,
    resolve_layout_safety_mode,
)
from backend.core.workflow_common import TempArtifactManager, build_hook_slug, run_blocking


def apply_opening_validation(
    *,
    video_processor,
    source_video: str,
    start_t: float,
    end_t: float,
    resolved_layout: str,
    manual_center_x: float | None = None,
) -> tuple[float, dict[str, object]]:
    opening_report = video_processor.analyze_opening_shot(
        input_video=source_video,
        start_time=start_t,
        end_time=end_t,
        resolved_layout=resolved_layout,
        manual_center_x=manual_center_x,
    )
    suggested_start = float(
        opening_report.get("suggested_start_time", start_t) or start_t
    )
    if suggested_start >= end_t:
        suggested_start = start_t
    opening_report["suggested_start_time"] = suggested_start
    return suggested_start, opening_report


async def render_pipeline_segments(
    ctx,
    segments: list[dict],
    *,
    metadata_file: str,
    master_video: str,
    style_name: str,
    animation_type: str,
    layout: str,
    skip_subtitles: bool,
    duration_min: float,
    duration_max: float,
    analysis_key: str,
    render_key: str,
) -> list[str]:
    from backend.core.media_ops import shift_timestamps_with_report
    from backend.core.render_quality import (
        build_debug_environment,
        compute_render_quality_score,
        merge_transcript_quality,
    )
    from backend.core.subtitle_timing import snap_segment_boundaries
    from backend.core.workflow_runtime import (
        create_subtitle_renderer,
        resolve_subtitle_render_plan,
    )
    from backend.services.subtitle_styles import StyleManager

    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    total_segments = len(segments)
    rendered_clip_names: list[str] = []
    safe_output_paths: list[str] = []
    review_items: list[dict[str, object]] = []
    layout_safety_mode = resolve_layout_safety_mode()

    with open(metadata_file, "r", encoding="utf-8") as transcript_handle:
        source_transcript = json.load(transcript_handle)

    debug_environment = _build_debug_environment(
        getattr(ctx, "video_processor", None),
        build_debug_environment=build_debug_environment,
    )
    ctx._update_status(f"{total_segments} adet viral short üretimine başlandı!", 60)
    progress = ProgressStepMapper(start=60, end=95, total_steps=total_segments)

    for segment_index, segment in enumerate(segments):
        ctx._check_cancelled()
        clip_number = segment_index + 1
        segment_start = segment["start_time"]
        segment_end = segment["end_time"]
        (
            segment_start,
            segment_end,
            snap_report,
            render_plan,
            opening_report,
        ) = _resolve_segment_window(
            video_processor=ctx.video_processor,
            transcript_source=source_transcript,
            source_video=master_video,
            start_t=segment_start,
            end_t=segment_end,
            requested_layout=layout,
            cut_as_short=True,
            manual_center_x=None,
            snap_segment_boundaries=snap_segment_boundaries,
            resolve_subtitle_render_plan=resolve_subtitle_render_plan,
        )

        clip_name = _build_segment_clip_name(
            prefix="short",
            clip_number=clip_number,
            segment=segment,
            max_hook_length=30,
        )
        clip_filename = f"{clip_name}.mp4"
        logger.info(f"🎬 Klip {clip_number}/{total_segments} kurgulanıyor: {clip_name}")

        render_progress = progress.map(segment_index)
        ctx._update_status(
            f"Klip {clip_number}/{total_segments} hazırlanıyor: "
            f"{segment.get('ui_title', 'Viral Klip')}...",
            render_progress,
        )

        shifted_json = str(TEMP_DIR / f"shifted_{clip_number}.json")
        ass_file = str(TEMP_DIR / f"subs_{clip_number}.ass")
        temp_cropped = str(TEMP_DIR / f"cropped_{clip_number}.mp4")
        quarantine_output = str(
            build_quarantine_output_path(ctx.project, clip_filename)
        )
        async with ctx.acquire_gpu_stage(
            wait_message=(
                f"Klip {clip_number}/{total_segments} - GPU render sırası bekleniyor..."
            ),
            active_message=(
                f"Klip {clip_number}/{total_segments} - GPU render slotu alındı."
            ),
            wait_progress=render_progress + 1,
            active_progress=render_progress + 1,
        ):
            duration_validation_status = resolve_duration_validation_status(
                segment_start,
                segment_end,
                duration_min=duration_min,
                duration_max=duration_max,
            )
            if duration_validation_status != "ok":
                raise RuntimeError("Segment süresi istenen aralığın dışına çıktı.")

            resolved_style = StyleManager.resolve_style(style_name, animation_type)
            with TempArtifactManager(shifted_json, ass_file) as artifacts:
                if temp_cropped != quarantine_output:
                    artifacts.add(temp_cropped)
                _register_render_bundle_artifacts(
                    artifacts,
                    quarantine_output=quarantine_output,
                )

                subtitle_engine = _create_subtitle_renderer_if_needed(
                    create_subtitle_renderer=create_subtitle_renderer,
                    style_name=style_name,
                    animation_type=animation_type,
                    render_plan=render_plan,
                    skip_subtitles=skip_subtitles,
                )
                if subtitle_engine is not None:
                    ctx._update_status(
                        f"Klip {clip_number}/{total_segments} - "
                        "Altyazılar oluşturuluyor...",
                        render_progress + 1,
                    )

                shift_report = shift_timestamps_with_report(
                    metadata_file,
                    segment_start,
                    segment_end,
                    shifted_json,
                )
                transcript_data = shift_report["segments"]
                _generate_ass_file_if_needed(
                    subtitle_engine=subtitle_engine,
                    shifted_json=shifted_json,
                    ass_file=ass_file,
                )

                ctx._update_status(
                    f"Klip {clip_number}/{total_segments} - "
                    "Video kesiliyor (YOLO + NVENC)...",
                    render_progress + 2,
                )
                if subtitle_engine is not None:
                    ctx._update_status(
                        f"Klip {clip_number}/{total_segments} - "
                        "Altyazılar videoya gömülüyor...",
                        render_progress + 3,
                    )

                render_plan, render_payload, safety_metadata = (
                    await _render_with_optional_single_fallback(
                        ctx=ctx,
                        create_subtitle_renderer=create_subtitle_renderer,
                        resolve_subtitle_render_plan=resolve_subtitle_render_plan,
                        master_video=master_video,
                        style_name=style_name,
                        animation_type=animation_type,
                        requested_layout=layout,
                        render_plan=render_plan,
                        segment_start=segment_start,
                        segment_end=segment_end,
                        shifted_json=shifted_json,
                        ass_file=ass_file,
                        temp_cropped=temp_cropped,
                        quarantine_output=quarantine_output,
                        opening_report=opening_report,
                        skip_subtitles=skip_subtitles,
                        cut_as_short=True,
                        require_audio=True,
                        manual_center_x=None,
                        layout_safety_mode=layout_safety_mode,
                        allow_single_fallback=True,
                    )
                )
                if render_payload:
                    artifacts.add(render_payload.get("debug_overlay_temp_path"))

                render_quality_context = _collect_render_quality_context(
                    compute_render_quality_score=compute_render_quality_score,
                    merge_transcript_quality=merge_transcript_quality,
                    project=ctx.project,
                    clip_filename=clip_filename,
                    render_payload=render_payload,
                    base_transcript_quality=shift_report.get("transcript_quality"),
                    snap_report=snap_report,
                    debug_environment=debug_environment,
                )
                clip_metadata = _build_clip_metadata(
                    ctx=ctx,
                    transcript_data=transcript_data,
                    segment=segment,
                    mode="pipeline_auto",
                    clip_filename=clip_filename,
                    start_time=segment_start,
                    end_time=segment_end,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    duration_validation_status=duration_validation_status,
                    requested_layout=layout,
                    render_plan=render_plan,
                    opening_report=opening_report,
                    safety_metadata=safety_metadata,
                    style_name=style_name,
                    animation_type=animation_type,
                    resolved_animation_type=resolved_style.animation_type,
                    skip_subtitles=skip_subtitles,
                    cut_as_short=True,
                    render_quality_context=render_quality_context,
                    analysis_key=analysis_key,
                    render_key=render_key,
                )

                if _should_hold_for_review(
                    layout_safety_mode=layout_safety_mode,
                    safety_metadata=safety_metadata,
                ):
                    cleanup_render_bundle(quarantine_output)
                    review_items.append(
                        _build_review_item(
                            segment_index=segment_index,
                            segment=segment,
                            start_time=segment_start,
                            end_time=segment_end,
                            requested_layout=layout,
                            attempted_layout=render_plan.resolved_layout,
                            safety_metadata=safety_metadata,
                        )
                    )
                    continue

                public_output = commit_render_bundle(
                    project=ctx.project,
                    quarantine_output=quarantine_output,
                    clip_filename=clip_filename,
                    clip_metadata=clip_metadata,
                    subject=ctx.subject,
                    project_id=ctx.project.root.name,
                    ui_title=str(segment.get("ui_title", "")).strip() or None,
                    message=f"Klip {clip_number}/{total_segments} hazır.",
                    progress=min(render_progress + 4, 99),
                    clip_event_port=ctx.clip_event_port,
                )
                safe_output_paths.append(public_output)
                rendered_clip_names.append(clip_filename)

    _raise_for_review_if_needed(
        ctx=ctx,
        review_items=review_items,
        safe_output_paths=safe_output_paths,
    )
    return rendered_clip_names


async def run_cut_points_workflow(
    ctx,
    *,
    cut_points: list[float],
    transcript_data: list,
    job_id: str | None,
    style_name: str,
    animation_type: str,
    project_id: str | None,
    layout: str,
    skip_subtitles: bool,
    cut_as_short: bool,
) -> list[str]:
    if len(cut_points) < 2:
        return []

    from backend.core.workflows_manual import ManualClipWorkflow

    results: list[str] = []
    total_segments = len(cut_points) - 1
    manual_workflow = ManualClipWorkflow(ctx)

    for index in range(total_segments):
        ctx._check_cancelled()
        start_t = cut_points[index]
        end_t = cut_points[index + 1]
        if end_t <= start_t:
            continue

        clip_number = index + 1
        progress = 10 + int((index / total_segments) * 85)
        ctx._update_status(
            f"Klip {clip_number}/{total_segments}: {start_t:.1f}-{end_t:.1f} sn...",
            progress,
        )
        output_name = f"cut_{clip_number}_{int(start_t)}_{int(end_t)}.mp4"
        output_path = await manual_workflow.run(
            start_t=start_t,
            end_t=end_t,
            transcript_data=transcript_data,
            job_id=job_id,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            center_x=None,
            layout=layout,
            output_name=output_name,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )
        results.append(output_path)

    ctx._update_status("Tüm kesim noktaları işlendi!", 100)
    return results


async def render_batch_segments(
    ctx,
    segments: list[dict],
    *,
    job_id: str | None,
    transcript_data: list,
    master_video: str,
    style_name: str,
    animation_type: str,
    layout: str,
    skip_subtitles: bool,
    cut_as_short: bool,
    duration_min: float,
    duration_max: float,
) -> list[tuple[str, float, int]]:
    from backend.core.media_ops import build_shifted_transcript_segments_with_report
    from backend.core.render_quality import (
        build_debug_environment,
        compute_render_quality_score,
        merge_transcript_quality,
    )
    from backend.core.subtitle_timing import snap_segment_boundaries
    from backend.core.workflow_runtime import (
        create_subtitle_renderer,
        resolve_subtitle_render_plan,
    )
    from backend.services.subtitle_styles import StyleManager

    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    total_segments = len(segments)
    progress = ProgressStepMapper(start=30, end=95, total_steps=total_segments)
    results: list[tuple[str, float, int]] = []
    safe_output_paths: list[str] = []
    review_items: list[dict[str, object]] = []
    layout_safety_mode = resolve_layout_safety_mode()
    debug_environment = _build_debug_environment(
        getattr(ctx, "video_processor", None),
        build_debug_environment=build_debug_environment,
    )

    for segment_index, segment in enumerate(segments):
        ctx._check_cancelled()
        clip_number = segment_index + 1
        (
            segment_start,
            segment_end,
            snap_report,
            render_plan,
            opening_report,
        ) = _resolve_segment_window(
            video_processor=ctx.video_processor,
            transcript_source=transcript_data,
            source_video=master_video,
            start_t=segment["start_time"],
            end_t=segment["end_time"],
            requested_layout=layout,
            cut_as_short=cut_as_short,
            manual_center_x=None,
            snap_segment_boundaries=snap_segment_boundaries,
            resolve_subtitle_render_plan=resolve_subtitle_render_plan,
        )
        clip_name = _build_segment_clip_name(
            prefix="batch",
            clip_number=clip_number,
            segment=segment,
            max_hook_length=25,
        )
        clip_filename = f"{clip_name}.mp4"
        render_progress = progress.map(segment_index)
        ctx._update_status(
            f"Klip {clip_number}/{total_segments} hazırlanıyor: "
            f"{segment.get('ui_title', 'Viral Klip')}...",
            render_progress,
        )

        shifted_json = str(TEMP_DIR / f"batch_s_{clip_number}.json")
        ass_file = str(TEMP_DIR / f"batch_a_{clip_number}.ass")
        temp_cropped = str(TEMP_DIR / f"batch_c_{clip_number}.mp4")
        temp_orig = str(TEMP_DIR / f"orig_{clip_number}.json")
        quarantine_output = str(
            build_quarantine_output_path(ctx.project, clip_filename)
        )

        async with ctx.acquire_gpu_stage(
            wait_message=(
                f"Klip {clip_number}/{total_segments} - GPU render sırası bekleniyor..."
            ),
            active_message=(
                f"Klip {clip_number}/{total_segments} - GPU render slotu alındı."
            ),
            wait_progress=render_progress + 1,
            active_progress=render_progress + 1,
        ):
            duration_validation_status = resolve_duration_validation_status(
                segment_start,
                segment_end,
                duration_min=duration_min,
                duration_max=duration_max,
            )
            if duration_validation_status != "ok":
                raise RuntimeError("Segment süresi istenen aralığın dışına çıktı.")

            resolved_style = StyleManager.resolve_style(style_name, animation_type)
            with TempArtifactManager(temp_orig, shifted_json) as artifacts:
                subtitle_engine = _create_subtitle_renderer_if_needed(
                    create_subtitle_renderer=create_subtitle_renderer,
                    style_name=style_name,
                    animation_type=animation_type,
                    render_plan=render_plan,
                    skip_subtitles=skip_subtitles,
                )
                if subtitle_engine is not None:
                    artifacts.add(ass_file)
                artifacts.add(temp_cropped)
                _register_render_bundle_artifacts(
                    artifacts,
                    quarantine_output=quarantine_output,
                )

                with open(temp_orig, "w", encoding="utf-8") as handle:
                    json.dump(transcript_data, handle, ensure_ascii=False)
                shifted_segments, shifted_quality = (
                    build_shifted_transcript_segments_with_report(
                        transcript_data,
                        segment_start,
                        segment_end,
                    )
                )
                with open(shifted_json, "w", encoding="utf-8") as shifted_handle:
                    json.dump(
                        shifted_segments,
                        shifted_handle,
                        ensure_ascii=False,
                        indent=4,
                    )
                _generate_ass_file_if_needed(
                    subtitle_engine=subtitle_engine,
                    shifted_json=shifted_json,
                    ass_file=ass_file,
                )

                ctx._update_status(
                    f"Klip {clip_number}/{total_segments} - Video kesiliyor...",
                    render_progress + 1,
                )
                if subtitle_engine is not None:
                    ctx._update_status(
                        f"Klip {clip_number}/{total_segments} - Altyazılar basılıyor...",
                        render_progress + 2,
                    )

                render_plan, render_payload, safety_metadata = (
                    await _render_with_optional_single_fallback(
                        ctx=ctx,
                        create_subtitle_renderer=create_subtitle_renderer,
                        resolve_subtitle_render_plan=resolve_subtitle_render_plan,
                        master_video=master_video,
                        style_name=style_name,
                        animation_type=animation_type,
                        requested_layout=layout,
                        render_plan=render_plan,
                        segment_start=segment_start,
                        segment_end=segment_end,
                        shifted_json=shifted_json,
                        ass_file=ass_file,
                        temp_cropped=temp_cropped,
                        quarantine_output=quarantine_output,
                        opening_report=opening_report,
                        skip_subtitles=skip_subtitles,
                        cut_as_short=cut_as_short,
                        require_audio=False,
                        manual_center_x=None,
                        layout_safety_mode=layout_safety_mode,
                        allow_single_fallback=cut_as_short,
                    )
                )
                if render_payload:
                    artifacts.add(render_payload.get("debug_overlay_temp_path"))

                render_quality_context = _collect_render_quality_context(
                    compute_render_quality_score=compute_render_quality_score,
                    merge_transcript_quality=merge_transcript_quality,
                    project=ctx.project,
                    clip_filename=clip_filename,
                    render_payload=render_payload,
                    base_transcript_quality=shifted_quality,
                    snap_report=snap_report,
                    debug_environment=debug_environment,
                )
                clip_metadata = _build_clip_metadata(
                    ctx=ctx,
                    transcript_data=shifted_segments,
                    segment=segment,
                    mode="batch_auto",
                    clip_filename=clip_filename,
                    start_time=segment_start,
                    end_time=segment_end,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    duration_validation_status=duration_validation_status,
                    requested_layout=layout,
                    render_plan=render_plan,
                    opening_report=opening_report,
                    safety_metadata=safety_metadata,
                    style_name=style_name,
                    animation_type=animation_type,
                    resolved_animation_type=resolved_style.animation_type,
                    skip_subtitles=skip_subtitles,
                    cut_as_short=cut_as_short,
                    render_quality_context=render_quality_context,
                )

                if _should_hold_for_review(
                    layout_safety_mode=layout_safety_mode,
                    safety_metadata=safety_metadata,
                ):
                    cleanup_render_bundle(quarantine_output)
                    review_items.append(
                        _build_review_item(
                            segment_index=segment_index,
                            segment=segment,
                            start_time=segment_start,
                            end_time=segment_end,
                            requested_layout=layout,
                            attempted_layout=render_plan.resolved_layout,
                            safety_metadata=safety_metadata,
                        )
                    )
                    continue

                public_output = commit_render_bundle(
                    project=ctx.project,
                    quarantine_output=quarantine_output,
                    clip_filename=clip_filename,
                    clip_metadata=clip_metadata,
                    subject=ctx.subject,
                    job_id=job_id,
                    project_id=ctx.project.root.name,
                    ui_title=str(segment.get("ui_title", "")).strip() or None,
                    message=f"Klip {clip_number}/{total_segments} hazır.",
                    progress=min(render_progress + 4, 99),
                    clip_event_port=ctx.clip_event_port,
                )
                safe_output_paths.append(public_output)
                results.append(
                    (
                        public_output,
                        render_quality_context["render_quality_score"],
                        segment_index,
                    )
                )

    _raise_for_review_if_needed(
        ctx=ctx,
        review_items=review_items,
        safe_output_paths=safe_output_paths,
    )
    return results


def _build_debug_environment(video_processor, *, build_debug_environment):
    if video_processor is None:
        return None
    model_path = str(video_processor._model_path)
    return build_debug_environment(
        model_identifier=os.path.basename(model_path),
        model_path=model_path,
    )


def _resolve_segment_window(
    *,
    video_processor,
    transcript_source: list,
    source_video: str,
    start_t: float,
    end_t: float,
    requested_layout: str,
    cut_as_short: bool,
    manual_center_x: float | None,
    snap_segment_boundaries,
    resolve_subtitle_render_plan,
) -> tuple[float, float, dict[str, object], object, dict[str, object]]:
    segment_start, segment_end, snap_report = snap_segment_boundaries(
        transcript_source,
        start_t,
        end_t,
    )
    render_plan = resolve_subtitle_render_plan(
        video_processor=video_processor,
        source_video=source_video,
        start_t=segment_start,
        end_t=segment_end,
        requested_layout=requested_layout,
        cut_as_short=cut_as_short,
        manual_center_x=manual_center_x,
    )
    opening_report: dict[str, object] = {
        "layout_validation_status": "not_applicable",
        "opening_visibility_delay_ms": 0.0,
        "suggested_start_time": segment_start,
    }
    if not cut_as_short:
        return segment_start, segment_end, snap_report, render_plan, opening_report

    validated_start, opening_report = apply_opening_validation(
        video_processor=video_processor,
        source_video=source_video,
        start_t=segment_start,
        end_t=segment_end,
        resolved_layout=render_plan.resolved_layout,
        manual_center_x=manual_center_x,
    )
    if str(opening_report.get("layout_validation_status")) == "opening_subject_missing":
        raise RuntimeError("Açılışta görünür subject bulunamadı.")
    if validated_start <= segment_start:
        return segment_start, segment_end, snap_report, render_plan, opening_report

    segment_start, segment_end, snap_report = snap_segment_boundaries(
        transcript_source,
        validated_start,
        segment_end,
    )
    render_plan = resolve_subtitle_render_plan(
        video_processor=video_processor,
        source_video=source_video,
        start_t=segment_start,
        end_t=segment_end,
        requested_layout=requested_layout,
        cut_as_short=cut_as_short,
        manual_center_x=manual_center_x,
    )
    _, opening_report = apply_opening_validation(
        video_processor=video_processor,
        source_video=source_video,
        start_t=segment_start,
        end_t=segment_end,
        resolved_layout=render_plan.resolved_layout,
        manual_center_x=manual_center_x,
    )
    return segment_start, segment_end, snap_report, render_plan, opening_report


def _build_segment_clip_name(
    *,
    prefix: str,
    clip_number: int,
    segment: dict,
    max_hook_length: int,
) -> str:
    hook_slug = build_hook_slug(
        segment.get("hook_text", ""),
        max_length=max_hook_length,
    )
    return f"{prefix}_{clip_number}_{hook_slug}"


def _create_subtitle_renderer_if_needed(
    *,
    create_subtitle_renderer,
    style_name: str,
    animation_type: str,
    render_plan,
    skip_subtitles: bool,
):
    if skip_subtitles:
        return None
    return create_subtitle_renderer(
        style_name,
        animation_type=animation_type,
        canvas_width=render_plan.canvas_width,
        canvas_height=render_plan.canvas_height,
        layout=render_plan.resolved_layout,
        safe_area_profile=render_plan.safe_area_profile,
        lower_third_detection=_build_lower_third_detection(render_plan),
    )


def _build_lower_third_detection(render_plan) -> dict[str, object]:
    return {
        "lower_third_collision_detected": render_plan.lower_third_collision_detected,
        "lower_third_band_height_ratio": render_plan.lower_third_band_height_ratio,
    }


def _register_render_bundle_artifacts(artifacts, *, quarantine_output: str) -> None:
    artifacts.add(quarantine_output)
    raw_output = Path(quarantine_output).with_name(
        f"{Path(quarantine_output).stem}_raw.mp4"
    )
    artifacts.add(str(raw_output))


def _generate_ass_file_if_needed(
    *,
    subtitle_engine,
    shifted_json: str,
    ass_file: str,
) -> None:
    if subtitle_engine is None:
        return
    subtitle_engine.generate_ass_file(
        shifted_json,
        ass_file,
        max_words_per_screen=3,
    )


async def _render_with_optional_single_fallback(
    *,
    ctx,
    create_subtitle_renderer,
    resolve_subtitle_render_plan,
    master_video: str,
    style_name: str,
    animation_type: str,
    requested_layout: str,
    render_plan,
    segment_start: float,
    segment_end: float,
    shifted_json: str,
    ass_file: str,
    temp_cropped: str,
    quarantine_output: str,
    opening_report: dict[str, object],
    skip_subtitles: bool,
    cut_as_short: bool,
    require_audio: bool,
    manual_center_x: float | None,
    layout_safety_mode: str,
    allow_single_fallback: bool,
) -> tuple[object, dict[str, object], dict[str, object]]:
    subtitle_engine = _create_subtitle_renderer_if_needed(
        create_subtitle_renderer=create_subtitle_renderer,
        style_name=style_name,
        animation_type=animation_type,
        render_plan=render_plan,
        skip_subtitles=skip_subtitles,
    )
    _generate_ass_file_if_needed(
        subtitle_engine=subtitle_engine,
        shifted_json=shifted_json,
        ass_file=ass_file,
    )
    render_payload = await _run_render_pass(
        ctx=ctx,
        master_video=master_video,
        segment_start=segment_start,
        segment_end=segment_end,
        temp_cropped=temp_cropped,
        quarantine_output=quarantine_output,
        ass_file=ass_file,
        subtitle_engine=subtitle_engine,
        render_plan=render_plan,
        opening_report=opening_report,
        cut_as_short=cut_as_short,
        require_audio=require_audio,
        manual_center_x=manual_center_x,
    )
    safety_metadata = assess_layout_safety(
        render_plan=render_plan,
        requested_layout=requested_layout,
        tracking_quality=_as_dict(render_payload.get("tracking_quality")),
        manual_center_x=manual_center_x,
    )

    should_rerender = (
        allow_single_fallback
        and layout_safety_mode == "enforce"
        and render_plan.resolved_layout == "split"
        and safety_metadata["layout_safety_status"] == "unsafe"
    )
    if not should_rerender:
        return render_plan, render_payload, safety_metadata

    cleanup_render_bundle(quarantine_output)
    render_plan = resolve_subtitle_render_plan(
        video_processor=ctx.video_processor,
        source_video=master_video,
        start_t=segment_start,
        end_t=segment_end,
        requested_layout="single",
        cut_as_short=cut_as_short,
        manual_center_x=manual_center_x,
    )
    subtitle_engine = _create_subtitle_renderer_if_needed(
        create_subtitle_renderer=create_subtitle_renderer,
        style_name=style_name,
        animation_type=animation_type,
        render_plan=render_plan,
        skip_subtitles=skip_subtitles,
    )
    _generate_ass_file_if_needed(
        subtitle_engine=subtitle_engine,
        shifted_json=shifted_json,
        ass_file=ass_file,
    )
    render_payload = await _run_render_pass(
        ctx=ctx,
        master_video=master_video,
        segment_start=segment_start,
        segment_end=segment_end,
        temp_cropped=temp_cropped,
        quarantine_output=quarantine_output,
        ass_file=ass_file,
        subtitle_engine=subtitle_engine,
        render_plan=render_plan,
        opening_report=opening_report,
        cut_as_short=cut_as_short,
        require_audio=require_audio,
        manual_center_x=manual_center_x,
    )
    safety_metadata = assess_layout_safety(
        render_plan=render_plan,
        requested_layout=requested_layout,
        tracking_quality=_as_dict(render_payload.get("tracking_quality")),
        manual_center_x=manual_center_x,
        layout_auto_fix_reason_override="split_runtime_degraded",
        layout_auto_fix_applied_override=True,
    )
    return render_plan, render_payload, safety_metadata


async def _run_render_pass(
    *,
    ctx,
    master_video: str,
    segment_start: float,
    segment_end: float,
    temp_cropped: str,
    quarantine_output: str,
    ass_file: str,
    subtitle_engine,
    render_plan,
    opening_report: dict[str, object],
    cut_as_short: bool,
    require_audio: bool,
    manual_center_x: float | None,
) -> dict[str, object]:
    render_report = await run_blocking(
        ctx._cut_and_burn_clip,
        master_video=master_video,
        start_t=segment_start,
        end_t=segment_end,
        temp_cropped=temp_cropped,
        final_output=quarantine_output,
        ass_file=ass_file,
        subtitle_engine=subtitle_engine,
        layout=render_plan.resolved_layout,
        center_x=manual_center_x,
        initial_slot_centers=resolve_initial_slot_centers(opening_report),
        cut_as_short=cut_as_short,
        require_audio=require_audio,
    )
    return render_report if isinstance(render_report, dict) else {}


def _collect_render_quality_context(
    *,
    compute_render_quality_score,
    merge_transcript_quality,
    project,
    clip_filename: str,
    render_payload: dict[str, object],
    base_transcript_quality,
    snap_report: dict[str, object] | None,
    debug_environment,
) -> dict[str, object]:
    subtitle_layout_quality = render_payload.get("subtitle_layout_quality")
    tracking_quality = render_payload.get("tracking_quality")
    debug_timing = render_payload.get("debug_timing")
    subtitle_layout_dict = _as_dict(subtitle_layout_quality)
    tracking_quality_dict = _as_dict(tracking_quality)
    debug_timing_dict = _as_dict(debug_timing)

    transcript_quality = merge_transcript_quality(
        base_quality=base_transcript_quality,
        subtitle_layout_quality=subtitle_layout_dict,
        snapping_report=snap_report,
    )
    render_quality_score = compute_render_quality_score(
        tracking_quality=tracking_quality_dict,
        transcript_quality=transcript_quality,
        debug_timing=debug_timing_dict,
        subtitle_layout_quality=subtitle_layout_dict,
    )
    debug_artifacts = persist_debug_artifacts(
        project=project,
        clip_name=clip_filename,
        render_report=render_payload or None,
        subtitle_layout_quality=subtitle_layout_dict,
        snap_report=snap_report,
        debug_timing=debug_timing_dict,
    )
    return {
        "subtitle_layout_quality": subtitle_layout_quality,
        "tracking_quality": tracking_quality,
        "debug_timing": debug_timing,
        "transcript_quality": transcript_quality,
        "debug_environment": debug_environment,
        "render_quality_score": render_quality_score,
        "debug_artifacts": debug_artifacts,
        "debug_tracking": render_payload.get("debug_tracking"),
        "audio_validation": render_payload.get("audio_validation"),
    }


def _build_clip_metadata(
    *,
    ctx,
    transcript_data: list,
    segment: dict,
    mode: str,
    clip_filename: str,
    start_time: float,
    end_time: float,
    duration_min: float,
    duration_max: float,
    duration_validation_status: str,
    requested_layout: str,
    render_plan,
    opening_report: dict[str, object],
    safety_metadata: dict[str, object],
    style_name: str,
    animation_type: str,
    resolved_animation_type: str,
    skip_subtitles: bool,
    cut_as_short: bool,
    render_quality_context: dict[str, object],
    analysis_key: str | None = None,
    render_key: str | None = None,
) -> dict:
    render_metadata = {
        "mode": mode,
        "project_id": ctx.project.root.name,
        "clip_name": clip_filename,
        "start_time": start_time,
        "end_time": end_time,
        "requested_duration_min": duration_min,
        "requested_duration_max": duration_max,
        "duration_validation_status": duration_validation_status,
        "crop_mode": "auto",
        "center_x": None,
        "layout": requested_layout,
        "resolved_layout": render_plan.resolved_layout,
        "layout_fallback_reason": render_plan.layout_fallback_reason,
        "layout_auto_fix_applied": safety_metadata["layout_auto_fix_applied"],
        "layout_auto_fix_reason": safety_metadata["layout_auto_fix_reason"],
        "layout_safety_status": safety_metadata["layout_safety_status"],
        "layout_safety_mode": safety_metadata["layout_safety_mode"],
        "layout_safety_contract_version": safety_metadata[
            "layout_safety_contract_version"
        ],
        "scene_class": safety_metadata["scene_class"],
        "speaker_count_peak": safety_metadata["speaker_count_peak"],
        "dominant_speaker_confidence": safety_metadata[
            "dominant_speaker_confidence"
        ],
        "layout_validation_status": opening_report.get("layout_validation_status"),
        "opening_visibility_delay_ms": opening_report.get(
            "opening_visibility_delay_ms"
        ),
        "style_name": style_name,
        "animation_type": animation_type,
        "resolved_animation_type": resolved_animation_type,
        "skip_subtitles": skip_subtitles,
        "cut_as_short": cut_as_short,
        "tracking_quality": render_quality_context["tracking_quality"],
        "transcript_quality": render_quality_context["transcript_quality"],
        "debug_timing": render_quality_context["debug_timing"],
        "debug_tracking": render_quality_context["debug_tracking"],
        "debug_environment": render_quality_context["debug_environment"],
        "render_quality_score": render_quality_context["render_quality_score"],
        "audio_validation": render_quality_context["audio_validation"],
        "subtitle_layout_quality": render_quality_context[
            "subtitle_layout_quality"
        ],
    }
    if analysis_key is not None:
        render_metadata["analysis_key"] = analysis_key
    if render_key is not None:
        render_metadata["render_key"] = render_key
    debug_artifacts = render_quality_context["debug_artifacts"]
    if debug_artifacts:
        render_metadata["debug_artifacts"] = debug_artifacts

    return ctx._build_clip_metadata(
        transcript_data,
        viral_metadata=_build_viral_metadata(segment),
        render_metadata=render_metadata,
    )


def _build_viral_metadata(segment: dict) -> dict[str, object]:
    return {
        "hook_text": segment.get("hook_text", ""),
        "ui_title": segment.get("ui_title", ""),
        "social_caption": segment.get("social_caption", ""),
        "viral_score": segment.get("viral_score", 0),
    }


def _should_hold_for_review(
    *,
    layout_safety_mode: str,
    safety_metadata: dict[str, object],
) -> bool:
    return (
        layout_safety_mode == "enforce"
        and safety_metadata["layout_safety_status"]
        not in SAFE_PUBLIC_LAYOUT_STATUSES
    )


def _build_review_item(
    *,
    segment_index: int,
    segment: dict,
    start_time: float,
    end_time: float,
    requested_layout: str,
    attempted_layout: str,
    safety_metadata: dict[str, object],
) -> dict[str, object]:
    return build_layout_review_item(
        clip_index=segment_index,
        ui_title=str(segment.get("ui_title", "")).strip() or None,
        start_time=start_time,
        end_time=end_time,
        requested_layout=requested_layout,
        attempted_layout=attempted_layout,
        layout_auto_fix_reason=str(
            safety_metadata["layout_auto_fix_reason"]
            or "split_runtime_degraded"
        ),
        suggested_layout="single",
    )


def _raise_for_review_if_needed(
    *,
    ctx,
    review_items: list[dict[str, object]],
    safe_output_paths: list[str],
) -> None:
    if not review_items:
        return
    raise RenderReviewRequiredError(
        "Bazı klipler güvenli olmadığı için manuel inceleme bekliyor.",
        review_items=review_items,
        output_paths=safe_output_paths,
        project_id=ctx.project.root.name if ctx.project is not None else None,
        num_clips=len(safe_output_paths),
    )


def _as_dict(value):
    return value if isinstance(value, dict) else None


__all__ = [
    "apply_opening_validation",
    "render_pipeline_segments",
    "run_cut_points_workflow",
    "render_batch_segments",
]
