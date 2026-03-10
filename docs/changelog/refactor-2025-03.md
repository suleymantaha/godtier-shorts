# Refactor Özeti - Ortak Kod Blokları (2025-03)

## Yapılan Değişiklikler

### 1. viral_analyzer.py — `_parse_llm_json_response()`

**Sorun:** `analyze_metadata` ve `analyze_transcript_segment` içinde aynı LLM JSON parse mantığı tekrarlanıyordu (```json``` temizliği, süslü parantez çıkarma, `segments` normalizasyonu).

**Çözüm:** Ortak `_parse_llm_json_response(content: str) -> dict | None` static metodu eklendi. Her iki analiz metodu bu helper'ı kullanıyor.

**Etki:** ~40 satır tekrar kaldırıldı, bakım kolaylaştı.

---

### 2. orchestrator.py — `_cut_and_burn_clip()`

**Sorun:** `run_pipeline`, `run_manual_clip`, `run_batch_manual_clips` içinde aynı video kesme + altyazı yakma bloğu 3 kez tekrarlanıyordu.

**Çözüm:** Ortak `_cut_and_burn_clip()` metodu eklendi:
- `create_viral_short` veya `cut_segment_only` çağrısı
- Altyazı varsa: `shutil.copy2` + `burn_subtitles_to_video`
- Altyazı yoksa: `shutil.move`

**Etki:** ~60 satır tekrar kaldırıldı, tek noktadan güncelleme sağlandı.

---

## Düzeltme: viral_analyzer fallback davranışı

**Sorun:** `_parse_llm_json_response` geçerli JSON bulamadığında `return None` yapıyordu. Orijinal kodda bu durumda `raise` ile dış `except Exception` tetiklenip fallback analiz çalışıyordu. Refactor sonrası fallback devreye girmiyordu.

**Çözüm:** JSON parse tamamen başarısız olduğunda (`{` `}` yok) `json.JSONDecodeError` fırlatılıyor; böylece dış `except Exception` fallback’i tetikliyor.

---

## Test Sonucu

```
33 passed, 1 skipped
```

- `test_manual_crop` — run_manual_clip refactor doğrulandı
- `test_raw_video_saved` — run_manual_clip + _raw.mp4 kaydı doğrulandı
- `test_viral_analyzer_params` — viral_analyzer refactor doğrulandı
