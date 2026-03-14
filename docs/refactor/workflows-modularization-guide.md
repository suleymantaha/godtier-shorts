# Workflows Modülerleştirme Rehberi

Bu rehber, uzun/monolitik workflow dosyalarını küçük, test edilebilir ve düşük bağlılıklı parçalara ayırmak için uygulanabilir bir playbook sunar.

## 1) Kod Parçalama ve Modülerleştirme

### Hedef yapı
- `workflow_context.py`: sözleşme/protocol (port)
- `workflows_pipeline.py`: pipeline orchestration
- `workflows_manual.py`: tekli manuel + cut-points
- `workflows_batch.py`: toplu klip üretimi
- `workflows_reburn.py`: reburn akışı
- `workflows.py`: sadece public export/facade

### Problemli blok (önce)
- Tek dosyada (`workflows.py`) tüm akışların birlikte bulunması.
- Yüksek dosya boyutu, değişiklik etkisinin belirsizleşmesi.

### Refactored yapı (sonra)
- Akış bazlı dosya ayrımı + ince facade.
- Import yüzeyi korunur: `from backend.core.workflows import ...`

### Neden daha iyi?
- Değişiklik scope’u küçülür.
- İnceleme ve test hedefi netleşir.

## 2) Fonksiyonel Decomposition Stratejisi

### Örnek: Pipeline
- `PipelineWorkflow.run` sadece akış sırasını yönetir.
- Stage fonksiyonları:
  - `_prepare_project`
  - `_ensure_master_assets`
  - `_ensure_transcript`
  - `_analyze_segments`
  - `_render_segments`

### Uygulama adımı
1. Önce akışı stage listesine böl.
2. Her stage için tek giriş/tek çıkış sözleşmesi tanımla.
3. Stage hatalarını domain context’iyle yeniden yükselt.

## 3) SOLID Uygulaması

### SRP
- Her workflow tek iş sorumluluğu taşır.

### DIP
- Workflow sınıfları `OrchestratorContext` protocol’üne bağımlıdır, concrete sınıfa değil.

### ISP
- Context üzerinden yalnız gerekli capability’ler tüketilir.

## 4) DRY ve KISS

### DRY örnekleri
- Temp dosya yönetimi: `TempArtifactManager`
- Progress dağıtımı: `ProgressStepMapper`

### KISS
- `workflows.py` içinde iş mantığı yok, sadece export var.

## 5) Test Yazılabilirliğini Artırma

### Uygulanabilir yaklaşım
- Workflow testleri için sahte context (fake/stub) üret.
- Dış bağımlılıkları izole et:
  - subprocess -> `CommandRunner`
  - ağır medya işlemleri -> `to_thread` + mock

### Minimum test matrisi
- Başarılı akış
- Eksik dosya
- Cancel/timeout
- Partial cleanup
- Metadata merge davranışı

## 6) Dokümantasyon ve Kod Organizasyonu Standardı

- Her yeni workflow için:
  - data-flow özeti,
  - failure-mode tablosu,
  - input/output sözleşmesi.
- Refactor kararları ADR-lite ile kayda alınır.

## 7) Otomatik Refactor Araçları ve Lint

### Önerilen araçlar
- Python:
  - `ruff` (complexity, duplicate code sinyalleri)
  - `pytest` (parity/failure mode)
- Frontend:
  - ESLint complexity + max-lines-per-function (warning ile başlayıp kademeli strict)

### Kural örneği (kademeli geçiş)
- İlk faz: warning
- İkinci faz: kritik modüllerde error

## 8) Code Review Süreci ve Ekip Standardı

### Refactor PR’de zorunlu alanlar
- Behavior parity kanıtı
- Taşınan kod haritası
- Risk/rollback planı
- Test çıktıları

### İnceleme checklist
- Dış API korunmuş mu?
- Stage sınırları net mi?
- Yeni abstraction gereksiz komplekslik yaratıyor mu?
- Failure path testleri var mı?

## 9) Uygulama Planı (Kısa)

1. Baseline testleri kilitle.
2. Monolitik dosyayı domain akışlarına böl.
3. Public facade/import yüzeyini sabit tut.
4. Guardrail testleri ekle.
5. Lint strictliğini kademeli artır.
6. ADR-lite ve PR template ile süreci standardize et.
