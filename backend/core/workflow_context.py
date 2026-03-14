"""Shared protocol contracts for workflow modules."""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional, Protocol

from backend.config import ProjectPaths
from backend.services.subtitle_renderer import SubtitleRenderer


class OrchestratorContext(Protocol):
    ui_callback: Optional[Callable[[dict], None]]
    cancel_event: threading.Event
    project: Optional[ProjectPaths]

    def _check_cancelled(self) -> None:
        ...

    def _validate_youtube_url(self, url: str) -> None:
        ...

    def _update_status(self, message: str, progress: int) -> None:
        ...

    async def _run_command_with_cancel_async(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ) -> tuple[int, str, str]:
        ...

    async def download_full_video_async(
        self,
        url: str,
        project_paths: Optional[ProjectPaths] = None,
        resolution: str = "best",
    ) -> tuple[str, str]:
        ...

    def _shift_timestamps(
        self,
        original_json: str,
        start_time: float,
        end_time: float,
        output_json: str,
    ) -> str:
        ...

    def _cut_and_burn_clip(
        self,
        master_video: str,
        start_t: float,
        end_t: float,
        temp_cropped: str,
        final_output: str,
        ass_file: str,
        subtitle_engine: Optional[SubtitleRenderer],
        layout: str = "single",
        center_x: Optional[float] = None,
        cut_as_short: bool = True,
    ) -> None:
        ...

    @staticmethod
    def _normalize_transcript_payload(transcript_data: list) -> list[dict]:
        ...

    @staticmethod
    def _build_clip_metadata(
        transcript_data: list[dict],
        *,
        viral_metadata: Optional[dict] = None,
        render_metadata: Optional[dict] = None,
    ) -> dict:
        ...

    def _load_project_transcript(self) -> list[dict]:
        ...

    @property
    def analyzer(self) -> Any:
        ...
