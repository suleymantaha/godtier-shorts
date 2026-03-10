# Upload & Transcribe

Yerel video yükleme ve transkripsiyon. AutoCutEditor veya Editor (master modu) üzerinden tetiklenir.

## Akış

```
Video upload → SHA256 hash → Proje ID (up_{hash[:16]}) → Ses çıkarma → faster-whisper transkripsiyon
```

## Adımlar

1. **Upload**: `POST /api/upload` ile multipart form-data
2. **Hash Hesaplama**: Dosya SHA256 ile hashlenir (64KB bloklar)
3. **Proje ID**: `up_{hash[:16]}` (örn: `up_b87b3b79e3be0537`)
4. **Cache Kontrolü**: Aynı hash varsa mevcut proje reuse edilir
5. **Ses Çıkarma**: FFmpeg ile 16kHz mono WAV (`master.wav`)
6. **Transkripsiyon**: `ensure_project_transcript()` → `run_transcription()`

## Tetikleyici

- **API**: `POST /api/upload`
- **Backend**: `backend/api/routes/clips.py` → `upload_local_video()`

## Proje Yapısı

```
workspace/projects/up_{hash}/

Public klip erişimi: `/api/projects/{project_id}/shorts/{clip_name}`
Master video erişimi: `/api/projects/{project_id}/master`
├── master.mp4      # Orijinal video
├── master.wav      # Ses izi
└── transcript.json # faster-whisper çıktısı
```

## Limitler

- Maksimum dosya boyutu: 5GB (`MAX_UPLOAD_BYTES`)

## WebSocket

Transkripsiyon sırasında ilerleme mesajları WebSocket ile broadcast edilir:
- `"Ses çıkarılıyor..."`
- `"Transkript hazır..."` (cache hit)
- faster-whisper adımları

## İlgili

- [clips.py](../../backend/api/routes/clips.py) – `prepare_uploaded_project`, `ensure_project_transcript`
- [Transcription](../architecture/transcription.md)
