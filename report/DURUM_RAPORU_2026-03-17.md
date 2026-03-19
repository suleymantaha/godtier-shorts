# Durum Raporu (2026-03-17)

## 1) Bu turda tamamlanan işler

- Repo keşif çıktıları üretildi:
  - `report/repo-manifest-2026-03-17.txt`
  - `report/repo-tree-depth3-2026-03-17.txt`
  - `docs/analysis/repo-deep-scan-2026-03-17.md`
- Tek noktadan gezinme için indeks oluşturuldu:
  - `report/INDEX.md`
- Skill ajan promptu güçlendirildi ve iki kopya senkronlandı:
  - `.agents/skills/godtier-shorts/agents/openai.yaml`
  - `.cursor/skills/godtier-shorts/agents/openai.yaml`
- `backend/services/subtitle_styles.py` ve `backend/services/subtitle_renderer.py` için CI/CD odaklı kalite analizi çıkarıldı.

## 2) Doğrulama çıktısı

- Aşağıdaki testler çalıştırıldı ve geçti:
  - `pytest backend/tests/test_subtitle_styles.py backend/tests/test_subtitle_renderer.py backend/tests/test_workflow_runtime.py -q`
- Sonuç: `46 passed`.

## 3) Kritik bulgular (CI/CD)

- Subtitle alanında temel test kapsaması var:
  - `backend/tests/test_subtitle_styles.py`
  - `backend/tests/test_subtitle_renderer.py`
  - `backend/tests/test_workflow_runtime.py`
- Guardrail dokümanında CI’da çalıştığı belirtilen kontrol, verify kapısında görünmüyor:
  - Doküman: `scripts/README.md` (`check_orphan_legacy.py` CI içinde deniyor)
  - Kapı: `scripts/verify.sh` (bu adım yok)
- Yardımcı script drift’i var:
  - `scripts/test_subtitle_styles.py` içinde `generate_ass_file(whisperx_json_path=...)`
  - Güncel imza: `backend/services/subtitle_renderer.py` -> `generate_ass_file(transcript_json_path=...)`

## 4) Çalışma ağacı notu

- Repo şu anda geniş çapta kirli (çok sayıda `M`, `D`, `??` dosya) ve bu değişikliklerin büyük kısmı bu turda yapılmadı.
- Bu rapor yalnızca mevcut durumun özetidir; herhangi bir revert uygulanmadı.

## 5) Sonraki net adım önerisi

- `scripts/verify.sh` içine şu iki adımı eklemek:
  - `python scripts/check_orphan_legacy.py`
  - `pytest backend/tests/test_subtitle_styles.py backend/tests/test_subtitle_renderer.py backend/tests/test_workflow_runtime.py -q`
- Ardından `.github/workflows/verify.yml` altında bu kapıyı zorunlu çalıştırmak (PR/push).

