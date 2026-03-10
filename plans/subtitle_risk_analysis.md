# Altyazı Sistemi Genişletme - Risk Analizi Raporu

**Tarih:** 2026-03-07  
**Durum:** Analiz Tamamlandı  
**Sonraki Adım:** Implementasyon

---

## 1. Render Sürecine Etki Analizi

### 1.1 Potansiyel Riskler

#### 🔴 Yüksek Riskler

| Risk ID | Açıklama                                  | Etki                                                                                                  | Önlem                                                                                                                  |
| ------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| R-001   | Yeni alanlar Pydantic modelinin kırılması | `SubtitleStyle` modeli güncellendiğinde eski `StyleManager.get_preset()` çağrıları başarısız olabilir | **Çözüm:** Tüm yeni alanlara `Field(default=...)` verilecek, böylece geriye dönük uyumluluk korunacak                  |
| R-002   | ASS header format uyumsuzluğu             | Renderer'da yapılacak değişiklikler mevcut ASS çıktısını bozabilir                                    | **Çözüm:** `_generate_ass_header()` metodu mevcut formatı koruyacak, sadece yeni alanlar için koşullu ekleme yapılacak |
| R-003   | Font yükleme hataları                     | Yeni presetlerdeki özel fontlar sistemde yüklü değilse render başarısız                               | **Çözüm:** Fallback font listesi eklenecek                                                                             |

#### 🟡 Orta Riskler

| Risk ID | Açıklama                           | Etki                                                         | Önlem                                                                                                            |
| ------- | ---------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| R-004   | Animasyon geçiş süresi uyuşmazlığı | Yeni animasyon tipleri mevcut timing algoritmasını bozabilir | **Çözüm:** `_calculate_animation_tags()` switch-case yapısı korunacak, bilinmeyen tipler için boş string dönecek |
| R-005   | Renk formatı hataları              | ASS formatı dışında renk girilirse render başarısız          | **Çözüm:** `field_validator` ile renk formatı kontrolü eklenecek                                                 |
| R-006   | FFmpeg uyumluluk sorunları         | Yeni ASS özellikleri FFmpeg'te desteklenmeyebilir            | **Çözüm:** ASS standardı dışına çıkılmaması, test ile doğrulama                                                  |

#### 🟢 Düşük Riskler

| Risk ID | Açıklama           | Etki                                                                   | Önlem                                                                  |
| ------- | ------------------ | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| R-007   | Performance düşüşü | Büyük font boyutları veya kompleks efektler render süresini uzatabilir | **Çözüm:** Maksimum değer sınırlamaları                                |
| R-008   | Bellek sızıntısı   | Gradient veya çoklu efektler bellek kullanımını artırabilir            | **Çözüm:** Mevcut kod zaten tek stil objesi kullanıyor, değişiklik yok |

### 1.2 Etki Matrisi

```
                    ┌─────────────────┬─────────────────┬─────────────────┐
                    │   Düşük Etki    │   Orta Etki     │   Yüksek Etki   │
├───────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ subtitle_styles   │                 │  Renk validasyon│ Model değişikliği│
│ subtitle_renderer │ Animasyon gen.  │ ASS header      │ FFmpeg uyumlulu.│
│ schemas.py        │                 │ Validation      │                 │
│ Frontend          │ CSS değişiklikleri│ Type tanımları  │ API değişiklikleri│
└───────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

---

## 2. Geriye Dönük Uyumluluk Analizi

### 2.1 Mevcut Durum Koruma Stratejisi

```python
# ✅ GÜVENLİ YAKLAŞIM: Tüm yeni alanlara varsayılan değer ver

class SubtitleStyle(BaseModel):
    # ... mevcut alanlar (DEĞİŞMEYECEK) ...

    # YENİ ALANLAR (varsayılan değerlerle)
    font_weight: int = Field(default=700)  # Mevcut davranış korunur
    gradient_colors: list[str] = Field(default_factory=lambda: ["&H00FFFFFF"])  # Tek renk
    background_color: str = Field(default="&H00000000")  # Şeffaf
```

### 2.2 API Uyumluluk Matrisi

| Endpoint           | Mevcut Davranış             | Yeni Davranş           | Uyumluluk              |
| ------------------ | --------------------------- | ---------------------- | ---------------------- |
| `GET /api/jobs`    | `style_name` döner          | Aynı                   | ✅ Tam Uyumlu          |
| `POST /api/jobs`   | Preset adı kabul eder       | Preset + custom style  | ✅ Geriye Dönük Uyumlu |
| `SubtitleRenderer` | Mevcut stil objesi kullanır | Yeni alanlar opsiyonel | ✅ Tam Uyumlu          |

### 2.3 Veritabanı Etkisi

**Şu an için veritabanı kullanılmıyor** - tüm stiller kod içinde tanımlı. Bu durum geriye dönük uyumluluk açısından avantajlı çünkü:

- Veritabanı migrasyonu gerekmiyor
- Eski kayıtlar etkilenmiyor
- Tüm stiller bellekte tutuluyor

---

## 3. Test Stratejisi

### 3.1 Unit Testler

```python
# backend/tests/test_subtitle_styles.py (YENİ)
import pytest
from backend.services.subtitle_styles import SubtitleStyle, StyleManager

class TestSubtitleStyle:
    """SubtitleStyle modeli için unit testler."""

    def test_default_style_has_all_fields(self):
        """Varsayılan stil tüm alanları içermeli."""
        style = SubtitleStyle()
        assert style.font_name == "Arial"
        assert style.font_size == 24
        assert style.primary_color == "&H00FFFFFF"

    def test_new_fields_have_defaults(self):
        """Yeni alanlar varsayılan değere sahip olmalı."""
        style = SubtitleStyle()
        assert style.font_weight == 700  # Varsayılan kalınlık
        assert style.background_color == "&H00000000"  # Şeffaf
        assert style.gradient_colors == ["&H00FFFFFF"]

    def test_existing_presets_unchanged(self):
        """Mevcut presetler değişmemeli."""
        style = StyleManager.get_preset("HORMOZI")
        assert style.name == "Hormozi Style"
        assert style.font_size == 120
        assert style.animation_type == "pop"

    def test_unknown_preset_returns_default(self):
        """Bilinmeyen preset varsayılan dönmeli."""
        style = StyleManager.get_preset("BILINMEYEN")
        assert isinstance(style, SubtitleStyle)
        assert style.name == "Custom"

class TestStyleManager:
    """StyleManager için unit testler."""

    def test_list_presets_returns_all(self):
        """Tüm presetler listelenmeli."""
        presets = StyleManager.list_presets()
        assert "HORMOZI" in presets
        assert "MRBEAST" in presets
        assert "MINIMALIST" in presets

    def test_case_insensitive_preset_lookup(self):
        """Preset araması büyük-küçük harf duyarsız olmalı."""
        assert StyleManager.get_preset("hormozi") == StyleManager.get_preset("HORMOZI")
        assert StyleManager.get_preset("Hormozi") == StyleManager.get_preset("HORMOZI")
```

### 3.2 Entegrasyon Testler

```python
# backend/tests/test_subtitle_renderer.py (GENİŞLETİLECEK)
import pytest
import tempfile
import json
from backend.services.subtitle_renderer import SubtitleRenderer
from backend.services.subtitle_styles import StyleManager

class TestSubtitleRenderer:
    """SubtitleRenderer için entegrasyon testleri."""

    @pytest.fixture
    def sample_whisperx_data(self):
        """Örnek WhisperX verisi."""
        return [
            {
                "words": [
                    {"word": "Merhaba", "start": 0.0, "end": 0.5},
                    {"word": "dünya", "start": 0.6, "end": 1.0}
                ]
            }
        ]

    def test_generate_ass_with_default_style(self, sample_whisperx_data):
        """Varsayılan stil ile ASS oluşturulabilmeli."""
        style = StyleManager.get_preset("HORMOZI")
        renderer = SubtitleRenderer(style)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_whisperx_data, f)
            json_path = f.name

        with tempfile.NamedTemporaryFile(suffix='.ass', delete=False) as f:
            output_path = f.name

        try:
            result = renderer.generate_ass_file(json_path, output_path)
            assert result == output_path
            with open(output_path, 'r') as f:
                content = f.read()
                assert "ScriptType: v4.00+" in content
                assert "Style: Main," in content
        finally:
            import os
            os.unlink(json_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_all_preset_styles_generate_valid_ass(self, sample_whisperx_data):
        """Tüm presetler geçerli ASS üretmeli."""
        for preset_name in StyleManager.list_presets():
            style = StyleManager.get_preset(preset_name)
            renderer = SubtitleRenderer(style)
            # ... (yukarıdaki test gibi)

    def test_new_style_with_all_fields(self, sample_whisperx_data):
        """Yeni alanları içeren stil ile ASS oluşturulabilmeli."""
        # Bu test implementasyondan sonra eklenecek
        pass
```

### 3.3 Regresyon Testleri

| Test Senaryosu                           | Beklenen Sonuç                     | Öncelik   |
| ---------------------------------------- | ---------------------------------- | --------- |
| Mevcut HORMOZI stili ile video işleme    | Başarılı, altyazı görünür          | 🔴 Yüksek |
| Mevcut MRBEAST stili ile video işleme    | Başarılı, altyazı görünür          | 🔴 Yüksek |
| Mevcut MINIMALIST stili ile video işleme | Başarılı, altyazı görünür          | 🔴 Yüksek |
| Bilinmeyen stil adı gönderme             | Varsayılan Custom stili kullanılır | 🟡 Orta   |
| API'ye stil olmadan istek atma           | Varsayılan HORMOZI kullanılır      | 🟡 Orta   |
| FFmpeg hatası durumunda                  | Uygun hata mesajı döner            | 🟡 Orta   |

### 3.4 Manual Test Checklist

- [ ] **HORMOZI stili**: TikTok video üretimi (1080x1920)
- [ ] **MRBEAST stili**: YouTube Shorts üretimi (1080x1920)
- [ ] **MINIMALIST stili**: Podcast klipi (1080x1080)
- [ ] **Yeni TIKTOK stili**: Varsayılan gradient görünüyor mu?
- [ ] **Yeni CORPORATE stili**: Arka plan şeffaf mı?
- [ ] **Bilinmeyen stil**: Custom'a düşüyor mu?
- [ ] **FFmpeg hatası**: Loglarda görünüyor mu?

---

## 4. Implementasyon Öncesi Kontrol Listesi

### 4.1 Güvenlik Kontrolleri

- [ ] **R-001:** Pydantic modeli tüm yeni alanlar için varsayılan değer içeriyor
- [ ] **R-002:** ASS header formatı değişmiyor, sadece koşullu alanlar ekleniyor
- [ ] **R-003:** Font fallback listesi tanımlanmış
- [ ] **R-004:** Animasyon fonksiyonu bilinmeyen tipler için boş string döndürüyor
- [ ] **R-005:** Renk formatı validator'ı eklenecek (regex: `^&H[0-9A-F]{8}$`)
- [ ] **R-006:** ASS standardı dışına çıkılmıyor

### 4.2 Performans Kontrolleri

- [ ] Maksimum font boyutu: 200px (sınırlandırma)
- [ ] Maksimum animasyon süresi: 2.0s
- [ ] Maksimum gradient renk sayısı: 3
- [ ] ASS dosyası boyutu kontrolü (log)

### 4.3 Kod Kalitesi Kontrolleri

- [ ] Tüm yeni metodlar için docstring yazıldı
- [ ] Type hints eklendi
- [ ] Loguru logger kullanıldı
- [ ] Error handling mevcut

---

## 5. Risk Azaltma Önlemleri Özeti

| Önlem                  | Uygulama Yeri                             | Sorumlu |
| ---------------------- | ----------------------------------------- | ------- |
| Geriye dönük uyumluluk | `subtitle_styles.py`                      | Code    |
| ASS format koruma      | `subtitle_renderer.py`                    | Code    |
| Unit testler           | `backend/tests/test_subtitle_styles.py`   | Code    |
| Entegrasyon testleri   | `backend/tests/test_subtitle_renderer.py` | Code    |
| Renk validasyonu       | `schemas.py`                              | Code    |
| Loglama                | Tüm dosyalar                              | Code    |

---

## 6. Sonuç ve Öneriler

### Risk Değerlendirmesi: 🟢 DÜŞÜK

Tüm riskler için önlemler belirlenmiş ve implementasyon güvenli bir şekilde yapılabilir. Önerilen yaklaşım:

1. **Aşamalı Implementasyon**: Önce `subtitle_styles.py`'ye yeni alanlar ve presetler ekle
2. **Test Odaklı**: Her değişiklikten önce unit testler çalıştır
3. **Geriye Dönük Uyumluluk**: Varsayılan değerlerle mevcut davranışı koru
4. **A/B Test**: Yeni stilleri küçük bir kullanıcı grubuyla test et

_Bu analiz, plans/subtitle_expansion_guide.md ile birlikte kullanılmalıdır._
