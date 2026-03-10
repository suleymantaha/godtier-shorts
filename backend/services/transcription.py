"""
backend/services/transcription.py
===================================
faster-whisper ile ses transkripsiyon servisi.
(Systran/faster-whisper-large-v3 modeli HuggingFace cache'inde mevcut)
"""
import os
import json
import threading
from pathlib import Path

import torch
import faster_whisper
from dotenv import load_dotenv
from loguru import logger

from backend.config import LOGS_DIR, MODELS_DIR, VIDEO_METADATA
from backend.core.exceptions import FileOperationError, TranscriptionError

load_dotenv()

# -------------------------------------------------------------------------
# Ortam / donanım
# -------------------------------------------------------------------------

HF_TOKEN     = os.environ.get("HF_TOKEN", "")
DEVICE       = "cuda" if torch.cuda.is_available() else "cpu"
LOCAL_MODEL_REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.json")

# Model cache: (model_size, device) -> WhisperModel (tekrarlı transkripsiyonlarda bellek/disk tasarrufu)
_model_cache: dict[tuple[str, str], faster_whisper.WhisperModel] = {}

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
            model = faster_whisper.WhisperModel(
                model_id,
                device=DEVICE,
                compute_type="int8" if DEVICE == "cpu" else "float16",
                download_root=download_root,
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

    model = _load_whisper_model(model_size)

    _status("Ses analiz ediliyor (konuşma → metin)...", 33)
    _check_cancelled()
    
    # Transkripsiyon
    try:
        segments, info = model.transcribe(
            audio_file,
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
    except (RuntimeError, ValueError, OSError) as exc:
        raise TranscriptionError("Ses transkripsiyonu başarısız oldu", details=str(exc)) from exc
    
    logger.info(f"✅ Transkript tamamlandı. Dil: {info.language}, {info.language_probability:.2f}")
    
    # Segmentleri liste olarak topla
    segment_list = []
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
    
    logger.success(f"✅ {len(segment_list)} segment işlendi.")

    # 2. JSON'a kaydet
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
