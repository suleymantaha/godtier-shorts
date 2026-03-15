# v2.1 Stabilizasyon Sonuç Raporu

**Tarih:** 2026-03-15  
**Kapsam:** Tracking güven eşiği, transcript/snapping güvenliği, subtitle overflow güvenliği, A/V guardrail, kalite metadata'sı, debug artifact bundle'ı, benchmark hattı, test stabilizasyonu ve dokümantasyon senkronizasyonu

## Yönetici Özeti

v2.1 kapsamındaki backend, frontend ve test altyapısı işleri tamamlandı. Render zinciri artık kalite metriği üreten, düşük kaliteli durumlarda daha kontrollü degrade olan ve clip bazında tanı verisi bırakabilen bir yapıda çalışıyor. Repo düzeyi kalite kapısı da tekrar yeşile döndü.

## Uygulanan Başlıklar

### 1. Tracking ve Crop Kararları

- YOLO akışı `track(..., persist=True, tracker="bytetrack.yaml", classes=[0])` tabanına taşındı.
- Confidence eşiği, accept score, grace/reacquire, shot-cut confidence ve controlled-return kuralları eklendi.
- Split kararı klibin tamamına yayılan örnek pencerelerle veriliyor.
- Tracking çıktıları `tracking_quality` ve `debug_tracking` altında raporlanıyor.

### 2. Transcript ve Subtitle Güvenliği

- Boundary snap, `word_coverage_ratio` ile kaliteye bağlı çalışıyor.
- Clip-local transcript üretiminde overlap korunuyor; `segment.text` retained word listeden tekrar kuruluyor.
- Subtitle chunking artık kelime sayısı yanında süre ve safe-area/overflow kontrollerini de kullanıyor.
- Frontend overlay preview, backend burn ile aynı chunk/word modeline hizalandı.

### 3. A/V Guardrail ve Debug

- CFR normalize ve drift ölçümü raporlanıyor.
- `audio_validation` ve `debug_timing` alanları clip metadata'ya ekleniyor.
- `DEBUG_RENDER_ARTIFACTS=1` ile clip bazlı debug bundle yazılıyor:
  - `tracking_overlay.mp4`
  - `tracking_timeline.json`
  - `subtitle_chunks.json`
  - `boundary_snap.json`
  - `timing_report.json`

### 4. Kalite Skoru ve Batch Kararı

- `render_quality_score` üretimi eklendi.
- Batch çıktıları kalite skoruna göre sıralanıyor.
- `SubtitleEditor` clip modunda read-only kalite kartı gösteriyor.

### 5. Test Altyapısı

- Backend test hang problemi giderildi.
- HTTP ve WebSocket testleri daha kararlı bir ASGI test harness ile çalışıyor.
- Workflow refactor guardrail bütçeleri yeniden sağlandı.

## Doğrulama Sonuçları

### Repo Düzeyi

```bash
bash scripts/verify.sh
```

Sonuç:

- toolchain check: geçti
- runtime config check: geçti
- frontend lint: geçti, `0 error / 36 warning`
- frontend test: `45 passed`
- backend pytest: `207 passed, 3 skipped`
- frontend build: geçti

## Çalıştırılan Kritik Komutlar

```bash
pytest backend/tests -q
pytest backend/tests/test_workflows_refactor_guardrails.py -q
pytest backend/tests/test_subtitle_styles.py -q
pytest backend/tests/integration/test_api_auth_and_errors.py -q
pytest backend/tests/test_social_routes.py -q
pytest backend/tests/test_websocket_auth.py -q
cd frontend && npm run test -- --reporter=dot
cd frontend && npm run build
cd frontend && npm run lint
```

## Beklenen Skip'ler

- `backend/tests/test_manual_crop.py`
  - Gerçek `master.mp4` veya ffmpeg/NVENC ortamı yoksa skip edilir.
- `backend/tests/test_raw_video_saved.py`
  - Özel fixture proje yoksa skip edilir.
- `backend/tests/test_viral_analyzer_params.py`
  - Cloud API gerektiren placeholder test skip edilir.

## Güncellenen Dokümantasyon

- Ana giriş ve komutlar:
  - `README.md`
  - `docs/README.md`
  - `frontend/README.md`
  - `scripts/README.md`
- Mimari:
  - `docs/architecture/video-processor.md`
  - `docs/architecture/subtitle-renderer.md`
  - `docs/architecture/transcription.md`
  - `docs/logic/video-processor/README.md`
  - `docs/logic/subtitle-renderer/README.md`
  - `docs/logic/transcription/README.md`
- Akışlar:
  - `docs/flows/youtube-pipeline.md`
  - `docs/flows/manual-cut.md`
  - `docs/flows/batch-clips.md`
  - `docs/flows/reburn.md`
  - `docs/operations/youtube-pipeline/README.md`
  - `docs/operations/manual-cut/README.md`
  - `docs/operations/batch-clips/README.md`
  - `docs/operations/reburn/README.md`
- UI:
  - `docs/pages/subtitle-editor.md`
- Skill referansları:
  - `.agents/skills/godtier-shorts/references/api-contracts.md`
  - `.agents/skills/godtier-shorts/references/runtime-and-paths.md`
  - `.agents/skills/godtier-shorts/references/workflows.md`
  - `.agents/skills/godtier-shorts/references/examples.md`

## Kalan Teknik Borç

- Frontend lint içinde 36 warning devam ediyor; doğrulamayı bloklamıyor ama ayrı bir temizlik işi olarak ele alınmalı.
- Debug overlay artifact şu an tanı amaçlı; ayrı download UI veya public file route yok.
- Benchmark hattı manuel/ops amaçlı; CI gate'i değil.
- Quality score şu aşamada gallery sıralamasını etkilemiyor.

## Genel Durum

Bu milestone sonunda sistem:

- daha deterministik crop kararı veriyor,
- transcript kalitesi kötü olduğunda daha muhafazakâr davranıyor,
- subtitle preview ile burn çıktısını daha iyi eşliyor,
- A/V drift ve overflow gibi sessiz hataları ölçebiliyor,
- clip bazında operasyonel tanı verisi bırakabiliyor,
- tam repo doğrulamasını yeniden başarılı şekilde geçiyor.
