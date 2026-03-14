"""
backend/tests/conftest.py
=========================
Pytest fixtures ve ortak ayarlar.
"""
import pytest


@pytest.fixture
def sample_transcript():
    """Örnek faster-whisper transkript JSON'u."""
    return [
        {
            "text": "Merhaba dünya",
            "start": 0.0,
            "end": 1.5,
            "speaker": "SPEAKER_00",
            "words": [
                {"word": "Merhaba", "start": 0.0, "end": 0.5, "score": 0.99},
                {"word": "dünya", "start": 0.5, "end": 1.5, "score": 0.98},
            ],
        },
    ]
