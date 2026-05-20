from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path



def test_load_pipeline_reads_hf_token_at_call_time(monkeypatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)

    from backend.services import diarization

    importlib.reload(diarization)
    diarization.release_diarization_pipeline()
    monkeypatch.setattr(diarization, "_check_pyannote", lambda: True)

    calls: list[tuple[str, dict[str, str]]] = []

    class FakePipeline:
        def to(self, device):
            return self

    class FakePipelineLoader:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs):
            calls.append((model_id, kwargs))
            return FakePipeline()

    fake_pyannote = types.ModuleType("pyannote")
    fake_pyannote_audio = types.ModuleType("pyannote.audio")
    fake_pyannote_audio.Pipeline = FakePipelineLoader
    fake_pyannote.audio = fake_pyannote_audio

    monkeypatch.setitem(sys.modules, "pyannote", fake_pyannote)
    monkeypatch.setitem(sys.modules, "pyannote.audio", fake_pyannote_audio)
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")

    pipeline = diarization._load_pipeline()

    assert pipeline is not None
    assert calls == [
        (
            "pyannote/speaker-diarization-3.1",
            {"token": "hf_test_token"},
        )
    ]


def test_hf_hub_compat_shim_maps_use_auth_token(monkeypatch) -> None:
    from backend.services import diarization

    diarization._hf_hub_compat_applied = False

    calls: list[dict[str, str]] = []

    fake_module = types.SimpleNamespace()

    def fake_hf_hub_download(*args, **kwargs):
        calls.append(dict(kwargs))
        return "ok"

    fake_module.hf_hub_download = fake_hf_hub_download
    fake_module.snapshot_download = fake_hf_hub_download
    fake_module.model_info = fake_hf_hub_download

    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)

    diarization._apply_hf_hub_compat_shims()
    fake_module.hf_hub_download(repo_id="demo", use_auth_token="hf_token")

    assert calls == [{"repo_id": "demo", "token": "hf_token"}]


def test_speechbrain_compat_shim_stubs_optional_k2_module(monkeypatch) -> None:
    from backend.services import diarization

    speechbrain_integrations = types.ModuleType("speechbrain.integrations")
    monkeypatch.setitem(sys.modules, "speechbrain.integrations", speechbrain_integrations)
    monkeypatch.setattr(
        diarization.importlib.util,
        "find_spec",
        lambda name: None if name in {"k2", "flair"} else object(),
    )
    sys.modules.pop("speechbrain.integrations.k2_fsa", None)
    sys.modules.pop("speechbrain.integrations.nlp", None)

    diarization._apply_speechbrain_compat_shims()

    assert "speechbrain.integrations.k2_fsa" in sys.modules
    assert getattr(speechbrain_integrations, "k2_fsa", None) is sys.modules["speechbrain.integrations.k2_fsa"]
    assert "speechbrain.integrations.nlp" in sys.modules
    assert getattr(speechbrain_integrations, "nlp", None) is sys.modules["speechbrain.integrations.nlp"]


def test_run_diarization_uses_worker_process(monkeypatch, tmp_path: Path) -> None:

    from backend.services import diarization

    audio_path = tmp_path / "audio.wav"
    transcript_path = tmp_path / "transcript.json"
    audio_path.write_bytes(b"RIFFstub")
    transcript_path.write_text("[]", encoding="utf-8")
    custom_python = tmp_path / "custom-python.exe"
    custom_python.write_text("", encoding="utf-8")

    status_updates: list[tuple[str, int]] = []
    popen_calls: list[tuple[list[str], dict[str, object]]] = []

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = iter(
                [
                    diarization.WORKER_EVENT_PREFIX + json.dumps({"type": "status", "message": "hazir", "progress": 41}) + "\n",
                    diarization.WORKER_EVENT_PREFIX + json.dumps({"type": "result", "ok": True}) + "\n",
                ]
            )

        def wait(self) -> int:
            return 0

        def kill(self) -> None:
            return None

    def fake_popen(cmd, **kwargs):
        popen_calls.append((list(cmd), kwargs))
        return FakeProcess()

    monkeypatch.setattr(diarization.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("DIARIZATION_SUBPROCESS_ENABLED", "1")
    monkeypatch.setenv("DIARIZATION_PYTHON", str(custom_python))
    diarization._worker_python_cmd_cache = None

    ok = diarization.run_diarization(
        str(audio_path),
        str(transcript_path),
        num_speakers=2,
        status_callback=lambda message, progress: status_updates.append((message, progress)),
    )

    assert ok is True
    assert status_updates == [("hazir", 41)]
    assert popen_calls
    cmd, kwargs = popen_calls[0]
    assert cmd[:3] == [str(custom_python), "-m", diarization.WORKER_MODULE]
    assert "--num-speakers" in cmd
    assert kwargs["text"] is True



def test_run_diarization_can_fallback_to_local_mode(monkeypatch, tmp_path: Path) -> None:
    from backend.services import diarization

    audio_path = tmp_path / "audio.wav"
    transcript_path = tmp_path / "transcript.json"
    audio_path.write_bytes(b"RIFFstub")
    transcript_path.write_text("[]", encoding="utf-8")

    calls: list[tuple[str, str, int | None]] = []

    def fake_local(audio_file: str, transcript_file: str, *, num_speakers: int | None = None, status_callback=None) -> bool:
        calls.append((audio_file, transcript_file, num_speakers))
        return True

    monkeypatch.setattr(diarization, "_run_diarization_local", fake_local)
    monkeypatch.setenv("DIARIZATION_SUBPROCESS_ENABLED", "0")

    ok = diarization.run_diarization(str(audio_path), str(transcript_path), num_speakers=3)

    assert ok is True
    assert calls == [(str(audio_path), str(transcript_path), 3)]


def test_run_diarization_falls_back_to_local_when_worker_fails(monkeypatch, tmp_path: Path) -> None:
    from backend.services import diarization

    audio_path = tmp_path / "audio.wav"
    transcript_path = tmp_path / "transcript.json"
    audio_path.write_bytes(b"RIFFstub")
    transcript_path.write_text("[]", encoding="utf-8")
    calls: list[tuple[str, str, int | None]] = []

    monkeypatch.setenv("DIARIZATION_SUBPROCESS_ENABLED", "1")
    monkeypatch.setattr(diarization, "_run_diarization_worker", lambda *args, **kwargs: False)

    def fake_local(audio_file: str, transcript_file: str, *, num_speakers: int | None = None, status_callback=None) -> bool:
        calls.append((audio_file, transcript_file, num_speakers))
        return True

    monkeypatch.setattr(diarization, "_run_diarization_local", fake_local)

    ok = diarization.run_diarization(str(audio_path), str(transcript_path), num_speakers=4)

    assert ok is True
    assert calls == [(str(audio_path), str(transcript_path), 4)]


def test_transcript_has_speaker_labels_detects_segment_and_word_labels(tmp_path: Path) -> None:
    from backend.services import diarization

    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(
        json.dumps(
            [
                {"start": 0.0, "end": 1.0, "speaker": "Unknown", "words": []},
                {
                    "start": 1.0,
                    "end": 2.0,
                    "speaker": "Unknown",
                    "words": [{"word": "hi", "start": 1.0, "end": 1.2, "speaker": "SPEAKER_00"}],
                },
            ]
        ),
        encoding="utf-8",
    )

    assert diarization.transcript_has_speaker_labels(str(transcript_path)) is True


def test_numpy_nan_aliases_restored_for_numpy2(monkeypatch) -> None:
    import numpy as np

    from backend.services import diarization

    diarization._pyannote_available = None
    monkeypatch.delattr(np, "NaN", raising=False)
    monkeypatch.delattr(np, "NAN", raising=False)
    monkeypatch.setattr(diarization, "_apply_torch_compat_shims", lambda: None)
    monkeypatch.setattr(diarization, "_apply_hf_hub_compat_shims", lambda: None)
    monkeypatch.setattr(
        diarization,
        "apply_torchaudio_compat_shims",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(diarization, "_apply_speechbrain_compat_shims", lambda: None)
    monkeypatch.setitem(sys.modules, "pyannote", types.ModuleType("pyannote"))
    monkeypatch.setitem(sys.modules, "pyannote.audio", types.ModuleType("pyannote.audio"))

    assert diarization._check_pyannote() is True
    assert hasattr(np, "NaN") and np.isnan(np.NaN)
    assert hasattr(np, "NAN") and np.isnan(np.NAN)


def test_resolve_diarization_python_supports_relative_env_path(monkeypatch, tmp_path: Path) -> None:
    from backend.services import diarization

    project_root = tmp_path / "repo"
    service_dir = project_root / "backend" / "services"
    python_path = project_root / ".venv-diarization" / "Scripts" / "python.exe"
    service_dir.mkdir(parents=True, exist_ok=True)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(diarization, "__file__", str(service_dir / "diarization.py"))
    monkeypatch.setenv("DIARIZATION_PYTHON", ".venv-diarization/Scripts/python.exe")
    diarization._worker_python_cmd_cache = None

    assert diarization._resolve_diarization_python() == [str(python_path.resolve())]
