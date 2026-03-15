"""Shared helpers for orchestrator workflow modules."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Optional

from backend.config import ProjectPaths, TEMP_DIR
from loguru import logger


@dataclass(frozen=True)
class ProgressStepMapper:
    """Maps iterative steps into a bounded progress range."""

    start: int
    end: int
    total_steps: int

    def map(self, step_index: int) -> int:
        if self.total_steps <= 0:
            return self.end
        bounded = min(max(step_index, 0), self.total_steps)
        delta = self.end - self.start
        return self.start + int((bounded / self.total_steps) * delta)


class TempArtifactManager:
    """Tracks temporary file paths and removes them on context exit."""

    def __init__(self, *paths: str):
        self._paths = [p for p in paths if p]

    def add(self, path: Optional[str]) -> None:
        if path:
            self._paths.append(path)

    def cleanup(self) -> None:
        for path in self._paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("Geçici dosya silinemedi: {} - {}", path, exc)

    def __enter__(self) -> "TempArtifactManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


def build_hook_slug(hook: str, *, max_length: int) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", hook).strip().lower().replace(" ", "_")
    return cleaned[:max_length]


async def run_blocking(func, /, *args, **kwargs):
    """Run a blocking callable inline in tests, otherwise offload to a worker thread."""
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("WORKFLOW_INLINE_BLOCKING") == "1":
        return func(*args, **kwargs)
    return await asyncio.to_thread(partial(func, *args, **kwargs))


def write_json_atomic(path: str | Path, payload: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def move_file_atomic(source: str | Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(source), str(destination))


def persist_debug_artifacts(
    *,
    project: ProjectPaths,
    clip_name: str,
    render_report: dict | None,
    subtitle_layout_quality: dict | None,
    snap_report: dict | None,
    debug_timing: dict | None,
) -> dict | None:
    if os.getenv("DEBUG_RENDER_ARTIFACTS") != "1":
        return None

    clip_stem = Path(clip_name).stem
    debug_dir = project.debug / clip_stem
    render_report = render_report if isinstance(render_report, dict) else {}
    subtitle_layout_quality = subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else {}
    tracking_payload = render_report.get("debug_tracking")
    chunk_payload = subtitle_layout_quality.get("chunk_dump", [])
    snap_payload = snap_report if isinstance(snap_report, dict) else {"enabled": False, "reason": "not_applicable"}
    timing_payload = debug_timing if isinstance(debug_timing, dict) else {}
    overlay_source = render_report.get("debug_overlay_temp_path")
    status = "complete"
    preferred_status = str(render_report.get("debug_artifacts_status", "complete") or "complete")
    if preferred_status == "partial":
        status = "partial"

    artifacts: dict[str, str] = {}
    try:
        write_json_atomic(debug_dir / "tracking_timeline.json", tracking_payload or {})
        artifacts["tracking_timeline"] = _project_relative_path(project, debug_dir / "tracking_timeline.json")
    except Exception as exc:
        logger.warning("Tracking timeline artifact yazilamadi: {} - {}", clip_name, exc)
        status = "partial"

    try:
        write_json_atomic(debug_dir / "subtitle_chunks.json", chunk_payload if isinstance(chunk_payload, list) else [])
        artifacts["subtitle_chunks"] = _project_relative_path(project, debug_dir / "subtitle_chunks.json")
    except Exception as exc:
        logger.warning("Subtitle chunk artifact yazilamadi: {} - {}", clip_name, exc)
        status = "partial"

    try:
        write_json_atomic(debug_dir / "boundary_snap.json", snap_payload)
        artifacts["boundary_snap"] = _project_relative_path(project, debug_dir / "boundary_snap.json")
    except Exception as exc:
        logger.warning("Boundary snap artifact yazilamadi: {} - {}", clip_name, exc)
        status = "partial"

    try:
        write_json_atomic(debug_dir / "timing_report.json", timing_payload)
        artifacts["timing_report"] = _project_relative_path(project, debug_dir / "timing_report.json")
    except Exception as exc:
        logger.warning("Timing artifact yazilamadi: {} - {}", clip_name, exc)
        status = "partial"

    if overlay_source and Path(str(overlay_source)).exists():
        try:
            destination = debug_dir / "tracking_overlay.mp4"
            move_file_atomic(str(overlay_source), destination)
            artifacts["tracking_overlay"] = _project_relative_path(project, destination)
        except Exception as exc:
            logger.warning("Tracking overlay artifact tasinamadi: {} - {}", clip_name, exc)
            status = "partial"
    else:
        status = "partial"

    artifacts["status"] = status
    return artifacts


def _project_relative_path(project: ProjectPaths, path: Path) -> str:
    return path.relative_to(project.root).as_posix()


def load_json_dict(path: str | Path) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else None


def write_reburn_metadata(
    *,
    ctx,
    meta_path: str,
    transcript: list,
    existing_metadata: dict | None,
    existing_render_metadata: dict | None,
    style_name: str,
    animation_type: str,
    resolved_animation_type: str,
    resolved_layout: str,
    layout_fallback_reason: str | None,
    transcript_quality: dict,
    subtitle_layout_quality: dict,
    debug_environment: dict,
    render_quality_score: float,
    debug_artifacts: dict | None,
) -> None:
    merged_metadata = ctx._build_clip_metadata(
        transcript,
        viral_metadata=(existing_metadata or {}).get("viral_metadata"),
        render_metadata=(existing_metadata or {}).get("render_metadata"),
    )
    render_metadata = merged_metadata.get("render_metadata")
    if not isinstance(render_metadata, dict):
        render_metadata = {}
        merged_metadata["render_metadata"] = render_metadata

    render_metadata["style_name"] = style_name
    render_metadata["animation_type"] = animation_type
    render_metadata["resolved_animation_type"] = resolved_animation_type
    render_metadata["resolved_layout"] = resolved_layout
    render_metadata["layout_fallback_reason"] = layout_fallback_reason
    render_metadata["transcript_quality"] = transcript_quality
    render_metadata["subtitle_layout_quality"] = subtitle_layout_quality
    render_metadata["debug_environment"] = debug_environment
    render_metadata["render_quality_score"] = render_quality_score

    debug_timing = existing_render_metadata.get("debug_timing") if isinstance(existing_render_metadata, dict) else None
    if isinstance(debug_timing, dict):
        render_metadata["debug_timing"] = debug_timing
    tracking_quality = existing_render_metadata.get("tracking_quality") if isinstance(existing_render_metadata, dict) else None
    if isinstance(tracking_quality, dict):
        render_metadata["tracking_quality"] = tracking_quality
    audio_validation = existing_render_metadata.get("audio_validation") if isinstance(existing_render_metadata, dict) else None
    if isinstance(audio_validation, dict):
        render_metadata["audio_validation"] = audio_validation
    debug_tracking = existing_render_metadata.get("debug_tracking") if isinstance(existing_render_metadata, dict) else None
    if isinstance(debug_tracking, dict):
        render_metadata["debug_tracking"] = debug_tracking
    if debug_artifacts:
        render_metadata["debug_artifacts"] = debug_artifacts

    write_json_atomic(Path(meta_path), merged_metadata)


def _pipeline_run_transcription(*args, **kwargs):
    from backend.services.transcription import run_transcription

    return run_transcription(*args, **kwargs)


def _pipeline_release_whisper_models() -> None:
    from backend.services.transcription import release_whisper_models

    release_whisper_models()


async def prepare_pipeline_project(ctx, youtube_url: str) -> ProjectPaths:
    from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest

    ctx._update_status("Video ID alınıyor...", 5)
    try:
        rc, stdout, stderr = await ctx._run_command_with_cancel_async(
            ["yt-dlp", "--get-id", youtube_url],
            timeout=120,
            error_message="Video ID alma işlemi timeout oldu",
        )
        if rc != 0:
            raise RuntimeError(stderr or "Video ID alınamadı")
        video_id = stdout.strip()
        if ctx.subject:
            project = ProjectPaths(build_owner_scoped_project_id("yt", ctx.subject, video_id))
            ensure_project_manifest(project.root.name, owner_subject=ctx.subject, source="youtube")
        else:
            project = ProjectPaths(f"yt_{video_id}")
        logger.info(f"📁 Proje klasörü: {project.root}")
        return project
    except Exception as exc:
        logger.error(f"Video ID alınamadı: {exc}")
        if ctx.subject:
            fallback_id = build_owner_scoped_project_id("fallback", ctx.subject, str(int(time.time())))
            ensure_project_manifest(fallback_id, owner_subject=ctx.subject, source="youtube_fallback")
            return ProjectPaths(fallback_id)
        return ProjectPaths(f"fallback_{int(time.time())}")


async def ensure_pipeline_master_assets(ctx, youtube_url: str, resolution: str) -> tuple[str, str]:
    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    master_video = str(ctx.project.master_video)
    master_audio = str(ctx.project.master_audio)
    if os.path.exists(master_video):
        ctx._update_status("✅ Video kütüphanede bulundu, indirme atlanıyor.", 25)
        logger.info(f"♻️ Video zaten mevcut: {master_video}")
        return master_video, master_audio

    ctx._check_cancelled()
    ctx._update_status("Orijinal video indiriliyor...", 10)
    try:
        return await ctx.download_full_video_async(youtube_url, ctx.project, resolution)
    except RuntimeError as exc:
        logger.error(f"Pipeline durduruldu: {exc}")
        ctx._update_status(f"HATA: {exc}", -1)
        raise


async def ensure_pipeline_transcript(ctx, master_audio: str) -> str:
    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    metadata_file = str(ctx.project.transcript)
    if os.path.exists(metadata_file):
        ctx._update_status("✅ Transkript kütüphanede bulundu, analiz atlanıyor.", 45)
        logger.info(f"♻️ Transkript zaten mevcut: {metadata_file}")
        return metadata_file

    ctx._check_cancelled()
    ctx._update_status("faster-whisper ses haritası çıkarıyor...", 30)
    try:
        metadata_file = await run_blocking(
            _pipeline_run_transcription,
            audio_file=master_audio,
            output_json=str(ctx.project.transcript),
            status_callback=lambda msg, pct: ctx._update_status(msg, pct),
            cancel_event=ctx.cancel_event,
        )
        await run_blocking(_pipeline_release_whisper_models)
        return metadata_file
    except Exception as exc:
        logger.error(f"❌ faster-whisper hatası: {exc}")
        ctx._update_status(f"faster-whisper hatası: {exc}", -1)
        raise RuntimeError(f"faster-whisper hatası: {exc}") from exc


async def analyze_pipeline_segments(
    ctx,
    metadata_file: str,
    *,
    num_clips: int,
    duration_min: float,
    duration_max: float,
) -> dict:
    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    ctx._update_status("LLM viral klipleri seçiyor...", 50)
    ctx._check_cancelled()
    viral_results = await run_blocking(
        ctx.analyzer.analyze_metadata,
        metadata_file,
        num_clips=num_clips,
        duration_min=duration_min,
        duration_max=duration_max,
        ui_callback=ctx.ui_callback,
        cancel_event=ctx.cancel_event,
    )
    if not viral_results or "segments" not in viral_results:
        logger.error("❌ LLM viral kısım bulamadı!")
        ctx._update_status("HATA: Viral klip secimi basarisiz.", -1)
        raise RuntimeError("Viral klip seçimi başarısız oldu.")

    with open(ctx.project.viral_meta, "w", encoding="utf-8") as handle:
        json.dump(viral_results, handle, ensure_ascii=False, indent=4)
    return viral_results


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
) -> None:
    from backend.core.media_ops import shift_timestamps_with_report
    from backend.core.render_quality import (
        build_debug_environment,
        compute_render_quality_score,
        merge_transcript_quality,
    )
    from backend.core.subtitle_timing import snap_segment_boundaries
    from backend.core.workflow_runtime import create_subtitle_renderer, resolve_subtitle_render_plan
    from backend.services.subtitle_styles import StyleManager

    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    total = len(segments)
    with open(metadata_file, "r", encoding="utf-8") as transcript_handle:
        source_transcript = json.load(transcript_handle)
    debug_environment = build_debug_environment(
        model_identifier=os.path.basename(str(ctx.video_processor._model_path)),
        model_path=str(ctx.video_processor._model_path),
    )
    ctx._update_status(f"{total} adet viral short üretimine başlandı!", 60)
    progress = ProgressStepMapper(start=60, end=95, total_steps=total)

    for idx, seg in enumerate(segments):
        ctx._check_cancelled()
        clip_num = idx + 1
        start_t, end_t = seg["start_time"], seg["end_time"]
        start_t, end_t, snap_report = snap_segment_boundaries(source_transcript, start_t, end_t)
        clip_name = f"short_{clip_num}_{build_hook_slug(seg.get('hook_text', ''), max_length=30)}"
        clip_filename = f"{clip_name}.mp4"
        logger.info(f"🎬 Klip {clip_num}/{total} kurgulanıyor: {clip_name}")

        render_pct = progress.map(idx)
        ctx._update_status(
            f"Klip {clip_num}/{total} hazırlanıyor: {seg.get('ui_title', 'Viral Klip')}...",
            render_pct,
        )

        shifted_json = str(TEMP_DIR / f"shifted_{clip_num}.json")
        ass_file = str(TEMP_DIR / f"subs_{clip_num}.ass")
        temp_cropped = str(TEMP_DIR / f"cropped_{clip_num}.mp4")
        final_output = str(ctx.project.outputs / clip_filename)
        render_plan = resolve_subtitle_render_plan(
            video_processor=ctx.video_processor,
            source_video=master_video,
            start_t=start_t,
            end_t=end_t,
            requested_layout=layout,
            cut_as_short=True,
            manual_center_x=None,
        )
        resolved_style = StyleManager.resolve_style(style_name, animation_type)
        subtitle_engine = None if skip_subtitles else create_subtitle_renderer(
            style_name,
            animation_type=animation_type,
            canvas_width=render_plan.canvas_width,
            canvas_height=render_plan.canvas_height,
            layout=render_plan.resolved_layout,
        )

        with TempArtifactManager(shifted_json, ass_file) as artifacts:
            if temp_cropped != final_output:
                artifacts.add(temp_cropped)

            if not skip_subtitles and subtitle_engine is not None:
                ctx._update_status(f"Klip {clip_num}/{total} - Altyazılar oluşturuluyor...", render_pct + 1)
            shift_report = shift_timestamps_with_report(metadata_file, start_t, end_t, shifted_json)
            transcript_data = shift_report["segments"]
            if not skip_subtitles and subtitle_engine is not None:
                subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

            ctx._update_status(f"Klip {clip_num}/{total} - Video kesiliyor (YOLO + NVENC)...", render_pct + 2)
            if not skip_subtitles and subtitle_engine is not None:
                ctx._update_status(f"Klip {clip_num}/{total} - Altyazılar videoya gömülüyor...", render_pct + 3)

            render_report = await run_blocking(
                ctx._cut_and_burn_clip,
                master_video,
                start_t,
                end_t,
                temp_cropped,
                final_output,
                ass_file,
                subtitle_engine,
                layout=render_plan.resolved_layout,
                center_x=None,
                cut_as_short=True,
                require_audio=True,
            )
            if isinstance(render_report, dict):
                artifacts.add(render_report.get("debug_overlay_temp_path"))

            subtitle_layout_quality = render_report.get("subtitle_layout_quality") if isinstance(render_report, dict) else None
            transcript_quality = merge_transcript_quality(
                base_quality=shift_report.get("transcript_quality"),
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snapping_report=snap_report,
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
                project=ctx.project,
                clip_name=clip_filename,
                render_report=render_report if isinstance(render_report, dict) else None,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snap_report=snap_report,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
            )
            clip_full_metadata = ctx._build_clip_metadata(
                transcript_data,
                viral_metadata={
                    "hook_text": seg.get("hook_text", ""),
                    "ui_title": seg.get("ui_title", ""),
                    "social_caption": seg.get("social_caption", ""),
                    "viral_score": seg.get("viral_score", 0),
                },
                render_metadata={
                    "mode": "pipeline_auto",
                    "project_id": ctx.project.root.name,
                    "clip_name": clip_filename,
                    "start_time": start_t,
                    "end_time": end_t,
                    "crop_mode": "auto",
                    "center_x": None,
                    "layout": layout,
                    "resolved_layout": render_plan.resolved_layout,
                    "layout_fallback_reason": render_plan.layout_fallback_reason,
                    "style_name": style_name,
                    "animation_type": animation_type,
                    "resolved_animation_type": resolved_style.animation_type,
                    "skip_subtitles": skip_subtitles,
                    "cut_as_short": True,
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
            )
            with open(final_output.replace(".mp4", ".json"), "w", encoding="utf-8") as handle:
                json.dump(clip_full_metadata, handle, ensure_ascii=False, indent=4)


async def run_cut_points_workflow(
    ctx,
    *,
    cut_points: list[float],
    transcript_data: list,
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
    total = len(cut_points) - 1
    manual_workflow = ManualClipWorkflow(ctx)

    for index in range(total):
        ctx._check_cancelled()
        start_t = cut_points[index]
        end_t = cut_points[index + 1]
        if end_t <= start_t:
            continue

        clip_num = index + 1
        pct = 10 + int((index / total) * 85)
        ctx._update_status(f"Klip {clip_num}/{total}: {start_t:.1f}-{end_t:.1f} sn...", pct)
        output_name = f"cut_{clip_num}_{int(start_t)}_{int(end_t)}.mp4"
        path = await manual_workflow.run(
            start_t=start_t,
            end_t=end_t,
            transcript_data=transcript_data,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            center_x=None,
            layout=layout,
            output_name=output_name,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )
        results.append(path)

    ctx._update_status("Tüm kesim noktaları işlendi!", 100)
    return results


async def render_batch_segments(
    ctx,
    segments: list[dict],
    *,
    transcript_data: list,
    master_video: str,
    style_name: str,
    animation_type: str,
    layout: str,
    skip_subtitles: bool,
    cut_as_short: bool,
) -> list[tuple[str, float, int]]:
    from backend.core.media_ops import build_shifted_transcript_segments_with_report
    from backend.core.render_quality import (
        build_debug_environment,
        compute_render_quality_score,
        merge_transcript_quality,
    )
    from backend.core.subtitle_timing import snap_segment_boundaries
    from backend.core.workflow_runtime import create_subtitle_renderer, resolve_subtitle_render_plan
    from backend.services.subtitle_styles import StyleManager
    from backend.services.subtitle_renderer import SubtitleRenderer

    total = len(segments)
    progress = ProgressStepMapper(start=30, end=95, total_steps=total)
    results: list[tuple[str, float, int]] = []
    debug_environment = None
    if getattr(ctx, "video_processor", None) is not None:
        debug_environment = build_debug_environment(
            model_identifier=os.path.basename(str(ctx.video_processor._model_path)),
            model_path=str(ctx.video_processor._model_path),
        )

    for idx, seg in enumerate(segments):
        ctx._check_cancelled()
        clip_num = idx + 1
        s_t, e_t, snap_report = snap_segment_boundaries(transcript_data, seg["start_time"], seg["end_time"])
        clip_name = f"batch_{clip_num}_{build_hook_slug(seg.get('hook_text', ''), max_length=25)}"
        clip_filename = f"{clip_name}.mp4"
        render_pct = progress.map(idx)
        ctx._update_status(f"Klip {clip_num}/{total} hazırlanıyor: {seg.get('ui_title', 'Viral Klip')}...", render_pct)

        shifted_json = str(TEMP_DIR / f"batch_s_{clip_num}.json")
        ass_file = str(TEMP_DIR / f"batch_a_{clip_num}.ass")
        temp_cropped = str(TEMP_DIR / f"batch_c_{clip_num}.mp4")
        temp_orig = str(TEMP_DIR / f"orig_{clip_num}.json")
        if ctx.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")
        final_output = str(ctx.project.outputs / clip_filename)

        render_plan = resolve_subtitle_render_plan(
            video_processor=ctx.video_processor,
            source_video=master_video,
            start_t=s_t,
            end_t=e_t,
            requested_layout=layout,
            cut_as_short=cut_as_short,
            manual_center_x=None,
        )
        resolved_style = StyleManager.resolve_style(style_name, animation_type)
        subtitle_engine: SubtitleRenderer | None = None
        if not skip_subtitles:
            subtitle_engine = create_subtitle_renderer(
                style_name,
                animation_type=animation_type,
                canvas_width=render_plan.canvas_width,
                canvas_height=render_plan.canvas_height,
                layout=render_plan.resolved_layout,
            )

        with TempArtifactManager(temp_orig, shifted_json) as artifacts:
            if subtitle_engine is not None:
                artifacts.add(ass_file)
                artifacts.add(temp_cropped)

            with open(temp_orig, "w", encoding="utf-8") as handle:
                json.dump(transcript_data, handle, ensure_ascii=False)
            shifted_segments, shifted_quality = build_shifted_transcript_segments_with_report(transcript_data, s_t, e_t)
            with open(shifted_json, "w", encoding="utf-8") as shifted_handle:
                json.dump(shifted_segments, shifted_handle, ensure_ascii=False, indent=4)
            if subtitle_engine is not None:
                subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

            ctx._update_status(f"Klip {clip_num}/{total} - Video kesiliyor...", render_pct + 1)
            if subtitle_engine is not None:
                ctx._update_status(f"Klip {clip_num}/{total} - Altyazılar basılıyor...", render_pct + 2)

            render_report = await run_blocking(
                ctx._cut_and_burn_clip,
                master_video,
                s_t,
                e_t,
                temp_cropped,
                final_output,
                ass_file,
                subtitle_engine,
                render_plan.resolved_layout,
                None,
                cut_as_short,
                False,
            )
            if isinstance(render_report, dict):
                artifacts.add(render_report.get("debug_overlay_temp_path"))

            subtitle_layout_quality = render_report.get("subtitle_layout_quality") if isinstance(render_report, dict) else None
            transcript_quality = merge_transcript_quality(
                base_quality=shifted_quality,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snapping_report=snap_report,
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
                project=ctx.project,
                clip_name=clip_filename,
                render_report=render_report if isinstance(render_report, dict) else None,
                subtitle_layout_quality=subtitle_layout_quality if isinstance(subtitle_layout_quality, dict) else None,
                snap_report=snap_report,
                debug_timing=debug_timing if isinstance(debug_timing, dict) else None,
            )
            clip_meta = ctx._build_clip_metadata(
                shifted_segments,
                viral_metadata={
                    "hook_text": seg.get("hook_text", ""),
                    "ui_title": seg.get("ui_title", ""),
                    "social_caption": seg.get("social_caption", ""),
                    "viral_score": seg.get("viral_score", 0),
                },
                render_metadata={
                    "mode": "batch_auto",
                    "project_id": ctx.project.root.name,
                    "clip_name": clip_filename,
                    "start_time": s_t,
                    "end_time": e_t,
                    "crop_mode": "auto",
                    "center_x": None,
                    "layout": layout,
                    "resolved_layout": render_plan.resolved_layout,
                    "layout_fallback_reason": render_plan.layout_fallback_reason,
                    "style_name": style_name,
                    "animation_type": animation_type,
                    "resolved_animation_type": resolved_style.animation_type,
                    "skip_subtitles": skip_subtitles,
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
            )
            with open(final_output.replace(".mp4", ".json"), "w", encoding="utf-8") as handle:
                json.dump(clip_meta, handle, ensure_ascii=False, indent=4)
            results.append((final_output, render_quality_score, idx))

    return results
