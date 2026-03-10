# God-Tier Shorts — Detaylı Repo Analiz Raporu

**Tarih:** 9 Mart 2026  
**Analiz Türü:** Teknik mimari, kod kalitesi, güvenlik ve iş akışı incelemesi

---

## 1. Proje Özeti

**God-Tier Shorts**, uzun videolardan dikey (9:16) kısa videolar (Shorts, Reels, TikTok) üreten, **lokal-first** ve **GPU hızlandırmalı** bir otomasyon aracıdır. YouTube URL’den başlayarak indirme, transkripsiyon, viral segment seçimi, video kırpma ve kinetic altyazı burn-in’e kadar tüm süreci tek bir uygulama ile yönetir.

### Hedef Kitle
- Video içerik üreticileri
- Yerel makinede maksimum performans isteyen kullanıcılar
- YouTube’dan otomatik short üretimi yapan kullanıcılar

---

## 2. Teknoloji Yığını

### Backend
| Bileşen | Teknoloji | Versiyon |
|---------|-----------|----------|
| Web Framework | FastAPI | ≥0.104.0 |
| ASGI Server | Uvicorn | ≥0.24.0 |
| Veri Doğrulama | Pydantic | ≥2.5.0 |
| Loglama | Loguru | ≥0.7.0 |
| AI/ML | PyTorch, TorchVision | ≥2.0.0 |
| Nesne Tespiti | Ultralytics (YOLO11) | ≥8.0.0 |
| Transkripsiyon | faster-whisper | ≥1.0.0 |
| Bilgisayarlı Görü | OpenCV | ≥4.8.0 |
| LLM API | OpenAI SDK | ≥1.3.0 |
| HTTP Client | httpx | ≥0.25.0 |
| Video İndirme | yt-dlp | ≥2024.0.0 |

### Frontend
| Bileşen | Teknoloji | Versiyon |
|---------|-----------|----------|
| Framework | React | 19.2.0 |
| Build Tool | Vite | 7.3.1 |
| State | Zustand | 5.0.11 |
| Stil | Tailwind CSS | 4.2.1 |
| Animasyon | Framer Motion | 12.34.3 |
| İkonlar | Lucide React | 0.575.0 |
| Test | Vitest | 4.0.18 |

### Harici Sistemler
- **ffmpeg** — video işleme, ses ayrıştırma, NVENC
- **yt-dlp** — YouTube indirme
- **OpenRouter / LM Studio** — LLM viral analiz

---

## 3. Mimari Yapı

### 3.1 Dizin Yapısı

```
godtier-shorts/
├── backend/
│   ├── api/
│   │   ├── routes/          # jobs, clips, editor
│   │   ├── server.py       # FastAPI fabrikası
│   │   └── websocket.py     # WebSocket manager
│   ├── core/
│   │   └── orchestrator.py # Ana orkestratör
│   ├── services/
│   │   ├── transcription.py
│   │   ├── viral_analyzer.py
│   │   ├── video_processor.py
│   │   ├── subtitle_styles.py
│   │   └── subtitle_renderer.py
│   ├── config.py           # Path, sabitler
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/
│       ├── hooks/
│       ├── store/
│       ├── utils/
│       └── api/
├── workspace/              # Runtime artifact'lar (gitignored)
│   ├── downloads/
│   ├── temp/
│   ├── projects/
│   ├── logs/
│   └── metadata/
├── docs/                   # Dokümantasyon
├── scripts/                # Yardımcı scriptler
└── requirements.txt
```

### 3.2 Veri Akışı

```
YouTube URL → yt-dlp → master.mp4 → FFmpeg → master.wav
                                                    ↓
                                            faster-whisper
                                                    ↓
                                            transcript.json
                                                    ↓
                                            ViralAnalyzer (LLM)
                                                    ↓
                                            viral_segments.json
                                                    ↓
                    ┌───────────────────────────────────────────────┐
                    │  Her segment için:                             │
                    │  • timestamp shift → shifted.json               │
                    │  • SubtitleRenderer → ASS → burn-in             │
                    │  • VideoProcessor (YOLO + SteadyCam) → 9:16      │
                    │  • shorts/*.mp4                                 │
                    └───────────────────────────────────────────────┘
```

### 3.3 Proje Tabanlı Yapı

`ProjectPaths` sınıfı ile her proje için ayrı klasör:

- `project_id/` (örn. `yt_abc123`)
  - `master.mp4`, `master.wav`
  - `transcript.json`
  - `viral.json`
  - `shorts/` — üretilen kısa videolar

---

## 4. Ana Bileşenler

### 4.1 Orchestrator (`GodTierShortsCreator`)

- **Yüklenen:** `run_transcription`, `ViralAnalyzer`, `VideoProcessor`, `StyleManager`, `SubtitleRenderer`
- **Ana fonksiyonlar:**
  - `run_pipeline()` — YouTube pipeline (indirme → transkript → viral analiz → klip üretimi)
  - `run_manual_clip()` — tek klip
  - `run_manual_clips_from_cut_points()` — kesim noktalarına göre birden fazla klip
  - `run_batch_manual_clips()` — AI ile toplu klip
  - `reburn_subtitles()` — altyazı yeniden basma
  - `transcribe_local_video()` — yerel video transkripsiyonu

**Refactor:** `_cut_and_burn_clip()` ortak video kesme + burn-in bloğu; tekrar kaldırıldı.

### 4.2 Viral Analyzer

- **LLM:** OpenRouter (cloud) veya LM Studio (local)
- **Model:** `moonshotai/kimi-k2.5` (cloud)
- **Pydantic:** `ViralSegment`, `ViralAnalysisResult` — yapılandırılmış çıktı
- **Fallback:** LLM başarısız olursa yoğunluk tabanlı segment seçimi

### 4.3 Video Processor

- **YOLO11** — nesne tespiti (kamera takibi)
- **SteadyCam** — yumuşak hareket
- **Lazy-load:** GPU yalnızca ilk `create_viral_short()` çağrısında kullanılır (Whisper ile VRAM çakışması önlenir)
- **NVENC** — ffmpeg ile hızlandırılmış encode

### 4.4 Subtitle Renderer

- **ASS** — Advanced Subtitle format
- **Preset stiller:** HORMOZI, TIKTOK vb.
- **Pop/fade animasyonları, burn-in**

---

## 5. API Özeti

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/styles` | Altyazı stilleri |
| POST | `/api/start-job` | YouTube pipeline başlat |
| GET | `/api/jobs` | Job listesi |
| POST | `/api/cancel-job/{id}` | Job iptal |
| GET | `/api/projects` | Proje listesi |
| GET | `/api/clips` | Klip listesi |
| POST | `/api/upload` | Video yükleme |
| GET | `/api/transcript` | Proje transkripti |
| POST | `/api/transcript` | Transkript kaydet |
| POST | `/api/process-manual` | Manuel klip render |
| POST | `/api/reburn` | Altyazı yeniden basma |
| POST | `/api/process-batch` | Toplu klip üretimi |
| POST | `/api/manual-cut-upload` | Video + kesim |
| WS | `/ws/progress` | Job ilerleme (WebSocket) |

---

## 6. Frontend Sayfaları

| Sayfa | Açıklama |
|-------|----------|
| **CONFIGURE** | YouTube URL, stil, job kuyruğu, klip galerisi |
| **AUTO CUT** | Video yükleme, zaman aralığı, kesim |
| **SUBTITLE EDIT** | Proje/klip transkript düzenleme |
| **Clip Editor** | Kadraj, stil, reburn |

---

## 7. Güvenlik ve Kalite

### 7.1 Path Traversal Koruması

`config.py` içinde:

- `sanitize_project_name()` — sadece güvenli karakterler
- `sanitize_clip_name()` — dosya adı güvenliği
- `get_project_dir()` — sanitize edilmiş proje yolu

### 7.2 Job ID Çakışması (Düzeltilmiş)

`conflict-error-scenarios.md`’e göre timestamp tabanlı job ID’ler UUID ile birleştirildi:

- `batch_{ts}_{uuid.hex[:6]}` formatı
- Aynı saniyede çakışma riski azaltıldı

### 7.3 Temp Dosya Sızıntısı (Düzeltilmiş)

`try/finally` ile cleanup garantilendi; hata durumunda geçici dosyalar temizleniyor.

---

## 8. Test ve Dokümantasyon

### Testler

- **Backend:** pytest (`backend/tests/`)
- **Frontend:** Vitest (`frontend/src/test/`)
- **Integration:** `workspace/video` gerektiren testler `-m "not integration"` ile atlanabilir

### Dokümantasyon

- `docs/` altında sayfa, akış ve mimari dokümanları
- `docs/analysis/` — çakışma analizi, refactor özeti
- `scripts/README.md` — yardımcı scriptler

---

## 9. Güçlü Yönler

1. **Lokal-first:** Veri yalnızca yerel makinede işlenir
2. **GPU optimizasyonu:** YOLO lazy-load, NVENC ile hız
3. **Modüler mimari:** Servisler ayrı modüllerde, net sorumluluklar
4. **Proje tabanlı yapı:** Her proje için izole klasör
5. **Gerçek zamanlı UI:** WebSocket ile job progress
6. **Dokümantasyon:** Sayfa, akış ve mimari dokümanları
7. **Hata analizi:** Çakışma senaryoları dokümante edilmiş

---

## 10. İyileştirme Önerileri

| Öncelik | Öneri | Durum |
|---------|-------|-------|
| P0 | Job ID UUID kullanımı | Uygulandı |
| P1 | Temp dosya cleanup | Uygulandı |
| P2 | WebSocket broadcast timeout | Kabul edilebilir (log var) |
| P3 | Docker/container desteği | Eksik |
| P3 | `.env.example` güncelleme | Kontrol edilmeli |
| P4 | CI/CD pipeline | Eksik |

---

## 11. Bağımlılık Yönetimi

- **Python:** `requirements.txt` (pip)
- **PyTorch:** `torch`, `torchvision` — CUDA için ayrı kurulum gerekebilir
- **Node:** `node_modules` — frontend bağımlılıkları

---

## 12. Sonuç

**God-Tier Shorts**, uzun videolardan dikey short üretimi için uçtan uca bir akış sunan, iyi yapılandırılmış bir projedir. Backend servisleri, orkestratör ve frontend arasındaki sorumluluklar net ayrılmış; proje tabanlı yapı ve path güvenliği düşünülmüş. Çakışma ve temp dosya sızıntısı gibi riskler dokümante edilmiş ve düzeltilmiş. GPU, CUDA ve ffmpeg gibi harici bağımlılıklar nedeniyle kurulum biraz karmaşık olabilir; Docker desteği eklenmesi dağıtımı kolaylaştırabilir.

---

*Rapor, reponun mevcut durumuna göre hazırlanmıştır.*
