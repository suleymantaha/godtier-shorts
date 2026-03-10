"""
backend/tests/test_viral_analyzer_params.py
===========================================
ViralAnalyzer.analyze_metadata ve _build_fallback_segments parametre testleri.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.services.viral_analyzer import ViralAnalyzer


class TestBuildFallbackSegments:
    """_build_fallback_segments limit ve duration parametreleri."""

    def test_accepts_limit_param(self):
        """limit parametresi segment sayisini sinirlar."""
        transcript = [
            {"text": "a", "start": 0.0, "end": 10.0},
            {"text": "b", "start": 10.0, "end": 20.0},
            {"text": "c", "start": 20.0, "end": 30.0},
            {"text": "d", "start": 30.0, "end": 40.0},
            {"text": "e", "start": 40.0, "end": 50.0},
        ]
        analyzer = ViralAnalyzer(engine="local")
        result = analyzer._build_fallback_segments(transcript, limit=2)
        assert len(result["segments"]) <= 2

    def test_accepts_duration_params(self):
        """min_duration, max_duration, target_duration parametreleri kabul edilir."""
        transcript = [
            {"text": "x", "start": 0.0, "end": 5.0},
            {"text": "y", "start": 5.0, "end": 15.0},
            {"text": "z", "start": 15.0, "end": 25.0},
        ]
        analyzer = ViralAnalyzer(engine="local")
        result = analyzer._build_fallback_segments(
            transcript,
            limit=3,
            min_duration=10.0,
            max_duration=30.0,
            target_duration=20.0,
        )
        assert "segments" in result
        for seg in result["segments"]:
            dur = seg["end_time"] - seg["start_time"]
            assert dur >= 10.0
            assert dur <= 30.0


class TestAnalyzeMetadataParams:
    """analyze_metadata num_clips, duration_min, duration_max parametreleri."""

    def test_analyze_metadata_accepts_params(self):
        """analyze_metadata num_clips, duration_min, duration_max alir."""
        transcript_data = [
            {"text": "test", "start": 0.0, "end": 5.0},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(transcript_data, f, ensure_ascii=False)
            path = f.name
        try:
            analyzer = ViralAnalyzer(engine="local")
            result = analyzer.analyze_metadata(
                path,
                num_clips=5,
                duration_min=90.0,
                duration_max=150.0,
            )
            assert result is not None
            assert "segments" in result
            assert len(result["segments"]) <= 5
        finally:
            Path(path).unlink(missing_ok=True)

    @pytest.mark.skipif(
        True,  # Cloud API gerektirir, CI'da atla
        reason="Cloud API mock gerekli",
    )
    def test_prompt_contains_duration_range(self):
        """Cloud modda prompt icinde duration araligi kullanilir."""
        pass
