"""Subtitle reburn workflow implementation."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Optional

from loguru import logger

from backend.config import TEMP_DIR
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import TempArtifactManager
from backend.core.workflow_runtime import create_subtitle_renderer, resolve_output_video_path


class ReburnWorkflow:
    def __init__(self, ctx: OrchestratorContext):
        self.ctx = ctx

    async def run(
        self,
        clip_name: str,
        transcript: list,
        project_id: Optional[str] = None,
        style_name: str = "HORMOZI",
    ) -> str:
        input_video = self._resolve_input_video(clip_name, project_id)
        if not os.path.exists(input_video):
            raise FileNotFoundError(f"Video bulunamadı: {input_video}")

        raw_video = input_video.replace(".mp4", "_raw.mp4")
        source_video = raw_video if os.path.exists(raw_video) else input_video
        if source_video == raw_video:
            logger.info(f"♻️ Ham video kullanılıyor (çift altyazı önlenir): {raw_video}")

        temp_output = input_video.replace(".mp4", "_temp_reburn.mp4")
        ass_file = str(TEMP_DIR / f"{clip_name.replace('.mp4', '')}.ass")

        self.ctx._update_status("Altyazı haritası güncelleniyor...", 30)
        subtitle_engine = create_subtitle_renderer(style_name)
        normalized_transcript = self.ctx._normalize_transcript_payload(transcript)

        temp_json = str(TEMP_DIR / f"reburn_{int(time.time())}.json")
        with TempArtifactManager(temp_json, ass_file) as _artifacts:
            with open(temp_json, "w", encoding="utf-8") as f:
                json.dump(normalized_transcript, f, ensure_ascii=False, indent=4)

            subtitle_engine.generate_ass_file(temp_json, ass_file, max_words_per_screen=3)

            self.ctx._update_status("Videonun makyajı tazeleniyor...", 60)
            await asyncio.to_thread(
                subtitle_engine.burn_subtitles_to_video,
                source_video,
                ass_file,
                temp_output,
                cancel_event=self.ctx.cancel_event,
            )

        os.replace(temp_output, input_video)

        meta_path = input_video.replace(".mp4", ".json")
        existing_metadata = self._load_existing_metadata(meta_path)

        with open(meta_path, "w", encoding="utf-8") as f:
            merged_metadata = self.ctx._build_clip_metadata(
                normalized_transcript,
                viral_metadata=(existing_metadata or {}).get("viral_metadata"),
                render_metadata=(existing_metadata or {}).get("render_metadata"),
            )
            if isinstance(merged_metadata.get("render_metadata"), dict):
                merged_metadata["render_metadata"]["style_name"] = style_name
            json.dump(merged_metadata, f, ensure_ascii=False, indent=4)

        self.ctx._update_status("Klip başarıyla güncellendi!", 100)
        return input_video

    @staticmethod
    def _resolve_input_video(clip_name: str, project_id: Optional[str]) -> str:
        return resolve_output_video_path(clip_name, project_id)

    @staticmethod
    def _load_existing_metadata(meta_path: str) -> Optional[dict]:
        if not os.path.exists(meta_path):
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            return loaded
        return None
