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

## ASS Üretimi ve Chunking

1. **Normalize**: Unicode normalize, zero-width temizleme ve whitespace collapse
2. **Chunking**: max kelime + süre sınırları (`max_chunk_duration`, `min_chunk_duration`)
3. **Line break**: güçlü ve zayıf noktalama kuralları
4. **Animasyon**: `_calculate_animation_tags()` – pop/fade/slide_up
5. **Format**: ASS `Dialogue` satırları
6. **PlayRes**: 1080x1920

Frontend preview parity için aynı zamanlama mantığı `frontend/src/utils/subtitleTiming.ts` içinde taşınır.

## Animasyon Tipleri

| Tip | Açıklama |
|-----|----------|
| pop | Okunma anında %140 büyüme, highlight renk |
| fade | Fade in/out |
| slide_up | Yukarı kayma |
| none | Statik |

## Burn-in

- FFmpeg `-vf "ass=..."` filter
- Libass overlay CPU tarafında çalışır; mevcut yol tam GPU decode/render pipeline değildir
- Video encode için önce `h264_nvenc` denenir, başarısızsa `libx264` CPU fallback kullanılır
- `REQUIRE_NVENC_FOR_BURN=1` ile NVENC zorunlu hale getirilebilir
- NVENC fallback durumunda stderr tail ve input stream forensic bilgisi rapora yazılır

## Overflow ve Güvenlik

- Render sırasında satır genişliği, safe-area ihlali ve lower-third güvenli alan sinyali ölçülür.
- Gerekirse önce daha konservatif chunking denenir.
- Single layout için alt bant/lower-third grafiği algılanırsa `lower_third_safe` profili seçilir.
- v2.1'de otomatik style swap yapılmaz; çözülemeyen taşmalar `partial` degrade olarak raporlanır.
- Son rapor `last_render_report` içinde `subtitle_overflow_detected`, `max_rendered_line_width_ratio`, `safe_area_violation_count`, `resolved_safe_area_profile`, `lower_third_collision_detected`, `chunk_dump` gibi alanlar üretir.

## Kullanım Yerleri

- YouTube pipeline: Her klip için ASS → burn
- Manual cut: run_manual_clip içinde
- Reburn: reburn_subtitles() – mevcut videoya yeni stil
