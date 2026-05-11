"""Pipeline preparation and upstream asset helpers."""

from __future__ import annotations

import os
import re
import time
from urllib.parse import parse_qs, urlparse

from loguru import logger

from backend.config import ProjectPaths
from backend.core.external_tools import ytdlp as resolve_ytdlp
from backend.core.workflow_common import run_blocking, write_json_atomic

YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[0-9A-Za-z_-]{11}$")


def extract_youtube_video_id(youtube_url: str) -> str | None:
    normalized = str(youtube_url or "").strip()
    if not normalized:
        return None

    if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(normalized):
        return normalized

    parsed = urlparse(normalized)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if host.endswith("youtu.be"):
        candidate = path.strip("/").split("/", 1)[0]
        return candidate if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate) else None

    if "youtube.com" not in host:
        return None

    if path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        return candidate if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate) else None

    path_parts = [part for part in path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live", "v"}:
        candidate = path_parts[1]
        return candidate if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate) else None

    return None


def _pipeline_run_transcription(*args, **kwargs):
    from backend.services.transcription import run_transcription

    return run_transcription(*args, **kwargs)


def _pipeline_release_whisper_models() -> None:
    from backend.services.transcription import release_whisper_models

    release_whisper_models()


async def fetch_youtube_video_id(ctx, youtube_url: str) -> str:
    parsed_video_id = extract_youtube_video_id(youtube_url)
    if parsed_video_id:
        return parsed_video_id

    rc, stdout, stderr = await ctx._run_command_with_cancel_async(
        [resolve_ytdlp(), "--get-id", youtube_url],
        timeout=120,
        error_message="Video ID alma işlemi timeout oldu",
    )
    if rc != 0:
        raise RuntimeError(stderr or "Video ID alınamadı")
    video_id = stdout.strip()
    if not video_id:
        raise RuntimeError("Video ID alınamadı")
    return video_id


async def prepare_pipeline_project(ctx, youtube_url: str) -> ProjectPaths:
    from backend.services.ownership import (
        build_owner_scoped_project_id,
        ensure_project_manifest,
    )

    ctx._update_status("Video ID alınıyor...", 5)
    try:
        video_id = await fetch_youtube_video_id(ctx, youtube_url)
        if ctx.subject:
            project_id = build_owner_scoped_project_id("yt", ctx.subject, video_id)
            project = ProjectPaths(project_id)
            ensure_project_manifest(
                project.root.name,
                owner_subject=ctx.subject,
                source="youtube",
            )
        else:
            project = ProjectPaths(f"yt_{video_id}")
        logger.info(f"📁 Proje klasörü: {project.root}")
        return project
    except Exception as exc:
        logger.error(f"Video ID alınamadı: {exc}")
        if ctx.subject:
            fallback_id = build_owner_scoped_project_id(
                "fallback",
                ctx.subject,
                str(int(time.time())),
            )
            ensure_project_manifest(
                fallback_id,
                owner_subject=ctx.subject,
                source="youtube_fallback",
            )
            return ProjectPaths(fallback_id)
        return ProjectPaths(f"fallback_{int(time.time())}")


async def ensure_pipeline_master_assets(
    ctx,
    youtube_url: str,
    resolution: str,
) -> tuple[str, str]:
    from backend.core.media_ops import extract_audio_async

    if ctx.project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    master_video = str(ctx.project.master_video)
    master_audio = str(ctx.project.master_audio)
    if os.path.exists(master_video):
        if not os.path.exists(master_audio):
            ctx._update_status("✅ Video bulundu, ses izi yeniden çıkarılıyor...", 20)
            await extract_audio_async(
                video_file=master_video,
                audio_file=master_audio,
                update_status=ctx._update_status,
                command_runner=ctx.command_runner,
            )
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
    project = ctx.project
    if project is None:
        raise RuntimeError("Proje bağlamı bulunamadı.")

    metadata_file = str(project.transcript)
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
            output_json=str(project.transcript),
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
    if not viral_results["segments"]:
        logger.error("❌ Süre/layout kontratını karşılayan viral segment bulunamadı!")
        ctx._update_status("HATA: İstenen süre aralığında uygun segment bulunamadı.", -1)
        raise RuntimeError("İstenen süre aralığında uygun segment bulunamadı.")

    enriched_results = {
        **viral_results,
        "requested_duration_min": duration_min,
        "requested_duration_max": duration_max,
    }
    write_json_atomic(ctx.project.viral_meta, enriched_results, indent=4)
    return enriched_results


__all__ = [
    "extract_youtube_video_id",
    "fetch_youtube_video_id",
    "prepare_pipeline_project",
    "ensure_pipeline_master_assets",
    "ensure_pipeline_transcript",
    "analyze_pipeline_segments",
]
