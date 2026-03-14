"""Manual clip workflows (single + cut-points)."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Optional

from backend.config import TEMP_DIR
from backend.core.workflow_context import OrchestratorContext
from backend.core.workflow_helpers import TempArtifactManager
from backend.core.workflow_runtime import create_subtitle_renderer, resolve_project_master_video
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
        project_id: Optional[str] = None,
        center_x: Optional[float] = None,
        layout: str = "single",
        output_name: Optional[str] = None,
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> str:
        self.ctx.project, master_video = resolve_project_master_video(project_id, generated_prefix="manual")
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

        with TempArtifactManager(temp_json, shifted_json, temp_cropped) as artifacts:
            if not skip_subtitles:
                artifacts.add(ass_file)

            with open(temp_json, "w", encoding="utf-8") as f:
                json.dump(normalized_transcript, f, ensure_ascii=False, indent=4)

            self.ctx._shift_timestamps(temp_json, start_t, end_t, shifted_json)

            subtitle_engine: Optional[SubtitleRenderer] = None
            if not skip_subtitles:
                subtitle_engine = create_subtitle_renderer(style_name)
                subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

            await asyncio.to_thread(
                self.ctx._cut_and_burn_clip,
                master_video,
                start_t,
                end_t,
                temp_cropped,
                final_output,
                ass_file,
                subtitle_engine,
                layout,
                center_x,
                cut_as_short,
            )

            meta_path = final_output.replace(".mp4", ".json")
            with open(shifted_json, "r", encoding="utf-8") as f:
                shifted_transcript = json.load(f)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.ctx._build_clip_metadata(
                        shifted_transcript,
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
                            "style_name": style_name,
                            "cut_as_short": cut_as_short,
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
        project_id: Optional[str] = None,
        layout: str = "single",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        if len(cut_points) < 2:
            return []

        results: list[str] = []
        total = len(cut_points) - 1
        manual_workflow = ManualClipWorkflow(self.ctx)

        for i in range(total):
            self.ctx._check_cancelled()
            start_t = cut_points[i]
            end_t = cut_points[i + 1]
            if end_t <= start_t:
                continue

            clip_num = i + 1
            pct = 10 + int((i / total) * 85)
            self.ctx._update_status(f"Klip {clip_num}/{total}: {start_t:.1f}-{end_t:.1f} sn...", pct)
            output_name = f"cut_{clip_num}_{int(start_t)}_{int(end_t)}.mp4"

            path = await manual_workflow.run(
                start_t=start_t,
                end_t=end_t,
                transcript_data=transcript_data,
                style_name=style_name,
                project_id=project_id,
                center_x=None,
                layout=layout,
                output_name=output_name,
                skip_subtitles=skip_subtitles,
                cut_as_short=cut_as_short,
            )
            results.append(path)

        self.ctx._update_status("Tüm kesim noktaları işlendi!", 100)
        return results
