# Transcription Servisi

Ses dosyasından kelime düzeyinde transkripsiyon. faster-whisper (Whisper large-v3) kullanır.

## Dosya

`backend/services/transcription.py`

## Ana Fonksiyon

```python
def run_transcription(
    audio_file: str,
    output_json: str | None = None,
    status_callback=None,
    language: str = "tr",
    model_size: str = "large-v3",
    cancel_event: threading.Event | None = None,
) -> str
```

## Model Yükleme

- **Öncelik**: Yerel model (`workspace/models/whisper-{size}/`) → HuggingFace cache → Systran/faster-whisper
- **Cihaz**: CUDA varsa GPU, yoksa CPU
- **Compute**: CPU'da int8, GPU'da float16
- **Lazy**: Model ilk transkripsiyonda yüklenir (VRAM tasarrufu)

## Çıktı Formatı

```json
[
  {
    "start": 0.0,
    "end": 2.5,
    "text": "Merhaba dünya",
    "speaker": "Unknown",
    "words": [
      {"word": "Merhaba", "start": 0.0, "end": 0.5, "score": 1.0},
      {"word": "dünya", "start": 0.5, "end": 2.5, "score": 1.0}
    ]
  }
]
```

## Parametreler

| Parametre | Varsayılan | Açıklama |
|-----------|------------|----------|
| beam_size | 5 | Arama genişliği |
| word_timestamps | True | Kelime zaman damgaları |
| vad_filter | True | Ses aktivite filtreleme |
| vad_parameters | min_silence_duration_ms=500 | Sessizlik eşiği |
| cancel_event | None | Pipeline iptal sinyali |

## Ortam Değişkenleri

- `HF_TOKEN`: HuggingFace token (opsiyonel, gated modeller için)
- `DEVICE`: cuda / cpu (otomatik tespit edilir)

## Kullanım Yerleri

- YouTube pipeline: İndirme sonrası ses ayrıştırma → transkripsiyon
- Upload: `ensure_project_transcript()` → `run_transcription()`

## v2.1 Notları

- `cancel_event` keyword arg olarak geçirilir; iptal kontrolü model yükleme, transkripsiyon ve yazma aşamalarında yapılır.
- Segmentlerde `words=[]` görülebilir; boundary snap ve clip-local transcript işlemleri bu durumda degrade/fallback kurallarıyla çalışır.
- `word_coverage_ratio`, boundary snap kararlarında kullanılan türetilmiş kalite metriğidir.
