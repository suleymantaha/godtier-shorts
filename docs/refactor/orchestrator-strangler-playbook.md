# GodTier Shorts Refactor Playbook (Repo + Pilot)

## Hedef
- Monolitik akışları küçük, test edilebilir workflow modüllerine bölmek.
- Dış API/method imzalarını koruyarak iç mimariyi sadeleştirmek.
- Refactor sonrası davranış eşdeğerliğini test kapılarıyla doğrulamak.

## Pilot Sonucu (2026-03-12)
- `backend/core/orchestrator.py`: 955 satırdan 348 satıra indirildi (façade yaklaşımı).
- Uzun akışlar ayrı modüllere taşındı:
  - `backend/core/workflows.py`
  - `backend/core/command_runner.py`
  - `backend/core/media_ops.py`
  - `backend/core/workflow_helpers.py`
- Public entrypoint imzaları korundu:
  - `run_pipeline_async`
  - `run_manual_clip_async`
  - `run_batch_manual_clips_async`
  - `reburn_subtitles_async`

## Sprint Planı

### Sprint 0 - Baseline ve Güvenlik Ağı
- Kritik akışlar için parity baseline: pipeline/manual/batch/reburn.
- Test gate sabitleme:
  - `pytest backend/tests`
  - `npm run lint` (frontend)
  - `npm run test -- --reporter=dot` (frontend)
- Metrik hedefleri:
  - Façade dosyası < 350 satır
  - Uzun methodların workflow sınıflarına taşınması

### Sprint 1 - Pilot Strangler Refactor
- `GodTierShortsCreator` dış API/facade olarak bırakıldı.
- İç iş mantığı `PipelineWorkflow`, `ManualClipWorkflow`, `BatchClipWorkflow`, `ReburnWorkflow` içine taşındı.
- Subprocess/cancel/timeout mantığı `CommandRunner` ile izole edildi.

### Sprint 2 - Guardrail ve Standartlar
- Temp dosya lifecycle için ortak yardımcı (`TempArtifactManager`) eklendi.
- Progress dağıtımı için `ProgressStepMapper` eklendi.
- Refactor guardrail testi eklendi: `backend/tests/test_orchestrator_refactor_guardrails.py`.

### Sprint 3 - Repo Geneline Yayılım
- Aynı pattern diğer büyük modüllere uygulanır:
  - önce façade bırakılır,
  - akışlar workflow sınıflarına taşınır,
  - parity testleri zorunlu tutulur.

## Somut Örnekler

### 1) Monolitik Method -> Stage Decomposition

#### Problemli blok (önce)
- `run_pipeline_async` tek method içinde proje hazırlığı + indirme + transkript + LLM + render döngüsü.

#### Refactored yapı (sonra)
- `PipelineWorkflow.run` içinde stage fonksiyonları:
  - `_prepare_project`
  - `_ensure_master_assets`
  - `_ensure_transcript`
  - `_analyze_segments`
  - `_render_segments`

#### Neden daha iyi?
- Her stage ayrı testlenebilir ve hata kaynağı daha hızlı bulunur.

#### Risk ve rollback
- Risk: stage arası context kaybı.
- Rollback: façade methodlar değişmediği için tek commit rollback ile eski davranışa dönülebilir.

#### Test senaryoları
- pipeline başarılı akış
- pipeline transkript mevcutken skip akışı
- cancel_event tetiklenmesi

### 2) Subprocess ve Cancel İzolasyonu

#### Problemli blok (önce)
- Komut çalıştırma/cancel polling orkestratör sınıfında gömülüydü.

#### Refactored yapı (sonra)
- `CommandRunner.run_async` ve `run_sync` ile merkezi yönetim.

#### Neden daha iyi?
- Timeout/cancel sözleşmesi tek yerde, tekrarsız ve tutarlı.

#### Risk ve rollback
- Risk: event-loop lifecycle hataları.
- Rollback: `GodTierShortsCreator._run_command_with_cancel*` imzaları korunarak geriye uyumlu geçiş.

#### Test senaryoları
- timeout
- cancel_event sırasında process kill
- stderr/stdout decode davranışı

### 3) DRY Temp Lifecycle

#### Problemli blok (önce)
- Her akışta elle `try/finally` dosya silme tekrarı.

#### Refactored yapı (sonra)
- `TempArtifactManager` ile merkezi cleanup.

#### Neden daha iyi?
- Tekrarlayan cleanup kodu azaltıldı, unutulan temp dosya riski düştü.

#### Risk ve rollback
- Risk: yanlış path eklenmesiyle erken silme.
- Rollback: context manager kaldırılıp eski `try/finally` blokları geri alınabilir.

#### Test senaryoları
- başarı akışında tüm temp dosyalar siliniyor mu
- exception akışında cleanup yine çalışıyor mu

## SOLID / DRY / KISS Uygulaması
- SRP: workflow sınıfları tek akış sorumluluğu taşıyor.
- DIP: façade -> workflow bağımlılığı; düşük seviye ayrıntılar helper modüllerde.
- DRY: cleanup ve progress dağıtımı ortaklaştırıldı.
- KISS: façade dış API’yi koruyor, iç detaylar modüler.

## Quality Gates
- Backend: `pytest backend/tests` tam yeşil.
- Frontend: `npm run lint` + `npm run test -- --reporter=dot` yeşil.
- Refactor PR kuralı: parity kanıtı yoksa merge yok.

## Yaygınlaştırma Kuralı
- Yeni refactor her zaman aynı sırada ilerler:
  1. Baseline testleri kilitle.
  2. Facade bırak, workflow çıkar.
  3. Helper/adapter taşı.
  4. Parity testleri geç.
  5. ADR-lite kaydı ekle.
