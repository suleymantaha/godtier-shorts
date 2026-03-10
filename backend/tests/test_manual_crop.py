"""
backend/tests/test_manual_crop.py
==================================
Manual crop (manual_center_x) için integration testi.
master.mp4 gerektirir - yoksa skip edilir.
"""
import os

import pytest

from backend.config import PROJECTS_DIR, TEMP_DIR
from backend.services.video_processor import VideoProcessor


@pytest.mark.integration
def test_manual_crop():
    """manual_center_x ile crop işlemi çalışmalı."""
    master_video = None
    for p in PROJECTS_DIR.iterdir():
        if p.is_dir() and (p / "master.mp4").exists():
            master_video = str(p / "master.mp4")
            break

    if not master_video:
        pytest.skip("master.mp4 bulunamadı (workspace/projects/*/master.mp4)")

    processor = VideoProcessor()
    output = str(TEMP_DIR / "test_manual_crop_output.mp4")

    processor.create_viral_short(
        input_video=master_video,
        start_time=0,
        end_time=2,
        output_filename=output,
        manual_center_x=0.2,
    )
    assert os.path.exists(output), "Çıktı dosyası oluşturulmalı"
    os.remove(output)
