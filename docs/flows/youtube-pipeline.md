# YouTube Pipeline

YouTube URL ile tam otomatik short üretim akışı. CONFIGURE sayfasındaki JobForm'dan tetiklenir.

## Akış

```
yt-dlp indirme → Ses ayrıştırma → faster-whisper transkripsiyon → LLM viral analiz → boundary snap → tracking/crop → ASS → burn-in → kalite metadata
```

## Adımlar

1. **Proje Hazırlığı**: Video ID alınır (`yt-dlp --get-id`), proje klasörü `yt_{video_id}` oluşturulur
2. **İndirme**: `yt-dlp` ile en yüksek kalitede mp4 indirilir
3. **Ses Ayrıştırma**: FFmpeg ile 16kHz mono WAV çıkarılır
4. **Transkripsiyon**: faster-whisper (large-v3) ile kelime düzeyinde zaman damgaları
5. **Viral Analiz**: LLM (OpenRouter/Claude veya local) ile viral segmentler seçilir
6. **Klip Üretimi**: Her segment için:
   - Transcript kalite metrikleri ve `word_coverage_ratio`
   - Boundary snapping (kaliteye göre açık / dar / kapalı)
   - ASS altyazı üretimi
   - YOLO tracking + crop + A/V doğrulama
   - Burn-in ve `render_quality_score`

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
- Public erişim: `/api/projects/{project_id}/shorts/{clip_name}`
- Her klip için `.json` metadata:
  - `transcript`
  - `viral_metadata`
  - `render_metadata.tracking_quality`
  - `render_metadata.transcript_quality`
  - `render_metadata.audio_validation`
  - `render_metadata.subtitle_layout_quality`
  - `render_metadata.debug_timing`
  - `render_metadata.render_quality_score`
  - `render_metadata.debug_artifacts` (`DEBUG_RENDER_ARTIFACTS=1` ise)

## İlgili

- [Orchestrator](../../backend/core/orchestrator.py) – `run_pipeline()`
- [Transcription](../architecture/transcription.md)
- [Viral Analyzer](../architecture/viral-analyzer.md)
- [Video Processor](../architecture/video-processor.md)
