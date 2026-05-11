"""
backend/services/transcription.py
===================================
faster-whisper ile ses transkripsiyon servisi.
(Systran/faster-whisper-large-v3 modeli HuggingFace cache'inde mevcut)
"""
import gc
import json
import os
import sys
import sysconfig
import threading
from pathlib import Path


def _register_nvidia_dll_directories() -> list[str]:
    """Windows Python 3.8+ icin nvidia-* pip paketlerinin DLL klasorlerini DLL search path'e ekler.

    CTranslate2 GPU build'i cublas64_12.dll, cudnn64_9.dll vb. icin bu yollara ihtiyac duyar;
    aksi halde 'Library cublas64_12.dll is not found or cannot be loaded' hatasi alinir.
    """
    if sys.platform != "win32":
        return []

    site_packages = Path(sysconfig.get_paths().get("purelib", ""))
    if not site_packages.is_dir():
        site_packages = Path(sysconfig.get_paths().get("platlib", ""))
    if not site_packages.is_dir():
        for entry in sys.path:
            candidate = Path(entry)
            if candidate.name == "site-packages" and candidate.is_dir():
                site_packages = candidate
                break

    nvidia_root = site_packages / "nvidia"
    if not nvidia_root.is_dir():
        return []

    registered: list[str] = []
    path_entries: list[str] = []
    for sub in nvidia_root.iterdir():
        bin_dir = sub / "bin"
        if not bin_dir.is_dir():
            continue
        try:
            os.add_dll_directory(str(bin_dir))
            registered.append(str(bin_dir))
            path_entries.append(str(bin_dir))
        except (OSError, FileNotFoundError):
            continue

    if path_entries:
        existing_path = os.environ.get("PATH", "")
        normalized_existing = existing_path.lower().split(os.pathsep)
        prefix_to_add = [
            entry for entry in path_entries if entry.lower() not in normalized_existing
        ]
        if prefix_to_add:
            os.environ["PATH"] = os.pathsep.join([*prefix_to_add, existing_path]) if existing_path else os.pathsep.join(prefix_to_add)
    return registered


_REGISTERED_NVIDIA_DLL_DIRS = _register_nvidia_dll_directories()

import ctranslate2
import torch
import faster_whisper
from dotenv import load_dotenv
from loguru import logger

if _REGISTERED_NVIDIA_DLL_DIRS:
    logger.debug("nvidia DLL search dirs: {}", _REGISTERED_NVIDIA_DLL_DIRS)

from backend.config import LOGS_DIR, MODELS_DIR, VIDEO_METADATA
from backend.core.exceptions import FileOperationError, TranscriptionError

load_dotenv()

# -------------------------------------------------------------------------
# Ortam / donanım
# -------------------------------------------------------------------------

HF_TOKEN     = os.environ.get("HF_TOKEN", "")
LOCAL_MODEL_REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.json")


def _detect_whisper_device() -> str:
    """faster-whisper icin cihaz secimi: torch CPU-only build olsa bile CTranslate2 GPU kullanabilir."""
    forced = os.environ.get("WHISPER_DEVICE", "").strip().lower()
    if forced in {"cpu", "cuda"}:
        return forced
    try:
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except (RuntimeError, OSError) as exc:
        logger.warning("CTranslate2 CUDA probe basarisiz: {}", exc)
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


DEVICE = _detect_whisper_device()


def _read_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


WHISPER_BEAM_SIZE   = _read_int_env("WHISPER_BEAM_SIZE", 1)
WHISPER_VAD_FILTER  = _read_bool_env("WHISPER_VAD_FILTER", True)
WHISPER_VAD_MIN_SILENCE_MS = _read_int_env("WHISPER_VAD_MIN_SILENCE_MS", 500, minimum=0)
WHISPER_CPU_THREADS = _read_int_env("WHISPER_CPU_THREADS", 8, minimum=0)
WHISPER_NUM_WORKERS = _read_int_env("WHISPER_NUM_WORKERS", 1, minimum=1)
WHISPER_COMPUTE_TYPE_GPU = os.environ.get("WHISPER_COMPUTE_TYPE_GPU", "float16").strip() or "float16"
WHISPER_COMPUTE_TYPE_CPU = os.environ.get("WHISPER_COMPUTE_TYPE_CPU", "int8").strip() or "int8"

# Model cache: (model_size, device) -> WhisperModel (tekrarlı transkripsiyonlarda bellek/disk tasarrufu)
_model_cache: dict[tuple[str, str], faster_whisper.WhisperModel] = {}


def release_whisper_models() -> None:
    """Whisper modellerini VRAM'den boşaltır (YOLO için alan açar)."""
    global _model_cache
    for _key, model in list(_model_cache.items()):
        try:
            del model
        except Exception:
            pass
    _model_cache.clear()
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


# Loglama
logger.add(
    str(LOGS_DIR / "transcription_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)


def _get_local_model_path(model_size: str) -> Path:
    return MODELS_DIR / f"whisper-{model_size}"


def _is_complete_local_model(model_path: Path) -> bool:
    return model_path.exists() and model_path.is_dir() and all(
        (model_path / required_file).exists() for required_file in LOCAL_MODEL_REQUIRED_FILES
    )


def _build_model_candidates(model_size: str) -> list[tuple[str, str | None]]:
    local_model_path = _get_local_model_path(model_size)
    cache_root = MODELS_DIR / "faster-whisper-cache"
    cache_root.mkdir(parents=True, exist_ok=True)

    candidates: list[tuple[str, str | None]] = []

    if _is_complete_local_model(local_model_path):
        candidates.append((str(local_model_path), None))
    elif local_model_path.exists():
        logger.warning(
            f"⚠️ Yerel model dizini eksik veya bozuk: {local_model_path}. "
            "İzole cache üzerinden yeniden denenecek."
        )

    candidates.extend(
        [
            (f"Systran/faster-whisper-{model_size}", str(cache_root)),
            (model_size, str(cache_root)),
            (f"Systran/faster-whisper-{model_size}", None),
        ]
    )
    return candidates


def _load_whisper_model(model_size: str) -> faster_whisper.WhisperModel:
    cache_key = (model_size, DEVICE)
    if cache_key in _model_cache:
        logger.debug(f"♻️ faster-whisper modeli cache'ten yüklendi: {model_size}")
        return _model_cache[cache_key]

    last_error: Exception | None = None

    for model_id, download_root in _build_model_candidates(model_size):
        try:
            logger.info(
                "📥 faster-whisper modeli deneniyor: "
                f"model_id={model_id}, download_root={download_root or 'varsayılan-cache'}"
            )
            compute_type = WHISPER_COMPUTE_TYPE_CPU if DEVICE == "cpu" else WHISPER_COMPUTE_TYPE_GPU
            model = faster_whisper.WhisperModel(
                model_id,
                device=DEVICE,
                compute_type=compute_type,
                download_root=download_root,
                cpu_threads=WHISPER_CPU_THREADS,
                num_workers=WHISPER_NUM_WORKERS,
            )
            logger.success(f"✅ Model yüklendi: {model_id}")
            _model_cache[cache_key] = model
            return model
        except (OSError, ValueError, RuntimeError) as exc:
            last_error = exc
            logger.warning(f"Model yükleme denemesi başarısız oldu ({model_id}): {exc}")

    raise TranscriptionError(
        f"faster-whisper modeli yüklenemedi ({model_size})",
        details=str(last_error),
    )


# -------------------------------------------------------------------------
# Ana fonksiyon
# -------------------------------------------------------------------------

def run_transcription(
    audio_file: str,
    output_json: str | None = None,
    status_callback=None,
    language: str = "tr",
    model_size: str = "large-v3",
    cancel_event: threading.Event | None = None,
) -> str:
    """
    faster-whisper ile ses dosyasını transkript eder. 
    Sonucu output_json'a yazar.

    Args:
        audio_file:       WAV dosyası yolu
        output_json:      Çıktı JSON dosyası yolu (varsayılan: config.VIDEO_METADATA)
        status_callback:  UI'a ilerleme bildirmek için callback(msg, progress)
        language:         Dil kodu (varsayılan: "tr")
        model_size:       Whisper model boyutu (varsayılan: "large-v3")

    Returns:
        Yazılan JSON dosyasının yolu
    """
    if output_json is None:
        output_json = str(VIDEO_METADATA)

    def _status(msg: str, pct: int) -> None:
        logger.info(f"[{pct}%] {msg}")
        if status_callback:
            status_callback(msg, pct)

    if not os.path.exists(audio_file):
        raise FileOperationError(f"Ses dosyası bulunamadı: {audio_file}")

    def _check_cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Job cancelled by user")

    # 1. Transkript (faster-whisper)
    _status(f"faster-whisper modeli ({model_size}) yükleniyor...", 31)
    _check_cancelled()

    try:
        model = _load_whisper_model(model_size)

        _status("Ses analiz ediliyor (konuşma → metin)...", 33)
        _check_cancelled()

        try:
            segments, info = model.transcribe(
                audio_file,
                language=language,
                beam_size=WHISPER_BEAM_SIZE,
                word_timestamps=True,
                vad_filter=WHISPER_VAD_FILTER,
                vad_parameters=dict(min_silence_duration_ms=WHISPER_VAD_MIN_SILENCE_MS),
            )
            logger.info(
                "🎛️ faster-whisper params: beam_size={}, vad_filter={}, vad_min_silence_ms={}, "
                "compute_type={}, cpu_threads={}, num_workers={}",
                WHISPER_BEAM_SIZE,
                WHISPER_VAD_FILTER,
                WHISPER_VAD_MIN_SILENCE_MS,
                WHISPER_COMPUTE_TYPE_CPU if DEVICE == "cpu" else WHISPER_COMPUTE_TYPE_GPU,
                WHISPER_CPU_THREADS,
                WHISPER_NUM_WORKERS,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            raise TranscriptionError("Ses transkripsiyonu başarısız oldu", details=str(exc)) from exc

        logger.info(f"✅ Transkript tamamlandı. Dil: {info.language}, {info.language_probability:.2f}")

        logger.success(f"🎉 İlk analiz başarılı, segmentler ayrıştırılıyor...")

        segment_list = []
        total_seg_count = 0
        
        for seg in segments:
            _check_cancelled()
            words = []
            for word in getattr(seg, "words", []) or []:
                if word.start is None or word.end is None:
                    continue

                token = (word.word or "").strip()
                if not token:
                    continue

                words.append({
                    "word": token,
                    "start": float(word.start),
                    "end": float(word.end),
                    "score": float(getattr(word, "probability", 1.0) or 1.0),
                })

            segment_list.append({
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text.strip(),
                "speaker": "Unknown",
                "words": words,
            })
            
            # Dinamik UI İlerleme Bildirimi (34% ile 40% arasında sanal ilerleme)
            total_seg_count += 1
            if total_seg_count % 5 == 0:
                fake_prog = min(40, 33 + (total_seg_count // 5))
                _status(f"Kelimeler işleniyor ({total_seg_count} cümle tamamlandı)...", fake_prog)

        logger.success(f"✅ {len(segment_list)} segment işlendi.")

        _status("Transkript sonuçları diske yazılıyor...", 41)
        _check_cancelled()
        try:
            Path(output_json).parent.mkdir(parents=True, exist_ok=True)
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(segment_list, f, ensure_ascii=False, indent=4)
        except OSError as exc:
            raise FileOperationError("Transkript dosyası yazılamadı", details=str(exc)) from exc

        logger.success(f"🎉 Transkript oluşturuldu → {output_json}")
        return output_json
    finally:
        release_whisper_models()
