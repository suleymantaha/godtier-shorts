"""Compatibility shims for pyannote.audio on newer torchaudio releases.

pyannote.audio 3.1.x still imports APIs that torchaudio 2.11 removed from the
old top-level / backend modules. The worker applies lightweight shims before
loading pyannote so the incompatibility does not crash the main backend.
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AudioMetaData:
    sample_rate: int
    num_frames: int
    num_channels: int
    bits_per_sample: int
    encoding: str


_DEF_BACKENDS = ["soundfile"]



def _build_audio_metadata(*, sample_rate: int, num_frames: int, num_channels: int, bits_per_sample: int = 0, encoding: str = "PCM_S") -> AudioMetaData:
    return AudioMetaData(
        sample_rate=int(sample_rate),
        num_frames=int(num_frames),
        num_channels=int(num_channels),
        bits_per_sample=int(bits_per_sample),
        encoding=str(encoding),
    )



def _info_via_soundfile(file: Any) -> AudioMetaData | None:
    try:
        import soundfile as sf

        info = sf.info(file)
        channels = int(getattr(info, "channels", 1) or 1)
        samplerate = int(getattr(info, "samplerate", 16000) or 16000)
        frames = int(getattr(info, "frames", 0) or 0)
        subtype = str(getattr(info, "subtype", "PCM_S") or "PCM_S")
        return _build_audio_metadata(
            sample_rate=samplerate,
            num_frames=frames,
            num_channels=channels,
            encoding=subtype,
        )
    except Exception:
        return None



def apply_torchaudio_compat_shims() -> None:
    try:
        import torchaudio
    except Exception:
        return

    backend_module = sys.modules.get("torchaudio.backend")
    if backend_module is None:
        backend_module = types.ModuleType("torchaudio.backend")
        sys.modules["torchaudio.backend"] = backend_module
        setattr(torchaudio, "backend", backend_module)

    common_module = sys.modules.get("torchaudio.backend.common")
    if common_module is None:
        common_module = types.ModuleType("torchaudio.backend.common")
        sys.modules["torchaudio.backend.common"] = common_module
    setattr(common_module, "AudioMetaData", AudioMetaData)
    setattr(backend_module, "common", common_module)

    if not hasattr(torchaudio, "AudioMetaData"):
        setattr(torchaudio, "AudioMetaData", AudioMetaData)

    if not hasattr(torchaudio, "get_audio_backend"):
        setattr(torchaudio, "get_audio_backend", lambda: None)

    if not hasattr(torchaudio, "set_audio_backend"):
        setattr(torchaudio, "set_audio_backend", lambda *args, **kwargs: None)

    if not hasattr(torchaudio, "list_audio_backends"):
        setattr(torchaudio, "list_audio_backends", lambda: list(_DEF_BACKENDS))

    if hasattr(torchaudio, "info"):
        return

    def _info(file: Any) -> AudioMetaData:
        soundfile_info = _info_via_soundfile(file)
        if soundfile_info is not None:
            return soundfile_info

        waveform, sample_rate = torchaudio.load(file)
        num_channels = int(waveform.shape[0]) if waveform.ndim > 1 else 1
        num_frames = int(waveform.shape[-1])
        encoding = Path(str(file)).suffix.lstrip(".").upper() or "UNKNOWN"
        return _build_audio_metadata(
            sample_rate=int(sample_rate),
            num_frames=num_frames,
            num_channels=num_channels,
            encoding=encoding,
        )

    setattr(torchaudio, "info", _info)
