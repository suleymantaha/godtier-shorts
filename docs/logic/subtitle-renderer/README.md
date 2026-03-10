# Subtitle Renderer

ASS altyazı üretimi ve videoya burn-in. SubtitleRenderer sınıfı.

## Dosya

`backend/services/subtitle_renderer.py`

> Not: Subtitle renderer için **tek doğru giriş noktası** `backend/services/subtitle_renderer.py` dosyasıdır.
> Kök dizindeki eski renderer modülü kullanılmamalıdır; importlarda yalnızca `backend.services.subtitle_renderer` kullanın.

## Sınıf

`SubtitleRenderer(style: SubtitleStyle)`

## Ana Metodlar

| Metod | Açıklama |
|-------|----------|
| `generate_ass_file(transcript_json, output_ass, max_words_per_screen=3)` | JSON → ASS dosyası |
| `burn_subtitles_to_video(input_video, ass_file, output_video)` | Altyazıyı videoya göm |

## ASS Üretimi

1. **Chunking**: `_smart_chunking()` – max_words_per_screen ile kelime grupları
2. **Animasyon**: `_calculate_animation_tags()` – pop/fade/slide_up
3. **Format**: ASS Events (Dialogue satırları)
4. **PlayRes**: 1080x1920 (Shorts formatı)

## Animasyon Tipleri

| Tip | Açıklama |
|-----|----------|
| pop | Okunma anında %140 büyüme, highlight renk |
| fade | Fade in/out |
| slide_up | Yukarı kayma |
| none | Statik |

## Burn-in

- FFmpeg `-vf "ass=..."` filter
- CUDA desteği (varsa hwupload_cuda, scale_cuda)
- Girdi video üzerine ASS overlay

## Kullanım Yerleri

- YouTube pipeline: Her klip için ASS → burn
- Manual cut: run_manual_clip içinde
- Reburn: reburn_subtitles() – mevcut videoya yeni stil
