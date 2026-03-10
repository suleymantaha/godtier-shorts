"""
backend/tests/test_raw_video_saved.py
======================================
run_manual_clip çağrıldığında _raw.mp4 (ham video) kaydedildiğini doğrular.
Reburn için gerekli.
"""
import os
from pathlib import Path

import pytest

from backend.config import PROJECTS_DIR
from backend.core.orchestrator import GodTierShortsCreator


@pytest.mark.skipif(
    not (PROJECTS_DIR / "yt_ZPkqcNHz2BM" / "master.mp4").exists(),
    reason="Test projesi yok (yt_ZPkqcNHz2BM/master.mp4)",
)
def test_run_manual_clip_saves_raw_video():
    """Proje modunda klip kesildiğinde _raw.mp4 kaydedilmeli."""
    project_id = "yt_ZPkqcNHz2BM"
    master = PROJECTS_DIR / project_id / "master.mp4"
    if not master.exists():
        pytest.skip("master.mp4 yok")

    transcript = [
        {"text": "Test", "start": 1.0, "end": 2.5, "speaker": "A", "words": []},
    ]
    # Kısa aralık, cut_as_short=False → sadece ffmpeg cut (YOLO yok, hızlı)
    creator = GodTierShortsCreator(ui_callback=None)
    output_path = creator.run_manual_clip(
        start_t=1.0,
        end_t=3.0,
        transcript_data=transcript,
        style_name="HORMOZI",
        project_id=project_id,
        center_x=None,
        layout="single",
        output_name="test_raw_check.mp4",
        skip_subtitles=False,
        cut_as_short=False,
    )

    raw_path = output_path.replace(".mp4", "_raw.mp4")
    assert os.path.exists(raw_path), f"_raw.mp4 kaydedilmedi: {raw_path}"
    assert os.path.getsize(raw_path) > 0, "_raw.mp4 boş"

    # Temizlik
    for p in [output_path, raw_path, output_path.replace(".mp4", ".json")]:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
