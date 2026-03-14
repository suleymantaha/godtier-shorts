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

    def test_lmstudio_client_appends_v1_suffix(self, monkeypatch: pytest.MonkeyPatch):
        """LM Studio host sonunda /v1 yoksa otomatik eklenir."""
        monkeypatch.setenv("LMSTUDIO_HOST", "http://localhost:1234")
        monkeypatch.delenv("LM_STUDIO_API_KEY", raising=False)

        with patch("backend.services.viral_analyzer.OpenAI") as mock_openai:
            analyzer = ViralAnalyzer(engine="lmstudio")
            analyzer._build_lmstudio_client()

        _, kwargs = mock_openai.call_args
        assert kwargs["base_url"] == "http://localhost:1234/v1"
        assert kwargs["api_key"] == "lm-studio"

    def test_analyze_metadata_uses_lmstudio_client(self):
        """engine=lmstudio iken LLM çağrısı LM Studio client ile yapılır."""
        transcript_data = [
            {"text": "test segment", "start": 0.0, "end": 12.0},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(transcript_data, f, ensure_ascii=False)
            path = f.name

        mock_message = MagicMock()
        mock_message.content = json.dumps(
            {
                "segments": [
                    {
                        "start_time": 0.0,
                        "end_time": 12.0,
                        "hook_text": "TEST HOOK",
                        "ui_title": "Test Baslik",
                        "social_caption": "Test #shorts",
                        "viral_score": 80,
                    }
                ]
            }
        )
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        try:
            analyzer = ViralAnalyzer(engine="lmstudio")
            with patch.object(analyzer, "_build_lmstudio_client", return_value=mock_client) as lm_client_builder, \
                 patch.object(analyzer, "_build_fallback_segments") as fallback_builder:
                result = analyzer.analyze_metadata(
                    path,
                    num_clips=3,
                    duration_min=90.0,
                    duration_max=150.0,
                )

            assert result is not None
            assert "segments" in result
            assert len(result["segments"]) == 1
            lm_client_builder.assert_called_once()
            fallback_builder.assert_not_called()
            _, kwargs = mock_client.chat.completions.create.call_args
            assert kwargs["model"] == analyzer.local_model_name
        finally:
            Path(path).unlink(missing_ok=True)

    @pytest.mark.skipif(
        True,  # Cloud API gerektirir, CI'da atla
        reason="Cloud API mock gerekli",
    )
    def test_prompt_contains_duration_range(self):
        """Cloud modda prompt icinde duration araligi kullanilir."""
        pass
