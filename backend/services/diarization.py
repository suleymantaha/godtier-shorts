"""
backend/services/diarization.py
================================
pyannote.audio ile konuşmacı diarizasyonu servisi.

Transkript segmentlerine SPEAKER_00, SPEAKER_01 gibi etiketler ekler.
VideoProcessor, bu etiketleri kullanarak frame zamaninda aktif konusmaciyi belirler.

Guvenli varsayilan: diarization ayri bir worker subprocess'inde calisir.
Boylece pyannote / torchaudio uyumsuzluklari ana backend process'ini bozmaz.
"""
from __future__ import annotations

import bisect
import functools
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import types
from pathlib import Path
from typing import Any, TypedDict

from loguru import logger

WORKER_EVENT_PREFIX = "DIARIZATION_EVENT "
WORKER_MODULE = "backend.workers.pyannote_diarization_worker"

# pyannote lazy import — kurulu degilse fonksiyonlar gracefully degrade eder
_pyannote_available: bool | None = None
_pipeline_cache: dict[str, object] = {}
_pipeline_lock = threading.Lock()
_hf_hub_compat_applied = False
_torch_compat_applied = False
_worker_python_cmd_cache: tuple[str, ...] | None = None


def _get_hf_token() -> str:
    """HF token'i her cagrida env'den oku; .env sonradan yuklenmis olabilir."""
    return os.environ.get("HF_TOKEN", "").strip()



def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}



def _notify_status(status_callback, msg: str, pct: int) -> None:
    logger.info("[{}%] {}", pct, msg)
    if status_callback:
        status_callback(msg, pct)


def _apply_hf_hub_compat_shims() -> None:
    global _hf_hub_compat_applied
    if _hf_hub_compat_applied:
        return

    try:
        import huggingface_hub as hf_hub
    except Exception:
        return

    def _wrap(name: str) -> None:
        original = getattr(hf_hub, name, None)
        if original is None or getattr(original, "__diarization_compat_wrapped__", False):
            return

        @functools.wraps(original)
        def _wrapped(*args, **kwargs):
            if "use_auth_token" in kwargs and "token" not in kwargs:
                kwargs["token"] = kwargs.pop("use_auth_token")
            else:
                kwargs.pop("use_auth_token", None)
            return original(*args, **kwargs)

        setattr(_wrapped, "__diarization_compat_wrapped__", True)
        setattr(hf_hub, name, _wrapped)

    for attr_name in ("hf_hub_download", "snapshot_download", "model_info"):
        _wrap(attr_name)

    _hf_hub_compat_applied = True


def _apply_torch_compat_shims() -> None:
    global _torch_compat_applied
    if _torch_compat_applied:
        return

    try:
        import torch
    except Exception:
        return

    try:
        from torch.serialization import add_safe_globals
        from torch.torch_version import TorchVersion

        add_safe_globals([TorchVersion])
    except Exception:
        pass

    original_torch_load = getattr(torch, "load", None)
    if original_torch_load is not None and not getattr(original_torch_load, "__diarization_compat_wrapped__", False):

        @functools.wraps(original_torch_load)
        def _wrapped_torch_load(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return original_torch_load(*args, **kwargs)

        setattr(_wrapped_torch_load, "__diarization_compat_wrapped__", True)
        torch.load = _wrapped_torch_load

    _torch_compat_applied = True


def _apply_speechbrain_compat_shims() -> None:
    """
    speechbrain'in opsiyonel k2 entegrasyonu pyannote import zincirinde sert
    ImportError uretebiliyor. k2 kurulu degilse bos bir stub ile degrade et.
    """
    def _register_stub(module_name: str, doc: str) -> None:
        if module_name in sys.modules:
            return
        stub = types.ModuleType(module_name)
        stub.__doc__ = doc
        stub.__file__ = "<speechbrain-compat-stub>"
        if module_name.endswith(".nlp"):
            stub.__path__ = []  # type: ignore[attr-defined]
        sys.modules[module_name] = stub

        parent_name, _, child_name = module_name.rpartition(".")
        if parent_name:
            parent_module = sys.modules.get(parent_name)
            if parent_module is not None:
                setattr(parent_module, child_name, stub)

    if importlib.util.find_spec("k2") is None:
        _register_stub("speechbrain.integrations.k2_fsa", "Compatibility stub for optional speechbrain k2 integration.")

    if importlib.util.find_spec("flair") is None:
        _register_stub("speechbrain.integrations.nlp", "Compatibility stub for optional speechbrain NLP integration.")



def _check_pyannote() -> bool:
    global _pyannote_available
    if _pyannote_available is None:
        _apply_torch_compat_shims()
        _apply_hf_hub_compat_shims()
        try:
            from backend.workers.torchaudio_compat import apply_torchaudio_compat_shims

            apply_torchaudio_compat_shims()
            _apply_speechbrain_compat_shims()

            # NumPy 2.0 uyumlulugu: np.NaN / np.NAN kaldirildi, bagimliliklar hala kullaniyor
            import numpy as _np

            if not hasattr(_np, "NaN"):
                _np.NaN = _np.nan  # type: ignore[attr-defined]
            if not hasattr(_np, "NAN"):
                _np.NAN = _np.nan  # type: ignore[attr-defined]

            import pyannote.audio  # type: ignore[import-untyped]  # noqa: F401

            _pyannote_available = True
        except ImportError:
            _pyannote_available = False
            logger.warning("pyannote.audio kurulu degil — diarization devre disi.")
        except Exception as exc:
            _pyannote_available = False
            logger.warning("pyannote.audio yuklenemedi — diarization devre disi: {}", exc)
    return _pyannote_available



def _load_pipeline():
    """pyannote speaker-diarization-3.1 pipeline'ini yukle (cache'e al)."""
    cache_key = "speaker-diarization-3.1"
    with _pipeline_lock:
        if cache_key in _pipeline_cache:
            return _pipeline_cache[cache_key]

        if not _check_pyannote():
            return None

        hf_token = _get_hf_token()
        if not hf_token:
            logger.error("HF_TOKEN tanimli degil veya henuz yuklenmedi — pyannote pipeline yuklenemiyor.")
            return None

        try:
            from pyannote.audio import Pipeline  # type: ignore[import-untyped]
            try:
                from torch.serialization import add_safe_globals
                from pyannote.audio.core.task import Problem, Resolution, Specifications  # type: ignore[import-untyped]

                safe_globals: list[object] = [Problem, Resolution, Specifications]
                try:
                    from pyannote.audio.utils.powerset import Powerset  # type: ignore[import-untyped]

                    safe_globals.append(Powerset)
                except Exception:
                    pass
                add_safe_globals(safe_globals)
            except Exception:
                pass

            logger.info("pyannote speaker-diarization-3.1 yukleniyor...")

            # Farkli pyannote/huggingface_hub surumleri icin token aktarimini kademeli dene.
            try:
                pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=hf_token,
                )
            except TypeError:
                try:
                    pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=hf_token,
                    )
                except TypeError:
                    from huggingface_hub import login as _hf_login

                    _hf_login(token=hf_token, add_to_git_credential=False)
                    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")

            try:
                import torch

                if torch.cuda.is_available():
                    pipeline = pipeline.to(torch.device("cuda"))
                    logger.info("pyannote pipeline CUDA'ya tasindi.")
            except Exception as exc:
                logger.warning("pyannote CUDA tasima basarisiz, CPU'da devam: {}", exc)

            _pipeline_cache[cache_key] = pipeline
            logger.success("pyannote pipeline hazir.")
            return pipeline
        except Exception as exc:
            logger.error("pyannote pipeline yuklenemedi: {}", exc)
            return None



def _parse_worker_event(line: str) -> dict[str, Any] | None:
    if not line.startswith(WORKER_EVENT_PREFIX):
        return None
    payload_raw = line[len(WORKER_EVENT_PREFIX) :]
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        logger.warning("Diarization worker JSON satiri parse edilemedi: {} | {}", exc, line)
        return None
    if not isinstance(payload, dict):
        return None
    return payload



def _probe_python_command(cmd: list[str]) -> bool:
    try:
        completed = subprocess.run(
            [*cmd, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0



def _resolve_diarization_python() -> list[str]:
    global _worker_python_cmd_cache
    if _worker_python_cmd_cache is not None:
        return list(_worker_python_cmd_cache)

    project_root = Path(__file__).resolve().parents[2]
    configured = os.environ.get("DIARIZATION_PYTHON", "").strip()
    if configured:
        configured_path = Path(configured)
        if not configured_path.is_absolute():
            configured_path = (project_root / configured_path).resolve()
        if configured_path.exists():
            _worker_python_cmd_cache = (str(configured_path),)
            return list(_worker_python_cmd_cache)
        logger.warning("DIARIZATION_PYTHON bulundu ama dosya yok: {}", configured_path)

    # Önce proje içi izole ortamları dene.
    candidate_paths = [
        project_root / ".venv-diarization" / "Scripts" / "python.exe",
        project_root / ".venv-diarization" / "bin" / "python",
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python",
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            _worker_python_cmd_cache = (str(candidate),)
            return list(_worker_python_cmd_cache)

    # Windows'ta py launcher ile desteklenen bir yorumlayıcıyı seçmeye çalış.
    if os.name == "nt":
        py_launcher = shutil.which("py")
        if py_launcher:
            for version in ("3.12", "3.11", "3.13"):
                cmd = [py_launcher, f"-{version}"]
                if _probe_python_command(cmd):
                    _worker_python_cmd_cache = tuple(cmd)
                    return list(_worker_python_cmd_cache)

    _worker_python_cmd_cache = (sys.executable,)
    return list(_worker_python_cmd_cache)



def transcript_has_speaker_labels(transcript_json_path: str) -> bool:
    """Transkriptte en az bir segment/kelime seviyesinde speaker etiketi var mı?"""
    try:
        with open(transcript_json_path, encoding="utf-8") as handle:
            segments = json.load(handle)
    except Exception as exc:
        logger.warning("Transkript speaker durumu okunamadi: {} | {}", transcript_json_path, exc)
        return False

    if not isinstance(segments, list):
        return False

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        speaker = str(seg.get("speaker", "")).strip()
        if speaker and speaker != "Unknown":
            return True
        for word in seg.get("words", []) or []:
            if not isinstance(word, dict):
                continue
            word_speaker = str(word.get("speaker", "")).strip()
            if word_speaker and word_speaker != "Unknown":
                return True
    return False



def ensure_transcript_diarization(
    audio_path: str,
    transcript_json_path: str,
    *,
    num_speakers: int | None = None,
    status_callback=None,
) -> bool:
    """
    Mevcut transkriptte speaker etiketleri yoksa diarization backfill uygular.

    Speaker etiketleri zaten varsa tekrar çalıştırmaz.
    """
    if transcript_has_speaker_labels(transcript_json_path):
        logger.debug("Transkript zaten diarization etiketleri içeriyor: {}", transcript_json_path)
        return True

    _notify_status(
        status_callback,
        "Mevcut transkriptte konusmaci etiketleri eksik; diarization backfill baslatiliyor...",
        42,
    )
    return run_diarization(
        audio_path,
        transcript_json_path,
        num_speakers=num_speakers,
        status_callback=status_callback,
    )



def _run_diarization_worker(
    audio_path: str,
    transcript_json_path: str,
    *,
    num_speakers: int | None = None,
    status_callback=None,
) -> bool:
    python_cmd = _resolve_diarization_python()
    if not python_cmd:
        logger.error("Diarization worker icin python executable cozumlenemedi.")
        return False

    project_root = Path(__file__).resolve().parents[2]
    cmd = [*python_cmd, "-m", WORKER_MODULE, "--audio-path", audio_path, "--transcript-json-path", transcript_json_path]
    if num_speakers is not None:
        cmd.extend(["--num-speakers", str(num_speakers)])

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONIOENCODING"] = "utf-8"

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    logger.info("Diarization worker baslatiliyor: {}", " ".join(python_cmd))

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
    except OSError as exc:
        logger.error("Diarization worker baslatilamadi: {}", exc)
        return False

    result_ok = False
    try:
        if process.stdout is None:
            logger.error("Diarization worker stdout acilamadi.")
            process.wait(timeout=5)
            return False

        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue

            event = _parse_worker_event(line)
            if event is None:
                logger.info("diarization-worker | {}", line)
                continue

            event_type = str(event.get("type", "")).strip().lower()
            if event_type == "status":
                message = str(event.get("message", "Diarization ilerliyor"))
                progress_raw = event.get("progress", 0)
                try:
                    progress = int(progress_raw)
                except (TypeError, ValueError):
                    progress = 0
                _notify_status(status_callback, message, progress)
            elif event_type == "result":
                result_ok = bool(event.get("ok"))
                speakers = event.get("unique_speakers")
                if isinstance(speakers, list):
                    logger.success("Diarization worker tamamlandi | Konusmacilar: {}", speakers)
            elif event_type == "error":
                logger.error("Diarization worker hatasi: {}", event.get("message", "Bilinmeyen hata"))

        return_code = process.wait()
    except Exception as exc:
        process.kill()
        logger.error("Diarization worker okunurken hata olustu: {}", exc)
        return False

    if return_code != 0:
        logger.error("Diarization worker sifirdan farkli kodla cikti: {}", return_code)
        return False

    if not result_ok:
        logger.warning("Diarization worker tamamlandi ama basarili sonuc donmedi.")
    return result_ok


# ---------------------------------------------------------------------------
# Ana diarizasyon fonksiyonu
# ---------------------------------------------------------------------------

def run_diarization(
    audio_path: str,
    transcript_json_path: str,
    *,
    num_speakers: int | None = None,
    status_callback=None,
) -> bool:
    """
    Ses dosyasina diarizasyon uygular ve transkript segmentlerini gunceller.

    Varsayilan olarak ayri bir worker subprocess'i kullanir. Bu sayede pyannote
    bagimliliklari ana backend ortamindan izole edilebilir.
    """
    if not os.path.exists(audio_path):
        logger.error("Ses dosyasi bulunamadi: {}", audio_path)
        return False

    if not os.path.exists(transcript_json_path):
        logger.error("Transkript dosyasi bulunamadi: {}", transcript_json_path)
        return False

    if _read_bool_env("DIARIZATION_SUBPROCESS_ENABLED", True):
        worker_ok = _run_diarization_worker(
            audio_path,
            transcript_json_path,
            num_speakers=num_speakers,
            status_callback=status_callback,
        )
        if worker_ok:
            return True
        logger.warning("Diarization worker basarisiz oldu; local fallback denenecek.")

    return _run_diarization_local(
        audio_path,
        transcript_json_path,
        num_speakers=num_speakers,
        status_callback=status_callback,
    )



def _run_diarization_local(
    audio_path: str,
    transcript_json_path: str,
    *,
    num_speakers: int | None = None,
    status_callback=None,
) -> bool:
    if not _check_pyannote():
        _notify_status(status_callback, "pyannote.audio kurulu degil, diarization atlandi.", 0)
        return False

    pipeline = _load_pipeline()
    if pipeline is None:
        return False

    try:
        _notify_status(status_callback, "Konusmaci diarization baslatiliyor...", 42)

        # TorchCodec bagimliligindan kacmak icin sesi once soundfile ile yukle.
        try:
            import soundfile as sf
            import torch
            import torchaudio

            waveform_np, sample_rate = sf.read(audio_path, always_2d=True, dtype="float32")
            waveform = torch.from_numpy(waveform_np.T)
            if sample_rate != 16000:
                waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)
                sample_rate = 16000
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            elif waveform.ndim == 1:
                waveform = waveform.unsqueeze(0)
            audio_input = {"waveform": waveform, "sample_rate": sample_rate}
        except Exception as exc:
            logger.warning("soundfile/torchaudio ile manuel audio load basarisiz ({}), dosya yolu ile deneniyor.", exc)
            audio_input = audio_path

        diarize_kwargs: dict[str, Any] = {"file": audio_input}
        if num_speakers is not None:
            diarize_kwargs["num_speakers"] = num_speakers

        diarization = pipeline(**diarize_kwargs)

        intervals: list[tuple[float, float, str]] = []
        for segment, _, label in diarization.itertracks(yield_label=True):
            intervals.append((segment.start, segment.end, label))
        intervals.sort(key=lambda item: item[0])

        _notify_status(status_callback, "Transkript segmentleri guncelleniyor...", 48)

        with open(transcript_json_path, encoding="utf-8") as handle:
            segments: list[dict[str, Any]] = json.load(handle)

        for seg in segments:
            seg["speaker"] = _dominant_speaker(intervals, float(seg["start"]), float(seg["end"])) or "Unknown"
            for word in seg.get("words", []):
                word["speaker"] = _dominant_speaker(
                    intervals,
                    float(word["start"]),
                    float(word["end"]),
                ) or seg["speaker"]

        with open(transcript_json_path, "w", encoding="utf-8") as handle:
            json.dump(segments, handle, ensure_ascii=False, indent=4)

        unique_speakers = sorted({seg["speaker"] for seg in segments if seg.get("speaker") != "Unknown"})
        _notify_status(status_callback, f"Diarization tamamlandi. Konusmacilar: {unique_speakers}", 50)
        logger.success("Diarization -> {} | Konusmacilar: {}", transcript_json_path, unique_speakers)
        return True

    except Exception as exc:
        logger.error("Diarization hatasi: {}", exc)
        return False



def _dominant_speaker(
    intervals: list[tuple[float, float, str]],
    seg_start: float,
    seg_end: float,
) -> str | None:
    """Verilen zaman araliginda en fazla overlap'e sahip konusmaciyi dondurur."""
    overlap_by_speaker: dict[str, float] = {}
    for iv_start, iv_end, label in intervals:
        if iv_end <= seg_start:
            continue
        if iv_start >= seg_end:
            break
        overlap = min(iv_end, seg_end) - max(iv_start, seg_start)
        if overlap > 0:
            overlap_by_speaker[label] = overlap_by_speaker.get(label, 0.0) + overlap
    if not overlap_by_speaker:
        return None
    return max(overlap_by_speaker, key=lambda speaker: overlap_by_speaker[speaker])


# ---------------------------------------------------------------------------
# Hizli arama indeksi (VideoProcessor icin)
# ---------------------------------------------------------------------------
class DiarizationEntry(TypedDict):
    start: float
    end: float
    speaker: str



def build_diarization_index(transcript_json_path: str) -> list[DiarizationEntry]:
    """
    transcript.json'dan konusmaci zaman indeksi olusturur.

    Donus: start zamanina gore sirali [(start, end, speaker)] listesi.
    Tum segmentlerde speaker == "Unknown" ise bos liste doner.
    """
    try:
        with open(transcript_json_path, encoding="utf-8") as handle:
            segments: list[dict[str, Any]] = json.load(handle)
    except Exception as exc:
        logger.warning("Diarization indeksi yuklenemedi: {}", exc)
        return []

    index: list[DiarizationEntry] = []
    for seg in segments:
        speaker = str(seg.get("speaker", "Unknown"))
        if speaker == "Unknown":
            continue
        index.append({"start": float(seg["start"]), "end": float(seg["end"]), "speaker": speaker})

    if not index:
        logger.debug("Diarization indeksi bos — tum segmentler Unknown.")
        return []

    index.sort(key=lambda entry: entry["start"])
    logger.debug(
        "Diarization indeksi yuklendi: {} segment, konusmacilar: {}",
        len(index),
        sorted({entry["speaker"] for entry in index}),
    )
    return index



def speaker_at(index: list[DiarizationEntry], t: float) -> str | None:
    """Verilen saniyede hangi konusmacinin aktif oldugunu dondurur."""
    if not index:
        return None
    starts = [entry["start"] for entry in index]
    pos = bisect.bisect_right(starts, t) - 1
    if pos < 0:
        return None
    entry = index[pos]
    if entry["start"] <= t <= entry["end"]:
        return entry["speaker"]
    return None



def release_diarization_pipeline() -> None:
    """Diarization pipeline'ini bellekten bosaltir."""
    with _pipeline_lock:
        _pipeline_cache.clear()
    logger.info("pyannote pipeline bellekten bosaltildi.")
