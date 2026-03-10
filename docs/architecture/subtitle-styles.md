# Subtitle Styles

ASS (Advanced SubStation Alpha) altyazı stil tanımları. StyleManager ile preset yönetimi.

## Dosya

`backend/services/subtitle_styles.py`

## Sınıflar

- **SubtitleStyle**: Pydantic model, font, renk, animasyon vb.
- **SubtitleCategory**: dynamic, minimal, creative, accessible, corporate
- **StyleManager**: Preset listesi ve get_preset()

## Preset Stiller

| Stil | Kategori | Özellik |
|------|----------|---------|
| HORMOZI | dynamic | Pop animasyon, büyük font |
| MRBEAST | dynamic | Enerjik, vurgulu |
| TIKTOK | dynamic | Kısa form uyumlu |
| MINIMALIST | minimal | Sade, az efekt |
| CUSTOM | - | Kullanıcı tanımlı |

## SubtitleStyle Alanları

- **Temel**: font_name, font_size, primary_color, highlight_color, outline_color
- **Animasyon**: animation_type (pop, slide_up, fade, none), animation_duration
- **Konum**: alignment, margin_v, position_x, position_y
- **Efektler**: blur, border_radius, gradient_colors

## API

- `StyleManager.list_presets()`: Tüm preset isimleri
- `StyleManager.get_preset(name)`: SubtitleStyle döner
- `GET /api/styles`: Frontend dropdown için stil listesi

## ASS Format

Renkler `&HAABBGGRR` (Alpha, Blue, Green, Red) formatında.
