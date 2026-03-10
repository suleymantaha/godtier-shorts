# YouTube Pipeline

YouTube URL ile tam otomatik short üretim akışı. CONFIGURE sayfasındaki JobForm'dan tetiklenir.

## Akış

```
yt-dlp indirme → Ses ayrıştırma → faster-whisper transkripsiyon → LLM viral analiz → Klip üretimi (YOLO + ASS + burn-in)
```

## Adımlar

1. **Proje Hazırlığı**: Video ID alınır (`yt-dlp --get-id`), proje klasörü `yt_{video_id}` oluşturulur
2. **İndirme**: `yt-dlp` ile en yüksek kalitede mp4 indirilir
3. **Ses Ayrıştırma**: FFmpeg ile 16kHz mono WAV çıkarılır
4. **Transkripsiyon**: faster-whisper (large-v3) ile kelime düzeyinde zaman damgaları
5. **Viral Analiz**: LLM (OpenRouter/Claude veya local) ile viral segmentler seçilir
6. **Klip Üretimi**: Her segment için:
   - Timestamp kaydırma (`_shift_timestamps`)
   - ASS altyazı üretimi
   - YOLO + SteadyCam crop (9:16)
   - Burn-in (FFmpeg CUDA)

## Tetikleyici

- **Frontend**: `JobForm` → `jobsApi.start()`
- **API**: `POST /api/start-job`
- **Backend**: `backend/api/routes/jobs.py` → `run_gpu_job()` → `GodTierShortsCreator.run_pipeline()`

## Parametreler

| Parametre | Açıklama |
|-----------|----------|
| `youtube_url` | YouTube video URL |
| `style_name` | Altyazı stili (TIKTOK, HORMOZI vb.) |
| `ai_engine` | local / cloud |
| `num_clips` | Üretilecek klip sayısı |
| `duration_min`, `duration_max` | Viral segment süre aralığı (sn) |
| `skip_subtitles` | Altyazı atlama |
| `layout` | single / split |

## Çıktı

- `workspace/projects/yt_{video_id}/shorts/short_{n}_{hook_slug}.mp4`
- Her klip için `.json` metadata (transcript, viral_metadata, render_metadata)

## İlgili

- [Orchestrator](../../backend/core/orchestrator.py) – `run_pipeline()`
- [Transcription](../logic/transcription/README.md)
- [Viral Analyzer](../logic/viral-analyzer/README.md)
- [Video Processor](../logic/video-processor/README.md)
