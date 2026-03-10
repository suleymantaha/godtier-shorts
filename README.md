# God-Tier Shorts

**God-Tier Shorts** uzun videolardan tamamen lokal-first, GPU hızlandırmalı, kinetic altyazılı dikey (9:16) kısa videolar (shorts, reels, tiktok) üretmek için tasarlanmış bir otomasyon aracıdır. [faster-whisper](https://github.com/Systran/faster-whisper) transkripsiyonları, YOLO tabanlı akıllı kamera takibi, LLM destekli (OpenRouter/Claude) viral analiz motoru ve React/Vite tabanlı arayüzü tek bir çatı altında birleştirir.

## Özellikler

- **Transkript**: faster-whisper large-v3, kelime düzeyinde zaman damgaları, VRAM optimizasyonu
- **Viral Analiz**: LLM (OpenRouter/Claude veya LM Studio) ile viral segment seçimi
- **Video İşleme**: YOLO11 + SteadyCam modu, 9:16 crop, NVENC hızlandırma
- **Kinetic Altyazı**: ASS stilleri (HORMOZI, TIKTOK vb.), pop/fade animasyonları, burn-in
- **Arayüz**: React, Zustand, Tailwind, WebSocket ile gerçek zamanlı job takibi

## Hızlı Başlangıç

### Kurulum

```bash
git clone https://github.com/suleymantaha/godtier-shorts.git
cd godtier-shorts

pip install -r requirements.txt
cd frontend && npm install
```

> Not: `POST /api/upload` ve diğer `multipart/form-data` kullanan form/upload endpoint'lerinin çalışması için backend'de `python-multipart` bağımlılığı kurulu olmalıdır (requirements içinde yer alır).

### Ortam Değişkenleri

`.env.example` dosyasını `.env` olarak kopyalayın ve gerekli anahtarları doldurun:

- `OPENROUTER_API_KEY` – Cloud LLM (viral analiz)
- `LMSTUDIO_HOST` – Local LLM (opsiyonel)
- `HF_TOKEN` – HuggingFace (faster-whisper modelleri, opsiyonel)

### Çalıştırma

```bash
# Tek komutla (backend + frontend)
./run.sh

# veya ayrı ayrı:
python -m backend.main          # Backend: http://0.0.0.0:8000
cd frontend && npm run dev      # Frontend: http://localhost:5173
```

## Sayfa Rehberi

| Sayfa | Açıklama | Dokümantasyon |
|-------|----------|---------------|
| **CONFIGURE** | YouTube URL, stil, job kuyruğu, klip galerisi | [docs/pages/configure](docs/pages/configure.md) |
| **AUTO CUT** | Video yükleme, zaman aralığı, kesim | [docs/pages/auto-cut](docs/pages/auto-cut.md) |
| **SUBTITLE EDIT** | Proje/klip transkript düzenleme | [docs/pages/subtitle-editor](docs/pages/subtitle-editor.md) |
| **Clip Editor** | Kadraj, stil, reburn | [docs/pages/clip-editor](docs/pages/clip-editor.md) |

## İşlem Akışları

| İşlem | Açıklama | Dokümantasyon |
|-------|----------|---------------|
| YouTube Pipeline | URL → indirme → transkripsiyon → viral analiz → klip üretimi | [docs/flows/youtube-pipeline](docs/flows/youtube-pipeline.md) |
| Upload & Transcribe | Video yükleme, hash, transkripsiyon | [docs/flows/upload-transcribe](docs/flows/upload-transcribe.md) |
| Manual Cut | Zaman aralığı veya cut_points ile kesim | [docs/flows/manual-cut](docs/flows/manual-cut.md) |
| Batch Clips | Aralıkta AI ile toplu klip | [docs/flows/batch-clips](docs/flows/batch-clips.md) |
| Reburn | Altyazı yeniden basma (transkript kaydetme dahil) | [docs/flows/reburn](docs/flows/reburn.md) |

## Mimari (Backend Servisleri)

> Not: Subtitle renderer için **tek doğru giriş noktası** `backend/services/subtitle_renderer.py` dosyasıdır.
> Proje kökünde benzer isimli renderer modülü bulunmaz; importlarda yalnızca `backend.services.subtitle_renderer` kullanın.

| Servis | Açıklama | Dokümantasyon |
|--------|----------|---------------|
| Transcription | faster-whisper, kelime zaman damgaları | [docs/architecture/transcription](docs/architecture/transcription.md) |
| Viral Analyzer | LLM viral segment seçimi | [docs/architecture/viral-analyzer](docs/architecture/viral-analyzer.md) |
| Video Processor | YOLO + SteadyCam crop | [docs/architecture/video-processor](docs/architecture/video-processor.md) |
| Subtitle Styles | ASS preset stilleri | [docs/architecture/subtitle-styles](docs/architecture/subtitle-styles.md) |
| Subtitle Renderer | Burn-in | [docs/architecture/subtitle-renderer](docs/architecture/subtitle-renderer.md) |

## Veri Akışı

### Mimari

```mermaid
flowchart TB
    subgraph Frontend [Frontend]
        Config[CONFIGURE]
        AutoCut[AUTO CUT]
        SubEdit[SUBTITLE EDIT]
        ClipEdit[Clip Editor]
    end

    subgraph API [API]
        StartJob["POST /start-job"]
        Upload["POST /upload"]
        Manual["POST /process-manual"]
        Batch["POST /process-batch"]
        Reburn["POST /reburn"]
    end

    subgraph Core [Core]
        Orch[Orchestrator]
        Trans[Transcription]
        Viral[Viral Analyzer]
        Video[Video Processor]
        Render[Subtitle Renderer]
    end

    Config --> StartJob
    AutoCut --> Upload
    AutoCut --> Manual
    AutoCut --> Batch
    SubEdit --> Reburn
    ClipEdit --> Manual
    ClipEdit --> Reburn

    StartJob --> Orch
    Upload --> Trans
    Manual --> Orch
    Batch --> Orch
    Reburn --> Orch

    Orch --> Trans
    Orch --> Viral
    Orch --> Video
    Orch --> Render
```

### YouTube Pipeline Akışı

```mermaid
flowchart TB
    YT["YouTube URL"]
    A1["yt-dlp indirme"]
    A2["FFmpeg ses çıkarma"]
    A3["faster-whisper transkripsiyon"]
    A4["LLM viral analiz"]
    B1["ASS altyazı üretimi"]
    B2["YOLO + SteadyCam crop"]
    B3["Burn-in"]
    Shorts["9:16 Short videolar"]

    YT --> A1 --> A2 --> A3 --> A4
    A4 --> B1 --> B2 --> B3 --> Shorts
```

## Transkripsiyon Notu

- **Mevcut durum**: Üretimde aktif transkripsiyon motoru `faster-whisper` (large-v3).
- **Hedef durum**: İleride ihtiyaç olursa `WhisperX` tabanlı bir akışa geri dönüş değerlendirilebilir.
- **Geçiş adımları (WhisperX'e dönüş planı)**:
  1. `backend/services/transcription.py` içinde WhisperX pipeline'ını yeniden etkinleştir ve kelime zaman damgası çıktısını mevcut `transcript.json` şemasıyla uyumlu tut.
  2. Orchestrator ve durum mesajlarında `faster-whisper`/`WhisperX` adlandırmalarını tekilleştir (`backend/core/orchestrator.py`, API progress mesajları).
  3. `docs/` ve test fixture'larında terminolojiyi eşleştir, transkripsiyon entegrasyon testlerini WhisperX senaryosu için tekrar çalıştır.

## API Özeti

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/styles` | Altyazı stilleri |
| POST | `/api/start-job` | YouTube pipeline başlat |
| GET | `/api/jobs` | Job listesi |
| POST | `/api/cancel-job/{id}` | Job iptal |
| GET | `/api/projects` | Proje listesi |
| GET | `/api/clips` | Klip listesi (güvenli clip URL ile) |
| GET | `/api/projects/{project_id}/master` | Proje master videosu (kontrollü erişim) |
| GET | `/api/projects/{project_id}/shorts/{clip_name}` | Shorts altındaki `.mp4/.json` dosyası (kontrollü erişim) |
| POST | `/api/upload` | Video yükleme |
| GET | `/api/transcript` | Proje transkripti |
| POST | `/api/transcript` | Transkript kaydet |
| POST | `/api/process-manual` | Manuel klip render |
| POST | `/api/reburn` | Altyazı yeniden basma |
| POST | `/api/process-batch` | Toplu klip üretimi |
| POST | `/api/manual-cut-upload` | Video + kesim |
| WS | `/ws/progress` | Job ilerleme |

## Güvenli dosya erişimi

- Doğrudan `/projects` mount erişimi kapatılmıştır.
- Public klip erişimi yalnızca `/api/projects/{project_id}/shorts/{clip_name}` endpoint'i üzerinden yapılır.
- Master/transcript gibi proje kök dosyaları doğrudan erişime kapalıdır; master için `/api/projects/{id}/master` endpoint'i kullanılır.

## Testler

```bash
# Backend
pytest backend/tests -v
pytest backend/tests -v -m "not integration"

# Frontend
cd frontend && npm run test
```

**Scripts:** `scripts/README.md` – reburn_clip, test_subtitle_styles vb.

## Katkı

Pull Request göndererek destek olabilirsiniz.

---

_Bu proje, video içerik üreticileri için tam donanımlı ve yerel makinede maksimum performans sağlamak amacıyla üretilmiştir._
