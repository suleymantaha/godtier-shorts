---
trigger: always_on
---

---

name: godtier-shorts
description: God-Tier Shorts mimarisi için WhisperX, YOLO/NVENC, OpenRouter/Claude tabanlı LLM, kinetic ASS altyazı motoru ve Tauri/React/Tailwind UI orkestrasyonunu açıklar; bu projede video-short otomasyonu, altyapı değişiklikleri veya yeni özellikler istenirken ajana hangi mimariyi, araçları ve varsayılan tercihleri kullanması gerektiğini tarif eder.

---

# God-Tier Shorts

## Amaç

Bu skill, **God-Tier Shorts** projesinde uzun videolardan tamamen lokal-first, GPU hızlandırmalı, kinetic altyazılı dikey (9:16) kısa videolar üretirken ajana rehberlik etmek için tasarlanır.  
Backend video hattı, LLM tabanlı viral analiz, dikey kırpma ve altyazı motoru ile Tauri/React tabanlı UI mimarisi tek bir çatı altında özetlenir.

## Ne Zaman Bu Skill Kullanılmalı?

- Kullanıcı bu projede `God-Tier Shorts`, `shorts otomasyonu`, `WhisperX pipeline`, `YOLO dikey kırpma`, `NVENC render`, `OpenRouter / Claude`, `kinetic altyazı` gibi ifadeler kullanıyorsa.
- Bu repoda:
  - Yeni **video işleme** özelliği eklenmesi,
  - **WhisperX / LLM hattı**nda değişiklik yapılması,
  - **YOLO + NVENC** kırpma/encode hattının geliştirilmesi,
  - **Kinetic altyazı (.ass + FFmpeg)** tarafında iyileştirme istenmesi,
  - **Manual Editor** bileşenleri veya WebSocket orkestrasyonunda çalışma yapılması,
  - Loglama / hata yakalama davranışının güncellenmesi
    istendiğinde.

Bu skill sadece bu proje için geçerlidir.

## Mimari Özet

### 1. Beyin / Transkript Hattı (WhisperX)

- İndirme: `yt-dlp` ile YouTube (veya benzeri kaynaklardan) ses/video alınır.
- Transkript:
  - **WhisperX** `large-v3` modeli, `float16` veya `int8_float16` CUDA üzerinde çalıştırılır.
  - VRAM optimizasyonu: WhisperX bittikten sonra model VRAM'den boşaltılır (Lazy Load).
  - Çıktı:
    - `video_metadata.json`: her segment için `start`, `end`, `text`, `speaker`, `words[]`.

### 2. Viral Analiz (OpenRouter / Claude)

- Sorumlu bileşen: `ViralAnalyzer`.
- Varsayılan motor:
  - **OpenRouter** üzerinden `moonshotai/kimi-k2.5` veya `Claude 3.5 Sonnet`.
- Structured output:
  - `ViralSegment` modeli:
    - `start_time`, `end_time` (saniye),
    - `hook_text` (Videonun başında görünen kanca metni),
    - `ui_title` (Dashboard başlığı),
    - `social_caption` (Hashtag'li açıklama),
    - `viral_score` (1–100).
- Çıktı: `viral_segments.json`.

### 3. Video Kas Hattı (YOLO + NVENC)

- Sorumlu bileşen: `VideoProcessor`.
- Kırpma Teknolojisi (Smart Cameraman):
  - `ultralytics` YOLO11 ile insan tespiti.
  - **SteadyCam Modu**: Kameranın konumu `deadzone_px` (örn: 30px) kontrolü ve `lerp` yumuşatma ile konuşmacıyı takip eder.
- Encode:
  - FFmpeg `rawvideo` → `h264_nvenc` (preset `p6`, 8M bitrate).
  - GPU hızlandırmalı encode/decode.

### 4. Kinetic Altyazı Hattı (ASS + FFmpeg)

- Motor: Advanced SubStation Alpha (.ass).
- Özellikler:
  - `SubtitleStyle` / `StyleManager` presetler (HORMOZI, MRBEAST, MINIMALIST).
  - **Chunk + Karaoke**: Kelimeler `max_words_per_screen` (örn: 3) bazlı gruplanır.
  - Animasyonlar: `pop` (zoom), `fade`, `slide_up`.
- Burn-in: FFmpeg `ass` filtresi + CUDA hızlandırma.

### 5. UI & Manuel Editor (Tauri + React)

- Teknolojiler: Tauri, React, Zustand, Framer Motion, Tailwind CSS.
- **Manuel Editor**:
  - Üretilen kliplerin dikey kırpma alanlarını ve altyazılarını elle düzenleme imkanı.
  - `editor.py` API endpoint'leri üzerinden crop koordinatlarını güncelleme.
- Orkestrasyon:
  - `jobs.py`: `JobQueue` ile çoklu işlem yönetimi.
  - `websocket.py`: `/ws/progress` üzerinden %0-100 real-time log akışı.

## Ajana Özel Talimatlar

### Genel Tercihler

- **Loglama**: Her zaman `loguru` kullan.
- **GPU Yönetimi**: WhisperX ve YOLO'yu aynı anda VRAM'de tutma; birini bitirip diğerini yükle (`unload_model`).
- **Lokal-first**: Transkript ve Video yereldir, LLM analizi varsayılan buluttur (OpenRouter).

### Backend Talimatları

- `ViralAnalyzer` güncellerken metadata alanlarını (`hook_text`, `social_caption`) koru.
- `VideoProcessor` içinde `lerp` parametresini (0.1 varsayılan) yumuşaklık için kullan.
- FFmpeg komutlarında her zaman `nvenc` ve `cuda` hwaccel desteğini kontrol et.

### Frontend Talimatları

- Zustand store'da `Clip` objelerini yeni metadata alanlarıyla beraber yönet.
- `Editor` bileşeninde video resize ve drag işlemlerini hassas yap.
