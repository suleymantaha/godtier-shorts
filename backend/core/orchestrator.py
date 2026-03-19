"""External facade orchestrator for GodTier Shorts workflows."""
from __future__ import annotations
import asyncio
import json
import re
import threading
from typing import Callable, Optional
from loguru import logger
from backend.config import LOGS_DIR, OUTPUTS_DIR, VIDEO_METADATA, YOLO_MODEL_PATH, ProjectPaths
from backend.core.command_runner import CommandRunner
from backend.core.media_ops import cut_and_burn_clip, download_full_video_async as download_video_assets_async, shift_timestamps
from backend.core.workflows import BatchClipWorkflow, CutPointsWorkflow, ManualClipWorkflow, PipelineWorkflow, ReburnWorkflow
from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.transcription import release_whisper_models, run_transcription
from backend.services.video_processor import VideoProcessor
from backend.services.viral_analyzer import ViralAnalyzer
logger.add(str(LOGS_DIR / "orchestrator_{time:YYYY-MM-DD}.log"), rotation="50 MB", retention="10 days", level="DEBUG")
StatusCallback = Callable[[dict], None]
class GodTierShortsCreator:
    def __init__(
        self,
        ui_callback: Optional[StatusCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        subject: Optional[str] = None,
    ):
        logger.info("👑 GOD-TIER SHORTS ORKESTRATÖRÜ BAŞLATILDI 👑")
        self.ui_callback = ui_callback
        self.cancel_event = cancel_event or threading.Event()
        self.subject = subject
        self.project: Optional[ProjectPaths] = None
        self.command_runner = CommandRunner(cancel_event=self.cancel_event)
        self.analyzer = ViralAnalyzer(engine="local")
        self.video_processor = VideoProcessor(model_version=str(YOLO_MODEL_PATH), device="cuda")
    def cleanup_gpu(self) -> None:
        try:
            release_whisper_models()
        except Exception:
            pass
        try:
            self.video_processor.cleanup_gpu()
        except Exception:
            pass
    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise RuntimeError("Job cancelled by user")
    def _validate_youtube_url(self, url: str) -> None:
        if re.match(r"^[0-9A-Za-z_-]{11}$", url):
            return
        youtube_regex = re.compile(
            r"^(https?://)?(www\.)?"
            r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)"
            r"([0-9A-Za-z_-]{11})(&.*)?$"
        )
        if not youtube_regex.match(url):
            raise ValueError(f"Geçersiz veya güvensiz YouTube URL formatı: {url}")
    async def _run_command_with_cancel_async(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ) -> tuple[int, str, str]:
        return await self.command_runner.run_async(cmd, timeout=timeout, error_message=error_message)
    def _run_command_with_cancel(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ):
        """DEPRECATED: retained for backward compatibility."""
        return self.command_runner.run_sync(cmd, timeout=timeout, error_message=error_message)
    @staticmethod
    def _normalize_transcript_payload(transcript_data: list) -> list[dict]:
        normalized: list[dict] = []
        for segment in transcript_data:
            if hasattr(segment, "model_dump"):
                normalized.append(segment.model_dump())
            elif isinstance(segment, dict):
                normalized.append(segment)
            else:
                normalized.append(dict(segment))
        return normalized
    @staticmethod
    def _build_clip_metadata(
        transcript_data: list[dict],
        *,
        viral_metadata: Optional[dict] = None,
        render_metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "transcript": transcript_data,
            "viral_metadata": viral_metadata,
            "render_metadata": render_metadata,
        }

    def _load_project_transcript(self) -> list[dict]:
        if self.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")
        if not self.project.transcript.exists():
            raise FileNotFoundError(f"Transkript bulunamadı: {self.project.transcript}")
        with open(self.project.transcript, "r", encoding="utf-8") as f:
            return json.load(f)

    def _update_status(self, message: str, progress: int) -> None:
        logger.info(f"[{progress}%] ⏳ {message}")
        if self.ui_callback:
            self.ui_callback({"message": message, "progress": progress})

    async def download_full_video_async(
        self,
        url: str,
        project_paths: Optional[ProjectPaths] = None,
        resolution: str = "best",
    ) -> tuple[str, str]:
        return await download_video_assets_async(
            url=url,
            project_paths=project_paths,
            resolution=resolution,
            validate_url=self._validate_youtube_url,
            update_status=self._update_status,
            command_runner=self.command_runner,
        )

    def download_full_video(self, url: str, project_paths: Optional[ProjectPaths] = None, resolution: str = "best") -> tuple[str, str]:
        return self._run_in_new_loop(self.download_full_video_async(url, project_paths, resolution))

    def _shift_timestamps(
        self,
        original_json: str,
        start_time: float,
        end_time: float,
        output_json: str,
    ) -> str:
        return shift_timestamps(original_json, start_time, end_time, output_json)

    def _cut_and_burn_clip(
        self,
        master_video: str,
        start_t: float,
        end_t: float,
        temp_cropped: str,
        final_output: str,
        ass_file: str,
        subtitle_engine: Optional[SubtitleRenderer],
        layout: str = "auto",
        center_x: Optional[float] = None,
        initial_slot_centers: tuple[float, float] | None = None,
        cut_as_short: bool = True,
        require_audio: bool = False,
    ) -> dict:
        return cut_and_burn_clip(
            video_processor=self.video_processor,
            cancel_event=self.cancel_event,
            master_video=master_video,
            start_t=start_t,
            end_t=end_t,
            temp_cropped=temp_cropped,
            final_output=final_output,
            ass_file=ass_file,
            subtitle_engine=subtitle_engine,
            layout=layout,
            center_x=center_x,
            initial_slot_centers=initial_slot_centers,
            cut_as_short=cut_as_short,
            require_audio=require_audio,
        )

    async def run_pipeline_async(
        self,
        youtube_url: str,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        layout: str = "auto",
        skip_subtitles: bool = False,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        resolution: str = "best",
    ) -> None:
        await PipelineWorkflow(self).run(
            youtube_url=youtube_url,
            style_name=style_name,
            animation_type=animation_type,
            layout=layout,
            skip_subtitles=skip_subtitles,
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
            resolution=resolution,
        )

    def run_pipeline(
        self,
        youtube_url: str,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        layout: str = "auto",
        skip_subtitles: bool = False,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        resolution: str = "best",
    ) -> None:
        self._run_in_new_loop(
            self.run_pipeline_async(
                youtube_url,
                style_name,
                animation_type,
                layout,
                skip_subtitles,
                num_clips,
                duration_min,
                duration_max,
                resolution,
            )
        )

    async def run_manual_clip_async(
        self,
        start_t: float,
        end_t: float,
        transcript_data: Optional[list],
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        project_id: Optional[str] = None,
        center_x: Optional[float] = None,
        layout: str = "auto",
        output_name: Optional[str] = None,
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> str:
        return await ManualClipWorkflow(self).run(
            start_t=start_t,
            end_t=end_t,
            transcript_data=transcript_data,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            center_x=center_x,
            layout=layout,
            output_name=output_name,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )

    def run_manual_clip(self, *args, **kwargs) -> str:
        return self._run_in_new_loop(self.run_manual_clip_async(*args, **kwargs))

    async def run_manual_clips_from_cut_points_async(
        self,
        cut_points: list[float],
        transcript_data: list,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
        project_id: Optional[str] = None,
        layout: str = "auto",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        return await CutPointsWorkflow(self).run(
            cut_points=cut_points,
            transcript_data=transcript_data,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            layout=layout,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )

    def run_manual_clips_from_cut_points(self, *args, **kwargs) -> list[str]:
        return self._run_in_new_loop(self.run_manual_clips_from_cut_points_async(*args, **kwargs))

    async def run_batch_manual_clips_async(
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
        layout: str = "auto",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        return await BatchClipWorkflow(self).run(
            start_t=start_t,
            end_t=end_t,
            num_clips=num_clips,
            transcript_data=transcript_data,
            duration_min=duration_min,
            duration_max=duration_max,
            style_name=style_name,
            animation_type=animation_type,
            project_id=project_id,
            layout=layout,
            skip_subtitles=skip_subtitles,
            cut_as_short=cut_as_short,
        )

    def run_batch_manual_clips(self, *args, **kwargs) -> list[str]:
        return self._run_in_new_loop(self.run_batch_manual_clips_async(*args, **kwargs))

    async def reburn_subtitles_async(
        self,
        clip_name: str,
        transcript: list,
        project_id: Optional[str] = None,
        style_name: str = "HORMOZI",
        animation_type: str = "default",
    ) -> str:
        return await ReburnWorkflow(self).run(
            clip_name=clip_name,
            transcript=transcript,
            project_id=project_id,
            style_name=style_name,
            animation_type=animation_type,
        )

    def reburn_subtitles(self, *args, **kwargs) -> str:
        return self._run_in_new_loop(self.reburn_subtitles_async(*args, **kwargs))

    def transcribe_local_video(self, video_path: str) -> list | None:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self._update_status("Ses haritası çıkarılıyor (faster-whisper)...", 20)
        try:
            run_transcription(
                audio_file=video_path,
                output_json=str(VIDEO_METADATA),
                status_callback=lambda msg, pct: self._update_status(f"Transkripsiyon: {msg}", 20 + int(pct * 0.4)),
                cancel_event=self.cancel_event,
            )
        except Exception as exc:
            self._update_status(f"HATA: {exc}", -1)
            return None
        with open(str(VIDEO_METADATA), "r", encoding="utf-8") as f:
            transcript = json.load(f)
        self._update_status("Video ve ses haritası hazır!", 100)
        logger.success("✅ Yerel video başarıyla işlendi.")
        return transcript

    @staticmethod
    def _run_in_new_loop(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        loop.close()
        return result
