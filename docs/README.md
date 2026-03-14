# GodTier Shorts Dokümantasyonu

Ana proje: [README.md](../README.md)

## Kurulum

- [API Key ve .env Rehberi](./api-key-setup.md)

## Sayfalar (UI)


| Sayfa                                       | Açıklama                                      |
| ------------------------------------------- | --------------------------------------------- |
| [CONFIGURE](./pages/configure.md)           | YouTube URL, stil, job kuyruğu, klip galerisi |
| [AUTO CUT](./pages/auto-cut.md)             | Video yükleme, zaman aralığı, kesim           |
| [SUBTITLE EDIT](./pages/subtitle-editor.md) | Proje/klip transkript düzenleme               |
| [Clip Editor](./pages/clip-editor.md)       | Kadraj, stil, reburn                          |


## İş Akışları


| Akış                                                | Açıklama                                                     |
| --------------------------------------------------- | ------------------------------------------------------------ |
| [YouTube Pipeline](./flows/youtube-pipeline.md)     | URL → indirme → transkripsiyon → viral analiz → klip üretimi |
| [Upload & Transcribe](./flows/upload-transcribe.md) | Video yükleme, hash, transkripsiyon                          |
| [Manual Cut](./flows/manual-cut.md)                 | Zaman aralığı veya cut_points ile kesim                      |
| [Batch Clips](./flows/batch-clips.md)               | Aralıkta AI ile toplu klip                                   |
| [Reburn](./flows/reburn.md)                         | Altyazı yeniden basma (transkript kaydetme dahil)            |


## Mimari (Backend Servisleri)

> Not: Subtitle renderer için **tek doğru giriş noktası** `backend/services/subtitle_renderer.py` dosyasıdır.
> Kök dizindeki eski renderer modülü kullanılmamalıdır; importlarda yalnızca `backend.services.subtitle_renderer` kullanın.

| Servis                                                   | Açıklama                               |
| -------------------------------------------------------- | -------------------------------------- |
| [Transcription](./architecture/transcription.md)         | faster-whisper, kelime zaman damgaları |
| [Viral Analyzer](./architecture/viral-analyzer.md)       | LLM viral segment seçimi               |
| [Video Processor](./architecture/video-processor.md)     | YOLO + SteadyCam crop                  |
| [Subtitle Styles](./architecture/subtitle-styles.md)     | ASS preset stilleri                    |
| [Subtitle Renderer](./architecture/subtitle-renderer.md) | Burn-in                                |

