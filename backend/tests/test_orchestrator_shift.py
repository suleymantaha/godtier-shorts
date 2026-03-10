"""
backend/tests/test_orchestrator_shift.py
=========================================
_shift_timestamps için unit testler.
Segment/kelime sınır taşması (clamp) doğrulaması.
"""
import json
import tempfile
from pathlib import Path

import pytest

from backend.core.orchestrator import GodTierShortsCreator


class TestShiftTimestamps:
    """_shift_timestamps clamp ve sınır davranışı."""

    def test_word_end_clamped_to_duration(self):
        """Klibi aşan segmentlerde we ve new_end duration'a clamp edilmeli."""
        # Segment: 8-15 sn, klip: 10-12 sn (duration=2)
        # Kelime 11-14 sn → shifted: 1-4 sn ama duration=2, we=4 olmamalı
        data = [
            {
                "text": "test kelime",
                "start": 8.0,
                "end": 15.0,
                "speaker": "A",
                "words": [
                    {"word": "test", "start": 8.0, "end": 10.5, "score": 1.0},
                    {"word": "kelime", "start": 10.5, "end": 14.0, "score": 1.0},
                ],
            }
        ]
        start_t, end_t = 10.0, 12.0
        duration = end_t - start_t  # 2.0

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            orig_path = f.name
        try:
            out_path = str(Path(orig_path).with_suffix(".out.json"))
            creator = GodTierShortsCreator(ui_callback=None)
            creator._shift_timestamps(orig_path, start_t, end_t, out_path)

            with open(out_path, "r", encoding="utf-8") as f:
                shifted = json.load(f)

            assert len(shifted) == 1
            seg = shifted[0]
            # new_end klip süresini aşmamalı
            assert seg["end"] <= duration, f"new_end={seg['end']} > duration={duration}"
            # Kelime end'leri de clamp edilmeli
            for w in seg["words"]:
                assert w["end"] <= duration, f"word end={w['end']} > duration={duration}"
        finally:
            Path(orig_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

    def test_segment_fully_inside_clip(self):
        """Tamamen klip içindeki segment değişmeden kaydırılmalı."""
        data = [
            {
                "text": "içeride",
                "start": 1.0,
                "end": 2.0,
                "words": [{"word": "içeride", "start": 1.0, "end": 2.0, "score": 1.0}],
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            orig_path = f.name
        try:
            out_path = str(Path(orig_path).with_suffix(".out.json"))
            creator = GodTierShortsCreator(ui_callback=None)
            creator._shift_timestamps(orig_path, 0.0, 5.0, out_path)

            with open(out_path, "r", encoding="utf-8") as f:
                shifted = json.load(f)

            assert len(shifted) == 1
            assert shifted[0]["start"] == 1.0
            assert shifted[0]["end"] == 2.0
            assert shifted[0]["words"][0]["end"] == 2.0
        finally:
            Path(orig_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)
