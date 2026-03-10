#!/usr/bin/env python3
"""
Klip reburn scripti: mevcut klibe yeni layout ve altyazı stili uygular.
Kullanım: python scripts/reburn_clip.py --project PROJECT_ID --clip CLIP_NAME [--layout split] [--style HORMOZI]
"""
import os
import sys
import json
import argparse
from loguru import logger

# Proje root'unu path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import TEMP_DIR, ProjectPaths
from backend.services.video_processor import VideoProcessor
from backend.services.subtitle_styles import StyleManager
from backend.services.subtitle_renderer import SubtitleRenderer


def reburn_clip(project_id: str, clip_name: str, layout: str = "split", style_name: str = "HORMOZI"):
    project = ProjectPaths(project_id)
    input_video = project.master_video

    # Clip metadata (to get start/end and transcript)
    clip_json = project.outputs / f"{clip_name}.json"
    if not clip_json.exists():
        logger.error(f"Clip metadata not found: {clip_json}")
        return

    with open(clip_json, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # In my orchestrator, personal clips saved as:
    # { "transcript": [], "viral_metadata": { ... } }
    # OR just a list if it was a manual reburn.
    if isinstance(meta, dict) and "transcript" in meta:
        transcript = meta["transcript"]
    else:
        transcript = meta

    # Get start/end from viral.json
    start_t, end_t = 0.0, 60.0  # Default guess
    if project.viral_meta.exists():
        with open(project.viral_meta, "r", encoding="utf-8") as f:
            viral = json.load(f)
        for seg in viral.get("segments", []):
            if "washington" in seg.get("hook_text", "").lower():
                start_t = seg["start_time"]
                end_t = seg["end_time"]
                break

    logger.info(f"Re-burning {clip_name} from {project_id} | {start_t}s - {end_t}s | Layout: {layout}")

    # 1. Video Processing
    vp = VideoProcessor()
    temp_cropped = TEMP_DIR / f"test_reburn_crop_{clip_name}.mp4"
    vp.create_viral_short(
        input_video=str(input_video),
        start_time=start_t,
        end_time=end_t,
        output_filename=str(temp_cropped),
        layout=layout
    )

    # Clean up VideoProcessor to free VRAM
    del vp
    import gc
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # 2. Subtitles
    style = StyleManager.get_preset(style_name)
    renderer = SubtitleRenderer(style=style)

    temp_shifted = TEMP_DIR / f"test_reburn_shifted_{clip_name}.json"
    with open(temp_shifted, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False)

    ass_file = TEMP_DIR / f"test_reburn_{clip_name}.ass"
    renderer.generate_ass_file(str(temp_shifted), str(ass_file))

    final_output = project.outputs / f"{clip_name}_FIXED.mp4"
    renderer.burn_subtitles_to_video(str(temp_cropped), str(ass_file), str(final_output))

    logger.success(f"FIXED video generated: {final_output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--clip", required=True)
    parser.add_argument("--layout", default="split")
    parser.add_argument("--style", default="HORMOZI")
    args = parser.parse_args()

    reburn_clip(args.project, args.clip, args.layout, args.style)
