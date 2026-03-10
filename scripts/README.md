# scripts/

Yardımcı ve integration scriptleri. Unit testler `backend/tests/` ve `frontend/src/**/*.test.*` altındadır.

| Script | Açıklama |
|--------|----------|
| `test_subtitle_styles.py` | Altyazı stilleri ASS üretimini gerçek proje ile test eder. `python scripts/test_subtitle_styles.py [PROJECT_DIR]` |
| `ass_format_example.py` | ASS pop/fade override string örnekleri. |
| `reburn_clip.py` | Klibe yeni layout/stil uygular. `python scripts/reburn_clip.py --project ID --clip NAME [--layout split] [--style HORMOZI]` |
| `check_orphan_legacy.py` | Legacy/orphan script/import guard. CI içinde çalışır ve kanonik yol olarak `backend.services.subtitle_renderer` kullanımını zorlar. |
