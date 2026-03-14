# Subtitle Style / Renderer Audit Report

Tarih: 14 Mart 2026

İnceleme kapsamı:
- `backend/services/subtitle_styles.py`
- `backend/services/subtitle_renderer.py`
- İlgili entegrasyon yüzeyleri: `/api/styles`, workflow çağrı zinciri, `frontend/src/config/subtitleStyles.ts`, `frontend/src/components/SubtitlePreview.tsx`, `frontend/src/components/VideoOverlay.tsx`

Bu rapor production odaklı kod denetimi metodolojisiyle hazırlanmıştır. Bulgular repo-gerçeğine, yerel kod okumaya ve hedefli test/komut çıktısına dayanır. Bu turda repo-tracked kod değiştirilmemiş, yalnızca analiz dokümantasyonu eklenmiştir.

## 1. Executive Summary

İki ana dosya işlevsel olarak kritik bir altyazı pipeline'ının merkezinde duruyor, ancak mevcut tasarım özellikle üç noktada operasyonel risk üretiyor:

1. `SubtitleRenderer` ve `StyleManager` üzerindeki `@logger.catch` dekoratörleri exception'ları bastırabildiği için hata zinciri sessizce kırılabiliyor.
2. Stil sözleşmesi gevşek: backend bilinmeyen `style_name` değerlerini sessiz fallback ile kabul ediyor, frontend ise aynı alan için birden fazla source of truth tutuyor.
3. Public `SubtitleStyle` modeli renderer ve UI parity katmanının gerçekte desteklediğinden daha geniş; bu da bakım maliyetini ve davranış drift'ini yükseltiyor.

Genel sonuç:
- Mimari kalite: Orta
- Operasyonel güvenilirlik: Orta-alt
- Test güveni: Orta-alt
- Güvenlik duruşu: Orta
- Bakım sürdürülebilirliği: Orta-alt

En kritik üç aksiyon:
- `@logger.catch` suppression davranışını kaldırmak veya `reraise=True` ile sınırlandırmak
- `style_name` sözleşmesini kapatmak ve `CUSTOM` semantiğini açıklaştırmak
- ASS metni ve FFmpeg filter path değerlerini escape etmek

## 2. Kanıt Tabanı ve Doğrulama

### 2.1 Okunan Kaynaklar

- `README.md`
- `.agents/skills/godtier-shorts/references/subtitle-style-parity.md`
- `.agents/skills/godtier-shorts/references/api-contracts.md`
- `.agents/skills/godtier-shorts/references/commands.md`
- `docs/architecture/subtitle-renderer.md`
- `docs/architecture/subtitle-styles.md`
- `backend/core/workflow_runtime.py`
- `backend/core/workflows_manual.py`
- `backend/core/workflows_batch.py`
- `backend/core/workflows_pipeline.py`
- `backend/core/workflows_reburn.py`
- `backend/core/media_ops.py`
- `backend/models/schemas.py`
- `frontend/src/config/subtitleStyles.ts`
- `frontend/src/components/subtitlePreview/helpers.ts`
- `frontend/src/components/SubtitlePreview.tsx`
- `frontend/src/components/VideoOverlay.tsx`

### 2.2 Çalıştırılan Kontroller

| Komut | Sonuç |
|---|---|
| `pytest backend/tests/test_subtitle_styles.py -q` | `20 passed` |
| `cd frontend && npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx --reporter=dot` | `2 test file, 15 test passed` |
| Loguru suppression doğrulaması | `@logger.catch` altında exception'ın bastırıldığı gözlendi |

### 2.3 Güven Seviyesi

- `Kanıtlandı`: Doğrudan kod, test veya yerel deneyle doğrulandı.
- `Çıkarım`: Koddan güçlü biçimde türetildi, ancak tam çalışma zamanı senaryosu ayrıca yürütülmedi.

## 3. Mimari ve Tasarım Analizi

### 3.1 `subtitle_styles.py`

Pozitif yönler:
- `SubtitleStyle` için Pydantic model kullanılması veri doğrulama ve default yönetimi açısından doğru bir temel.
- `SubtitleCategory` eklenmesi preset gruplama ihtiyacını destekliyor.
- `StyleManager` preset kataloğunu tek yerde tutarak temel keşif maliyetini düşürüyor.

Sorunlar:
- `SubtitleStyle` modeli public API olarak çok geniş; renderer ve frontend parity katmanı model alanlarının önemli bölümünü tüketmiyor.
- `StyleManager` gerçek bir manager değil; immutable registry gibi davranması gerekirken mutable model örnekleri döndürüyor.
- `create_custom_style()` mevcut API/route zincirine bağlı değil; public factory var ama çağrılmıyor.

SOLID değerlendirmesi:

| Prensip | Değerlendirme | Not |
|---|---|---|
| SRP | Zayıf-Orta | Model hem desteklenen hem de desteklenmeyen stil alanlarını taşıyor |
| OCP | Zayıf | Yeni stil alanı eklemek backend renderer, frontend preview ve overlay kodunu elle güncellemeyi gerektiriyor |
| LSP | Nötr | Gerçek bir kalıtım/polimorfizm yüzeyi yok |
| ISP | Zayıf | Tüketiciler ihtiyaç duymadıkları çok sayıda alanı almak zorunda |
| DIP | Zayıf | Üst seviye iş akışları doğrudan `StyleManager` concrete API'sine bağlı |

### 3.2 `subtitle_renderer.py`

Pozitif yönler:
- Transcript -> ASS -> FFmpeg burn hattı tek dosyada bulunuyor; operasyonel akış izlenebilir.
- İşlemlerin çoğu doğrusal (`O(n)`) kelime akışı üzerinden ilerliyor.
- `cancel_event` desteği operasyonel iptal senaryosunu kısmen ele alıyor.

Sorunlar:
- Sınıf çok fazla sorumluluk taşıyor: transcript normalization, timing heuristics, ASS serialization, FFmpeg orchestration, cancellation polling, logging.
- Stil soyutlaması ile render implementasyonu arasında kapalı bir mapping katmanı yok.
- `StyleManager` import edilmesine rağmen dosya içinde kullanılmıyor; bu da gereksiz bağımlılık ve zayıf modül sınırı işareti.

SOLID değerlendirmesi:

| Prensip | Değerlendirme | Not |
|---|---|---|
| SRP | Zayıf | Tek sınıf birden fazla değişim sebebi taşıyor |
| OCP | Zayıf | Yeni animasyon veya stil alanı için doğrudan method gövdeleri açılıyor |
| LSP | Nötr | Kalıtım yüzeyi yok |
| ISP | Zayıf | `SubtitleRenderer` kullanan akışlar yalnızca küçük bir kısmına ihtiyaç duysa da tam concrete sınıfı bağlıyor |
| DIP | Zayıf | FFmpeg, loguru, filesystem ve style concrete tipine doğrudan bağımlılık var |

## 4. Bağımlılık ve Entegrasyon Analizi

### 4.1 Backend Veri Akışı

1. API veya workflow katmanı `style_name` alıyor.
2. `backend/core/workflow_runtime.py` içindeki `create_subtitle_renderer()` `StyleManager.get_preset(style_name)` çağırıyor.
3. `SubtitleRenderer.generate_ass_file()` transcript JSON'dan ASS üretiyor.
4. `backend/core/media_ops.py` üzerinden `burn_subtitles_to_video()` çağrılıyor.
5. Metadata JSON'a `style_name` ayrı yazılıyor, fakat gerçekte kullanılan stilin resolved hali garanti edilmiyor.

### 4.2 UI Entegrasyonu

- Backend preset anahtarları `frontend/src/config/subtitleStyles.ts` içinde elle kopyalanıyor.
- `STYLE_LABELS`, `SUBTITLE_STYLES` ve `SUBTITLE_INLINE_STYLES` üç ayrı yapı olarak yaşıyor.
- Preview tarafında `frontend/src/components/subtitlePreview/helpers.ts` kendi `STYLE_LABELS` kopyasını tutuyor.
- `VideoOverlay.tsx` backend preset davranışından bağımsız Tailwind sınıflarıyla anlık overlay çiziyor.

### 4.3 Sözleşme Netliği

| Yüzey | Durum | Risk |
|---|---|---|
| `/api/styles` | Sadece string listesi | Stil metadata'sı UI'ya taşınmıyor |
| `style_name` request alanı | Serbest `str` | Bilinmeyen değerler sessiz fallback alıyor |
| `CUSTOM` | UI'da var, backend'de gerçek custom payload yok | Kullanıcı beklentisi ile backend gerçekliği ayrışıyor |
| Preset object yaşam döngüsü | Paylaşımlı instance | Gelecekte mutation sızıntısı riski |

## 5. Hata, Bug ve Risk Bulguları

### F1. Critical — Sessiz exception suppression üretim akışını yanlış başarıya döndürebiliyor

- Ciddiyet: `critical`
- Durum: `kanıtlandı`
- Konum:
  - `backend/services/subtitle_styles.py:349-358`
  - `backend/services/subtitle_renderer.py:276-342`
  - `backend/services/subtitle_renderer.py:344-397`
  - `backend/core/workflows_manual.py:69-74`
  - `backend/core/workflows_batch.py:64-66`
  - `backend/core/workflows_pipeline.py:180-216`
  - `backend/core/workflows_reburn.py:42-55`
- Sorun:
  - `@logger.catch` dekoratörü `StyleManager.get_preset()`, `generate_ass_file()` ve `burn_subtitles_to_video()` üzerinde kullanılıyor.
  - Loguru varsayılan davranışta exception'ı loglayıp yeniden fırlatmıyor.
- Kök neden:
  - Hata yakalama politikası domain sınırında değil, çekirdek servis method'larında tanımlanmış.
  - Workflow katmanı bu method'ların başarısız olursa exception fırlatacağını varsayıyor.
- Potansiyel etkiler:
  - ASS üretimi başarısız olup workflow'un altyazı eklenmiş gibi devam etmesi
  - Metadata içinde `style_name` varken gerçek çıktının altyazısız olması
  - Reburn akışında geçici dosya veya eksik çıktı sorunlarının yanlış başarıya dönmesi
- Yeniden üretilebilirlik:
  - Yerel Loguru denemesinde `@logger.catch` altında exception `None` dönüşüyle bastırıldı.
- Önerilen çözüm:
  - Bu method'larda ya dekoratörü kaldırın ya da `reraise=True` kullanın.
  - Hata eşleme ve kullanıcıya uygun mesaj üretimini orchestrator/API sınırına taşıyın.
- Alternatif çözüm:
  - `generate_ass_file()` sonrasında dosya varlığı ve boyut kontrolü ile invariant doğrulaması ekleyin.

```python
# backend/services/subtitle_renderer.py
from pathlib import Path

@logger.catch(reraise=True)
def generate_ass_file(
    self,
    transcript_json_path: str,
    output_ass_path: str = "dynamic_subs.ass",
    max_words_per_screen: int = 4,
) -> str:
    ...
    Path(output_ass_path).write_text(ass_content, encoding="utf-8")
    if not Path(output_ass_path).exists():
        raise RuntimeError(f"ASS output was not created: {output_ass_path}")
    return output_ass_path

@logger.catch(reraise=True)
def burn_subtitles_to_video(
    self,
    input_video: str,
    ass_file: str,
    output_video: str,
    cancel_event: threading.Event | None = None,
) -> None:
    ...
```

### F2. High — `style_name` sözleşmesi açık değil; bilinmeyen stil sessiz fallback alıyor

- Ciddiyet: `high`
- Durum: `kanıtlandı`
- Konum:
  - `backend/models/schemas.py:24-62`
  - `backend/models/schemas.py:76-102`
  - `backend/api/routes/jobs.py:103-108`
  - `backend/services/subtitle_styles.py:351-358`
- Sorun:
  - API modellerinde `style_name` yalnızca `str`.
  - `StyleManager.get_preset()` bilinmeyen değerde varsayılan `SubtitleStyle()` döndürüyor.
  - `/api/styles` endpoint'i `CUSTOM` döndürüyor, ancak bu anahtar için backend'de ayrı bir custom payload sözleşmesi yok.
- Kök neden:
  - Stil seçimi domain sözleşmesi olarak değil, gevşek string alanı olarak modellenmiş.
  - UI seçilebilir seçenekler ile backend kabul edilen payload arasında tip kapaması yapılmamış.
- Potansiyel etkiler:
  - Yazım hatalı stiller sessizce `Custom` render alır
  - Operatör yanlış preset kullandığını anlayamaz
  - `CUSTOM` seçeneği kullanıcıya olmayan bir capability varmış gibi görünür
- Yeniden üretilebilirlik:
  - `test_unknown_preset_returns_default` bu davranışı mevcut ve beklenen hale getiriyor.
- Önerilen çözüm:
  - `style_name` validator ekleyin.
  - `CUSTOM` için ayrı `custom_style` payload'ı tanımlayın veya `CUSTOM` seçeneğini public API'den kaldırın.
  - `StyleManager.get_preset()` deep copy döndürsün.
- Alternatif çözüm:
  - Sessiz fallback yerine `resolved_style_name` ve `fallback_reason` metadata'sı döndürün.

```python
# backend/models/schemas.py
from backend.services.subtitle_styles import StyleManager

class JobRequest(BaseModel):
    youtube_url: str
    style_name: str = "HORMOZI"
    custom_style: dict[str, Any] | None = None

    @field_validator("style_name")
    @classmethod
    def validate_style_name(cls, value: str) -> str:
        key = value.upper()
        if key != "CUSTOM" and key not in StyleManager.list_presets():
            raise ValueError(f"unknown style_name: {value}")
        return key

# backend/services/subtitle_styles.py
@classmethod
def get_preset(cls, preset_name: str) -> SubtitleStyle:
    key = preset_name.upper()
    if key in cls._PRESETS:
        return cls._PRESETS[key].model_copy(deep=True)
    raise ValueError(f"Unknown subtitle preset: {preset_name}")
```

### F3. High — ASS text ve FFmpeg filter path escape edilmiyor

- Ciddiyet: `high`
- Durum: `çıkarım`
- Konum:
  - `backend/services/subtitle_renderer.py:316-333`
  - `backend/services/subtitle_renderer.py:355-370`
- Sorun:
  - Transcript token'ları doğrudan ASS `Dialogue` text içine yazılıyor.
  - `ass='{ass_abs}'` filter argümanı FFmpeg filtergraph kurallarına göre escape edilmiyor.
- Kök neden:
  - Shell injection düşünülmüş olabilir, ancak parser/filter seviyesindeki escape ihtiyacı ele alınmamış.
- Potansiyel etkiler:
  - `{`, `}`, `\`, newline veya tek tırnak içeren metinlerde render bozulması
  - ASS override tag enjeksiyonu
  - Dosya yolu içinde özel karakter varsa FFmpeg filter parse hatası
- Güvenlik etkisi:
  - Shell injection yok, çünkü `subprocess.Popen()` liste ile çağrılıyor.
  - Parser seviyesinde injection/kırılma riski var.
- Önerilen çözüm:
  - `_escape_ass_text()` ve `_escape_filter_path()` yardımcılarını ekleyin.
- Alternatif çözüm:
  - Temp dosya isimlerini sınırlı karakter setine zorlayın ve transcript girişinde kontrol karakterlerini reddedin.

```python
def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )

def _escape_filter_path(path: str) -> str:
    return (
        path.replace("\\", r"\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
    )

word_text = _escape_ass_text(w["word"].strip())
ass_filter = f"ass='{_escape_filter_path(ass_abs)}'"
```

### F4. High — Public `SubtitleStyle` API'sinin büyük kısmı fiilen uygulanmıyor

- Ciddiyet: `high`
- Durum: `kanıtlandı`
- Konum:
  - `backend/services/subtitle_styles.py:54-78`
  - `backend/services/subtitle_styles.py:148-345`
  - `backend/services/subtitle_renderer.py:66-159`
  - `frontend/src/components/subtitlePreview/helpers.ts:63-97`
- Sorun:
  - `gradient_colors`, `gradient_direction`, `position_y`, `border_radius`, `animation_duration`, `animation_easing`, `high_contrast`, `large_text` gibi alanlar modelde ve presetlerde var.
  - Renderer veya frontend parity katmanı bunların çoğunu hiç kullanmıyor.
- Kök neden:
  - Domain model capability-driven tasarlanmamış.
  - "İleride gerekebilir" alanları public modele alınmış, ama runtime contract'a dönüştürülmemiş.
- Potansiyel etkiler:
  - Preset açıklamaları gerçeği yansıtmaz
  - Stil ekleme maliyeti artar
  - Bakım yapan kişi desteklenen/desteklenmeyen alan ayrımını anlayamaz
- Mimari etkisi:
  - SRP ve OCP doğrudan zedeleniyor
  - Frontend/backend parity sürekli manuel eşleme gerektiriyor
- Önerilen çözüm:
  - `SubtitleStyle` -> `ResolvedRenderStyle` dönüşüm katmanı ekleyin.
  - Sadece gerçekten desteklenen alanları render spec'e indirin.
- Alternatif çözüm:
  - Desteklenmeyen alanları modelden çıkarın veya `experimental` olarak işaretleyin.

```python
class ResolvedRenderStyle(BaseModel):
    font_name: str
    font_size: int
    primary_color: str
    highlight_color: str
    outline_color: str
    outline_width: float
    blur: float
    margin_v: int
    animation_ms: int
    bold: bool
    italic: bool
    underline: bool

def to_render_style(style: SubtitleStyle) -> ResolvedRenderStyle:
    return ResolvedRenderStyle(
        font_name=style.font_name,
        font_size=style.font_size,
        primary_color=style.primary_color,
        highlight_color=style.highlight_color,
        outline_color=style.outline_color,
        outline_width=style.outline_width,
        blur=style.blur,
        margin_v=int((1.0 - style.position_y) * 1920),
        animation_ms=max(50, int(style.animation_duration * 1000)),
        bold=style.font_weight >= 600,
        italic=style.italic,
        underline=style.underline,
    )
```

### F5. High — Timing, chunking ve animasyon süreleri hard-coded; stil verisi yok sayılıyor

- Ciddiyet: `high`
- Durum: `kanıtlandı` ve `çıkarım`
- Konum:
  - `backend/services/subtitle_renderer.py:105-159`
  - `backend/services/subtitle_renderer.py:161-199`
  - `backend/services/subtitle_renderer.py:226-252`
  - `backend/services/subtitle_renderer.py:297-333`
- Sorun:
  - `animation_duration` alanı presetlerde var, ama hesaplama sabit `100/150ms` kullanıyor.
  - `segment.text` ile `segment.words` uyuşmazsa sentetik eşit süreli kelime zamanları üretiliyor.
  - `gap < 0.4s` olduğunda chunk sonu sonraki kelimenin başlangıcına uzatılıyor.
- Kök neden:
  - Renderer heuristics-first yazılmış, style-first veya transcript-truth-first yazılmamış.
- Potansiyel etkiler:
  - Karaoke vurgusu gerçek konuşma ritminden kayar
  - Çok kısa kelimelerde `150ms` zorlaması görsel patlamayı abartır
  - Çok dilli, emojili veya noktalama yoğun transcript'lerde chunk sınırları yanlış oluşur
- Performans analizi:
  - `_smart_chunking()`, `_resolve_overlaps()`, `_flatten_render_words()` yaklaşık `O(n)`.
  - `dialogue_text += ...` string birleştirme uzun transcript'lerde ekstra kopya maliyeti getirir.
  - Asıl dominant maliyet FFmpeg encode olsa da render-prep heuristics optimize edilebilir.
- Önerilen çözüm:
  - Animasyon süresini `style.animation_duration` üzerinden hesaplayın.
  - `words` zamanları varsa mümkün olduğunca koruyun.
  - `dialogue_text` için liste topla + `"".join(...)` kullanın.
- Alternatif çözüm:
  - Text/words mismatch durumda fail-fast davranıp transcript veri kalitesini yukarı akışta zorlayın.

```python
animation_ms = max(50, int(self.style.animation_duration * 1000))
word_ms = max(1, int((word_end - word_start) * 1000))
active_ms = min(animation_ms, word_ms)

parts: list[str] = []
for word in chunk:
    escaped = _escape_ass_text(word["word"].strip())
    tags = self._calculate_animation_tags(...)
    parts.append(f"{reset_tag}{tags}{escaped} ")
dialogue_text = "".join(parts).strip()
```

### F6. Medium — Frontend parity zinciri parçalı; preview ve live overlay gerçeği yansıtmıyor

- Ciddiyet: `medium`
- Durum: `kanıtlandı`
- Konum:
  - `frontend/src/config/subtitleStyles.ts:23-281`
  - `frontend/src/components/subtitlePreview/helpers.ts:8-97`
  - `frontend/src/components/SubtitlePreview.tsx:10-22`
  - `frontend/src/components/VideoOverlay.tsx:113-117`
- Sorun:
  - `STYLE_LABELS` iki yerde tanımlı.
  - `VideoOverlay` Tailwind sınıflarıyla backend preset davranışını aşan stiller uyguluyor.
  - Örnek: `HORMOZI` overlay italic, `MRBEAST` overlay underline alıyor; backend preset bunları tanımlamıyor.
  - `HIGHCARE` etiketi preview helper'da ASCII'ye düşürülmüş (`Yuksek Kontrast`), config'de aksanlı (`Yüksek Kontrast`).
- Kök neden:
  - Stil kaynağı tek registry üzerinden üretilmiyor.
  - Preview ve overlay gerçek burn-in'den bağımsız tasarlanmış.
- Potansiyel etkiler:
  - Kullanıcı önizlemede gördüğünü çıktı olarak alamaz
  - UI testleri yanlış güven hissi üretir
  - Stil güncellemelerinde drift sürekli tekrarlanır
- Önerilen çözüm:
  - Tek `STYLE_REGISTRY` tanımlayın ve `STYLE_OPTIONS`, `STYLE_LABELS`, inline preview map ve overlay class'larını buradan türetin.
- Alternatif çözüm:
  - Backend `/api/styles` yanıtına stil metadata'sı ekleyin ve frontend'i ince istemciye çevirin.

```ts
export const STYLE_REGISTRY = {
  HORMOZI: {
    label: 'Hormozi',
    overlayClassName: 'text-4xl text-white font-black',
    inline: {
      primaryColor: '#ffffff',
      highlightColor: '#ffff00',
      outlineColor: '#000000',
      outlineWidth: 10,
      fontSize: '2rem',
      fontWeight: 900,
      fontFamily: '"Montserrat", "Outfit", sans-serif',
      backgroundColor: null,
    },
  },
  MRBEAST: {
    label: 'MrBeast',
    overlayClassName: 'text-3xl text-white font-black',
    inline: {
      primaryColor: '#ffffff',
      highlightColor: '#00ff00',
      outlineColor: '#000000',
      outlineWidth: 12,
      fontSize: '2.2rem',
      fontWeight: 900,
      fontFamily: '"Comic Sans MS", "Outfit", cursive',
      backgroundColor: null,
    },
  },
} as const;

export const STYLE_OPTIONS = Object.keys(STYLE_REGISTRY) as Array<keyof typeof STYLE_REGISTRY>;
export const STYLE_LABELS = Object.fromEntries(
  STYLE_OPTIONS.map((name) => [name, STYLE_REGISTRY[name].label]),
) as Record<(typeof STYLE_OPTIONS)[number], string>;
```

### F7. Medium — Test coverage kritik renderer davranışlarını korumuyor

- Ciddiyet: `medium`
- Durum: `kanıtlandı`
- Konum:
  - `backend/tests/test_subtitle_styles.py`
  - `frontend/src/test/config/subtitleStyles.test.ts`
  - `frontend/src/test/components/SubtitlePreview.test.tsx`
  - `frontend/src/test/components/subtitlePreview.helpers.test.ts`
- Sorun:
  - Renderer için doğrudan unit test dosyası yok.
  - ASS escaping, cancellation, NVENC -> CPU fallback, timing invariants, unknown style rejection, UI overlay parity test dışı.
- Kök neden:
  - Testler preset katalog doğrulamasına odaklı; render mekanizması smoke veya snapshot ile korunmuyor.
- Potansiyel etkiler:
  - En pahalı üretim yolu olan burn pipeline regressions fark edilmeden merge edilir
  - CI yeşil kalsa da gerçek medya çıktısı bozulabilir
- Önerilen çözüm:
  - `backend/tests/test_subtitle_renderer.py` ekleyin.
  - En azından header üretimi, ASS escaping, cancellation ve style duration mapping testlensin.
- Alternatif çözüm:
  - Ağır medya smoke testlerini nightly pipeline'a taşıyın.

```python
def test_generate_ass_file_escapes_control_chars(tmp_path: Path) -> None:
    transcript = [{
        "text": r"{boom} slash\\word",
        "start": 0.0,
        "end": 1.0,
        "words": [
            {"word": r"{boom}", "start": 0.0, "end": 0.5},
            {"word": r"slash\\word", "start": 0.5, "end": 1.0},
        ],
    }]
    source = tmp_path / "transcript.json"
    source.write_text(json.dumps(transcript), encoding="utf-8")

    renderer = SubtitleRenderer(StyleManager.get_preset("HORMOZI"))
    output = renderer.generate_ass_file(str(source), str(tmp_path / "out.ass"))

    text = Path(output).read_text(encoding="utf-8")
    assert r"\{" in text
    assert r"\\word" in text
```

### F8. Low — Unicode, localization ve metin normalizasyonu agresif ve tutarsız

- Ciddiyet: `low`
- Durum: `kanıtlandı` ve `çıkarım`
- Konum:
  - `backend/services/subtitle_renderer.py:221-274`
  - `frontend/src/components/subtitlePreview/helpers.ts:8-25`
  - `frontend/src/components/SubtitlePreview.tsx:32-49`
- Sorun:
  - `_canonicalize_text()` alphanumeric dışı karakterleri boşluğa çeviriyor; emoji, apostrof, bazı dillerdeki işaretler ve bidi işaretleri kayboluyor.
  - UI preview etiketleri ve başlıkları ASCII'ye düşürülmüş.
- Kök neden:
  - Transcript eşleştirme kolaylaştırmak için fazla kaba normalization yapılmış.
  - UI kopyalarında tek localization kaynağı yok.
- Potansiyel etkiler:
  - Çok dilli transcript'te text/words mismatch oranı artabilir
  - Türkçe ve diğer dillerde kullanıcı yüzeyi kalitesi düşer
- Önerilen çözüm:
  - Unicode-aware normalization kullanın.
  - UI label'larını tek yerden üretin.
- Alternatif çözüm:
  - Preview helper katmanında ASCII fallback'i tamamen kaldırın.

```python
import unicodedata

@staticmethod
def _canonicalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text.casefold())
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in normalized)
    return " ".join(cleaned.split())
```

### F9. Low — Import-time logging side effect ve dokümantasyon drift'i var

- Ciddiyet: `low`
- Durum: `kanıtlandı`
- Konum:
  - `backend/services/subtitle_renderer.py:17-22`
  - `docs/architecture/subtitle-renderer.md:20-33`
- Sorun:
  - `logger.add()` import anında çalışıyor.
  - Dokümanda CUDA `hwupload_cuda, scale_cuda` akışından söz ediliyor, mevcut kod yalnızca `-vf ass=...` kullanıyor.
- Kök neden:
  - Operasyonel logging ve runtime setup modül import'una bağlanmış.
  - Dokümantasyon güncellemesi kod refactor'ı ile birlikte yürütülmemiş.
- Potansiyel etkiler:
  - Test worker/reload senaryolarında duplicate sink riski
  - Operatör ve geliştirici yanlış mimari beklentiye girer
- Önerilen çözüm:
  - Logger sink kurulumunu uygulama startup'ına taşıyın.
  - Subtitle renderer dokümantasyonunu gerçek komut zinciriyle hizalayın.
- Alternatif çözüm:
  - `if not _renderer_logger_initialized` benzeri guard ekleyin.

```python
_RENDERER_LOGGER_READY = False

def configure_renderer_logging() -> None:
    global _RENDERER_LOGGER_READY
    if _RENDERER_LOGGER_READY:
        return
    logger.add(
        str(LOGS_DIR / "renderer_{time:YYYY-MM-DD}.log"),
        rotation="50 MB",
        retention="10 days",
        level="DEBUG",
    )
    _RENDERER_LOGGER_READY = True
```

## 6. Performans Analizi

### 6.1 Karmaşıklık

| Fonksiyon | Yaklaşık karmaşıklık | Not |
|---|---:|---|
| `_smart_chunking()` | `O(n)` | Kelime başına sabit kontrol |
| `_resolve_overlaps()` | `O(n)` | Önceki kelime ile karşılaştırmalı tek geçiş |
| `_flatten_render_words()` | `O(n)` | Segment ve kelime düzeyi tek geçiş, ancak canonicalization maliyeti ekli |
| `generate_ass_file()` | `O(n)` | Kelime sayısına doğrusal; string concatenation ek kopya yaratıyor |
| `burn_subtitles_to_video()` | Dış süreç maliyeti baskın | CPU/GPU encode gerçek darboğaz |

### 6.2 Temel Darboğazlar

- Gerçek baskın maliyet FFmpeg encode.
- NVENC başarısızlığında tam ikinci encode çalıştırılıyor; fallback pahalı ama makul.
- `dialogue_text += ...` kullanımı uzun transcript'lerde gereksiz string kopyası üretir.
- Text/words mismatch olduğunda sentetik kelime üretimi kalite sorunuyla beraber ek hesaplama getirir.

### 6.3 Caching ve Bellek

- Stil cache'i yok; buna ihtiyaç da düşük.
- FFmpeg stdout/stderr pipe'ları süreç bitene kadar bellekte tutuluyor. Büyük hata çıktılarında büyüyebilir ama `-loglevel error` ile sınırlı.
- Object pooling ihtiyacı görünmüyor.

## 7. Güvenlik Analizi

### 7.1 Güçlü Noktalar

- Shell command'leri liste olarak çağrılıyor; klasik shell injection yüzeyi düşük.
- Renk formatı regex ile sınırlandırılmış.
- Font size clamp mekanizması kaynak tüketimini kısmen sınırlandırıyor.

### 7.2 Zayıf Noktalar

- ASS parser enjeksiyonu ve filter path escape eksikliği
- `style_name` doğrulanmadığı için kullanıcı girdisi domain'de sessiz şekilde farklı anlam kazanabiliyor
- Transcript içeriği loglarda tam yazılmıyor; bu iyi. Ancak path ve job mesajları gelecekte PII taşıyabilir
- Resource exhaustion açısından transcript boyutu veya kelime sayısı için renderer seviyesinde ek hard limit yok

### 7.3 Güvenlik Sonucu

Shell seviyesinde kritik açık görünmüyor. Parser düzeyinde kırılma ve sözleşme gevşekliği orta risk yaratıyor. Bu alanlar CI öncesi kapatılmalı.

## 8. Concurrency ve Thread Safety Analizi

### 8.1 Gözlemler

- `SubtitleRenderer` mutable `self.style` tutuyor; bu tek başına sorun değil, fakat `StyleManager` paylaşımlı preset döndürdüğü için ileride thread-safe olmayan mutation riski var.
- `_run_command_with_cancel()` polling tabanlı; her 500ms'de `cancel_event` kontrol ediyor.
- GIL etkisi düşük; ağır iş FFmpeg dış sürecinde gerçekleşiyor.
- Açık deadlock paterni görülmedi.

### 8.2 Riskler

- Preset instance paylaşımı eşzamanlı worker'larda ileride mutation sızıntısına açık.
- `proc.kill()` yalnızca ilgili süreci öldürüyor; alt süreç zinciri oluşursa process-group yönetimi daha güvenli olurdu. Bu risk burada düşük ama not edilmeli.

## 9. Test Coverage ve Kalite Metrikleri

Mevcut durum:
- Backend: preset katalog ve validation odaklı testler var
- Frontend: config ve preview smoke testleri var
- Eksik: renderer unit/integration tests, overlay parity tests, failure-path tests

CI/CD önerileri:
- PR CI:
  - `pytest backend/tests/test_subtitle_styles.py -q`
  - yeni `pytest backend/tests/test_subtitle_renderer.py -q`
  - `cd frontend && npm run test -- src/test/config/subtitleStyles.test.ts src/test/components/SubtitlePreview.test.tsx src/test/components/subtitlePreview.helpers.test.ts --reporter=dot`
- Nightly veya ops smoke:
  - `python scripts/test_subtitle_styles.py [PROJECT_DIR]`

## 10. Internationalization ve Localization

Değerlendirme:
- UTF-8 dosya I/O doğru kullanılıyor.
- UI kopyalarında ASCII fallback var.
- Font fallback stratejisi kısmen mevcut, ama bidi/RTL veya language-specific render için açık bir strateji yok.
- `canonicalize_text()` çok dilli transcript uyumunu zayıflatıyor.

Öneri:
- UI etiketlerini tek kaynaktan üretin.
- Unicode normalization stratejisini daha güvenli hale getirin.
- Eğer Arapça/İbranice gibi diller hedefleniyorsa ASS shaping/font fallback testi ekleyin.

## 11. Önceliklendirme Tablosu

| ID | Konu | Impact | Effort | Öncelik |
|---|---|---:|---:|---|
| F1 | Exception suppression | Çok yüksek | Düşük | P0 |
| F2 | Style contract ve mutable preset | Yüksek | Düşük-Orta | P0 |
| F3 | ASS/path escaping | Yüksek | Orta | P0 |
| F7 | Renderer test açığı | Yüksek | Orta | P0 |
| F4 | Uygulanmayan public style API | Yüksek | Yüksek | P1 |
| F5 | Timing/chunking heuristics | Yüksek | Orta | P1 |
| F6 | Frontend parity drift | Orta | Orta | P1 |
| F8 | i18n/localization drift | Orta | Düşük | P2 |
| F9 | Import-time logger ve docs drift | Düşük | Düşük | P2 |

## 12. Risk Matrisi

| Olasılık \ Etki | Düşük | Orta | Yüksek | Çok yüksek |
|---|---|---|---|---|
| Yüksek | F9 | F8 | F3, F7 | F1 |
| Orta | - | F6 | F4, F5 | F2 |
| Düşük | - | Import-time process-group cleanup notu | - | - |

## 13. Somut Eylem Önerileri

### Backlog

| Öncelik | İş | Kabul Kriteri |
|---|---|---|
| P0 | `@logger.catch` suppression kaldır | Renderer/style hataları workflow'a exception olarak ulaşır |
| P0 | `style_name` validator ve `CUSTOM` sözleşmesi | Bilinmeyen stil 4xx döner veya açık custom payload gerekir |
| P0 | ASS ve filter path escape | Özel karakter içeren transcript ve path ile testler geçer |
| P0 | Renderer unit test paketi | En az header, escape, cancel, fallback testleri eklenir |
| P1 | `ResolvedRenderStyle` katmanı | Desteklenen alanlar açıkça ayrılır |
| P1 | Frontend `STYLE_REGISTRY` birleştirmesi | Label, preview, overlay aynı kaynaktan türetilir |
| P1 | Timing heuristics revizyonu | `animation_duration` gerçekten render davranışını etkiler |
| P2 | Logger setup refactor | Sink kurulumu startup'a taşınır |
| P2 | Docs parity güncellemesi | Mimari doküman gerçek davranışla hizalanır |

### Refactoring Roadmap

1. Faz 1 — Güvenilirlik ve sözleşme
   - F1, F2, F3, F7
2. Faz 2 — Render spec ve doğruluk
   - F4, F5
3. Faz 3 — UI parity ve operasyonel temizlik
   - F6, F8, F9

## 14. Teknik Borç Listesi

- `StyleManager` gerçek manager değil, global preset registry wrapper
- `create_custom_style()` public ama entegre değil
- `StyleManager` ve renderer arasında açık render-spec katmanı yok
- Preview helper içinde duplicate labels tutuluyor
- Overlay ve burn-in farklı görsel semantiklere sahip
- Dokümantasyon subtitle renderer gerçek komut akışından sapmış

## 15. UI Tarafı İçin Kısa Geliştirme Önerileri

- Preview bileşenine "yaklaşık parity" yerine "backend parity" modu ekleyin.
- Video overlay, mümkün olduğunca aynı registry'den türetilmiş inline style veya CSS variable kullanmalı.
- Stil seçicide yalnızca desteklenen davranışlar gösterilmeli; experimental alanlar kullanıcıya taşınmamalı.
- `CUSTOM` gerçekten desteklenmiyorsa UI'dan kaldırılmalı.

## 16. Referanslar

- `README.md`
- `.agents/skills/godtier-shorts/references/subtitle-style-parity.md`
- `.agents/skills/godtier-shorts/references/api-contracts.md`
- `.agents/skills/godtier-shorts/references/commands.md`
- `docs/architecture/subtitle-renderer.md`
- `docs/architecture/subtitle-styles.md`
- `backend/services/subtitle_styles.py`
- `backend/services/subtitle_renderer.py`
- `frontend/src/config/subtitleStyles.ts`
- `frontend/src/components/subtitlePreview/helpers.ts`
- `frontend/src/components/SubtitlePreview.tsx`
- `frontend/src/components/VideoOverlay.tsx`
