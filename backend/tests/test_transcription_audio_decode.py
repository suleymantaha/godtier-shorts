"""Ensure the locked PyAV version can decode audio for faster-whisper."""

from __future__ import annotations

import wave

from faster_whisper.audio import decode_audio


def test_faster_whisper_decodes_local_wav(tmp_path):
    audio_path = tmp_path / "sample.wav"
    with wave.open(str(audio_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)

    decoded = decode_audio(str(audio_path))

    assert len(decoded) == 1600
