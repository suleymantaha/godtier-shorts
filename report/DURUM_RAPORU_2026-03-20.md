# Durum Raporu (2026-03-20)

## 1) Bu fazda tamamlanan işler

- Faz 1 tamamlandı: verify hattını bloke eden üç frontend `react-hooks/set-state-in-effect` hatası giderildi.
- `frontend/src/test/components/videoOverlay.helpers.test.ts` güncel overlay davranışıyla hizalandı.
- `backend/tests/test_social_routes.py` içindeki zaman-duyarlı approval testi göreli gelecek tarih kullanacak şekilde deterministik hale getirildi.
- Ana denetim raporuna faz takibi eklendi; AUD-001 ve AUD-002 remediation durumu işlendi.

## 2) Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `53` warning
- `cd frontend && npm run test -- src/test/components/videoOverlay.helpers.test.ts --reporter=dot`
  - Sonuç: `3 passed`
- `pytest backend/tests/test_social_routes.py -q`
  - Sonuç: `12 passed`

## 3) Kalan riskler / blokajlar

- Faz 1 yalnız kapıyı açtı; frontend lint warning yükü hâlâ yüksek ve ayrı iyileştirme alanı olarak duruyor.
- Guardrail ihlalleri devam ediyor:
  - `backend/core/orchestrator.py` -> `366` satır, hedef `<=350`
  - `backend/core/workflows_manual.py` -> `233` satır, hedef `<=220`
  - `backend/core/workflows_reburn.py` -> `155` satır, hedef `<=150`
- `backend.core -> backend.api` bağımlılığı ve subtitle parity drift riski henüz ele alınmadı.

## 4) Sonraki net adım

- Faz 2'ye geç: orchestrator ve workflow guardrail ihlallerini public davranışı bozmadan bütçe içine al.
- Faz 2 kapanışında `pytest backend/tests/test_orchestrator_refactor_guardrails.py -q` ve `pytest backend/tests/test_workflows_refactor_guardrails.py -q` temiz olmalı.

## 5) Faz 2'de tamamlanan işler

- `backend/core/orchestrator.py` facade dosyası `366` satırdan `345` satıra indirildi.
- `backend/core/workflows_manual.py` dosyası `233` satırdan `217` satıra indirildi.
- `backend/core/workflows_reburn.py` dosyası `155` satırdan `137` satıra indirildi.
- Manual ve reburn akışlarında davranış korunarak tekrar eden JSON yazımı ve render payload kullanımı sadeleştirildi.

## 6) Faz 2 doğrulamaları

- `pytest backend/tests/test_orchestrator_refactor_guardrails.py -q`
  - Sonuç: `2 passed`
- `pytest backend/tests/test_workflows_refactor_guardrails.py -q`
  - Sonuç: `3 passed`
- `pytest backend/tests/test_route_imports_smoke.py -q`
  - Sonuç: `1 passed`
- `pytest backend/tests/test_social_routes.py -q`
  - Sonuç: `12 passed`

## 7) Faz 2 sonrası kalan riskler / blokajlar

- Guardrail kapısı yeşil, ancak `backend.core -> backend.api` ters bağımlılığı hâlâ açık.
- Subtitle preview ile backend render planı arasında contract/parity testi hâlâ yok.
- Docs drift ve Python dependency locking işleri henüz başlamadı.

## 8) Sonraki net adım

- Faz 3'e geç: `backend.core` içinden route/websocket/cache internallerine giden bağımlılıkları internal port/adaptor sınırına taşı.
- Aynı faz içinde subtitle planning için fixture/golden test yaklaşımını kur ve hedefli parity kontrollerini çalıştır.

## 9) Faz 3'te tamamlanan işler

- `backend/core/clip_events.py` ile internal `ClipEventPort` sözleşmesi tanımlandı.
- API katmanında `backend/api/clip_events.py` adapter'ı eklendi ve orchestrator route katmanından bu adapter ile kurulacak hale getirildi.
- `backend.core` içindeki doğrudan `backend.api` import'ları temizlendi.
- Frontend ve backend için ortak `tests/fixtures/subtitle_parity_cases.json` golden fixture seti eklendi.
- `backend/tests/test_subtitle_parity_contract.py` ve `frontend/src/test/utils/subtitleTiming.parity.test.ts` ile parity kontrolleri bağlandı.

## 10) Faz 3 doğrulamaları

- `rg -n "from backend\\.api|backend\\.api\\." backend/core`
  - Sonuç: eşleşme yok
- `pytest backend/tests/test_clip_ready_routing.py backend/tests/test_route_imports_smoke.py backend/tests/test_subtitle_parity_contract.py -q`
  - Sonuç: `3 passed`
- `pytest backend/tests/test_orchestrator_refactor_guardrails.py backend/tests/test_workflows_refactor_guardrails.py -q`
  - Sonuç: `5 passed`
- `cd frontend && npm run test -- src/test/utils/subtitleTiming.parity.test.ts --reporter=dot`
  - Sonuç: `3 passed`

## 11) Faz 3 sonrası kalan riskler / blokajlar

- Docs link drift ve rapor freshness yönetimi hâlâ açık.
- Python dependency çözümlemesi hâlâ lock'suz ve audit akışı henüz repo standardı değil.
- Frontend lint warning yükü devam ediyor; bu fazda kapsam dışı bırakıldı.

## 12) Sonraki net adım

- Faz 4'e geç: docs link checker ekle, kırık linkleri sıfırla ve Python dependency lock/audit akışını repo içinde tanımla.

## 13) Faz 4'te tamamlanan işler

- `scripts/check_markdown_links.py` eklendi ve `scripts/verify.sh` içine bağlandı.
- `docs/pages/*/README.md` ve `docs/operations/*/README.md` içindeki kırık relative linkler düzeltildi.
- `scripts/generate_requirements_lock.py`, `scripts/update_requirements_lock.sh` ve `scripts/audit_python_deps.sh` ile lock/audit akışı tanımlandı.
- `requirements.lock` üretildi ve audit bulgularına göre `PyJWT` ile `cryptography` minimum sürümleri güvenli sürümlere çekildi.
- `report/TEKNIK_DENETIM_RAPORU_2026-03-12.md` ve `report/TEKNIK_DENETIM_RAPORU_2026-03-13.md` historical snapshot olarak etiketlenecek şekilde güncellendi.

## 14) Faz 4 doğrulamaları

- `python scripts/check_markdown_links.py docs README.md`
  - Sonuç: `Markdown links ok: 49 files checked`
- `bash scripts/update_requirements_lock.sh`
  - Sonuç: `Wrote requirements.lock`
- `bash scripts/audit_python_deps.sh`
  - Sonuç: `No known vulnerabilities found`
- `bash scripts/verify.sh`
  - Sonuç: tüm adımlar geçti; frontend `232 passed`, backend `254 passed, 2 skipped`, build başarılı

## 15) Final durum

- Faz 1, Faz 2, Faz 3 ve Faz 4 tamamlandı.
- Repo kalite kapısı yeniden yeşile döndü.
- Açık ama kapsam dışı kalan ana teknik borç: frontend lint warning yükü ve daha ileri parity tek-kaynak mimarisi.

## 16) Faz sonrası checkpoint — GTS-A06 frontend warning azaltımı

### Bu adımda tamamlanan işler

- `frontend/src/auth/useResilientAuth.ts` içinde backend identity sync akışı ana hook'tan ayrıldı.
- `frontend/src/auth/useResilientAuth.helpers.ts` içinde fallback auth state çözümlemesi yardımcı fonksiyonlara bölündü.
- `frontend/src/components/HoloTerminal.tsx`, `frontend/src/components/SubtitlePreview.tsx` ve `frontend/src/components/VideoOverlay.tsx` içinde effect/render sorumlulukları küçük yardımcı parçalara ayrıldı.
- `frontend/src/components/autoCutEditor/useAutoCutEditorState.ts` içinde başlangıç session çözümlemesi tek helper altında toplandı.
- `frontend/src/test/utils/subtitleTiming.test.ts` daha küçük senaryo gruplarına ayrıldı.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `45` warning
- `cd frontend && npm run test -- src/test/components/HoloTerminal.test.tsx src/test/components/SubtitlePreview.test.tsx src/test/components/VideoOverlay.test.tsx src/test/utils/subtitleTiming.test.ts src/test/utils/subtitleTiming.parity.test.ts --reporter=dot`
  - Sonuç: `5 files passed`, `43 passed`

### Kalan riskler / blokajlar

- Frontend warning yükü azaldı ama henüz kapanmadı; özellikle `frontend/src/api/client.ts`, `subtitleEditor/*`, `useWebSocket.ts` ve büyük test dosyaları ana borç alanı olarak duruyor.
- `autoCutEditor/useAutoCutEditorState.ts` içindeki initial-state helper karmaşıklığı sınırda kaldı; bir sonraki turda controller/state dilimini birlikte ele almak daha verimli olacak.

### Sonraki net adım

- `GTS-A06` kapsamında sıradaki hedef küme: `frontend/src/api/client.ts`, `frontend/src/components/autoCutEditor/*` ve `frontend/src/hooks/useWebSocket.ts`.
- Hedef: warning sayısını bir sonraki checkpoint'te `45` altına indirirken ilgili hedefli testleri yeşil tutmak.

## 17) Faz sonrası checkpoint — GTS-A06 auth/websocket/auto-cut kümesi

### Bu adımda tamamlanan işler

- `frontend/src/api/client.ts` içinde token refresh, forced replay ve protected-request hata senkronizasyonu yardımcı fonksiyonlara ayrıldı.
- `frontend/src/hooks/useWebSocket.ts` içinde store ref kurulumu, progress event işleme, reconnect ve cleanup akışları ayrı yardımcı parçalara bölündü.
- `frontend/src/components/autoCutEditor/useAutoCutEditorController.ts` dönüş modeli hook dışına taşındı.
- `frontend/src/components/autoCutEditor/useAutoCutEditorState.ts` başlangıç session çözümlemesi timing/subtitle yardımcılarına ayrıldı.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `37` warning
- `cd frontend && npm run test -- src/test/api/client.test.ts src/test/unit/useWebSocket.test.tsx src/test/components/AutoCutEditor.flow.test.tsx --reporter=dot`
  - Sonuç: `3 files passed`, `20 passed`

### Kalan riskler / blokajlar

- Hedef kümede `frontend/src/components/autoCutEditor/sections.tsx` içindeki `AutoCutSubtitleOptions` hâlâ satır bütçesini aşıyor.
- Sonraki yoğun warning adaları `clipGallery/*`, `jobForm/*` ve büyük `subtitleEditor/*` yüzeyi.

### Sonraki net adım

- Önce `autoCutEditor/sections.tsx` içindeki son warning'i kapat.
- Ardından `clipGallery` kümesine geçip küçük view/controller ayrımlarıyla warning sayısını aşağı çekmeye devam et.

## 18) Faz sonrası checkpoint — GTS-A06 auto-cut/clip-gallery kümesi

### Bu adımda tamamlanan işler

- `frontend/src/components/autoCutEditor/sections.tsx` içinde subtitle option satırları toggle/status yardımcı bileşenlerine ayrıldı ve bu kümedeki son lint warning kapatıldı.
- `frontend/src/components/clipGallery/sections.tsx` içinde header summary ve toolbar bölümleri ayrıştırıldı.
- `frontend/src/components/clipGallery/useClipGalleryController.ts` state, retry, fetch, effect, delete-action ve view-model sorumluluklarına bölündü.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `34` warning
- `cd frontend && npm run test -- src/test/components/ClipGallery.test.tsx src/test/components/AutoCutEditor.flow.test.tsx --reporter=dot`
  - Sonuç: `2 files passed`, `16 passed`

### Kalan riskler / blokajlar

- `ClipGallery` hedefli testleri geçiyor, ancak Vitest çıktısında async state güncellemeleri için `act(...)` uyarıları görünmeye devam ediyor; test güvenilirliğini bozmuyor ama ileride temizlenmesi faydalı.
- Kalan warning yoğunluğu artık daha çok `jobForm/*`, `subtitleEditor/*`, `editor/helpers.ts` ve bazı büyük test dosyalarında toplandı.

### Sonraki net adım

- Sıradaki hedef küme: `frontend/src/components/jobForm/*` ve `frontend/src/components/editor/helpers.ts`.
- Ardından en yüksek warning adası olan `subtitleEditor/*` için ayrı bir daha büyük refactor turu planlanmalı.

## 19) Faz sonrası checkpoint — GTS-A06 editor/job-form kümesi

### Bu adımda tamamlanan işler

- `frontend/src/components/editor/helpers.ts` içinde stored editor state çözümlemesi default/clip yardımcılarına ayrıldı.
- `frontend/src/components/jobForm/sections.tsx` içinde control grid kartları küçük select/toggle/input bileşenlerine bölündü.
- `frontend/src/components/jobForm/useJobFormController.ts` içinde state, id, sync, cache-status ve submit akışları ayrı yardımcı hook/fonksiyonlara taşındı.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `32` warning
- `cd frontend && npm run test -- src/test/components/editor.helpers.test.ts src/test/components/JobForm.submission.test.tsx src/test/components/JobForm.preferences.test.tsx src/test/components/JobForm.accessibility.test.tsx --reporter=dot`
  - Sonuç: `4 files passed`, `19 passed`

### Kalan riskler / blokajlar

- `jobForm` kümesinde yalnız `useJobFormStartAction` için tek bir satır-bütçesi warning kaldı; davranış temiz ama istenirse bir sonraki turda kolayca kapanabilir.
- Kalan warning borcu artık büyük ölçüde `subtitleEditor/*`, `subtitlePreview/helpers.ts`, `subtitleStyles.ts`, `useWebSocket.helpers.ts` ve bazı büyük test dosyalarında yoğunlaşıyor.

### Sonraki net adım

- Öncelik artık `frontend/src/components/subtitleEditor/*` warning adası olmalı.
- Daha küçük ara hedef istenirse `useJobFormStartAction` ve birkaç helper warning’i önce temizlenebilir, ama en yüksek kaldıraç `subtitleEditor` tarafında.

## 20) Faz sonrası checkpoint — GTS-A06 subtitle-editor başlangıç dilimi

### Bu adımda tamamlanan işler

- `frontend/src/components/jobForm/useJobFormController.ts` içinde `useJobFormStartAction` parametre tipi ayrıştırıldı ve `jobForm` kümesindeki kalan küçük warning kapatıldı.
- `frontend/src/components/subtitleEditor/sections.tsx` içinde panel props passthrough kaldırıldı ve preview/transcript alanları daha net alt parçalara ayrıldı.
- `subtitleEditor` yüzeyinde ilk düşük riskli dilim sadeleştirildi; test davranışı korunarak daha büyük refactor için hazırlık yapıldı.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `30` warning
- `cd frontend && npm run test -- src/test/components/editor.helpers.test.ts src/test/components/JobForm.submission.test.tsx src/test/components/JobForm.preferences.test.tsx src/test/components/JobForm.accessibility.test.tsx src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
  - Sonuç: `7 files passed`, `36 passed`

### Kalan riskler / blokajlar

- Kalan warning borcu artık yoğun biçimde `subtitleEditor/*` içinde toplandı; özellikle `buildRenderWarnings`, `TranscriptCard`, `useTranscriptLoader` ve `useSubtitleEditorActions` ana sıcak noktalar.
- Bu alan daha derin refactor gerektirdiği için küçük checkpoint’lerle ilerlemek hâlâ doğru yaklaşım.

### Sonraki net adım

- `frontend/src/components/subtitleEditor/sections.tsx` içindeki `TranscriptCard` ve `buildRenderWarnings` dilimini ayır.
- Ardından `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde `useTranscriptLoader` ve `useSubtitleEditorActions` sorumluluklarını böl.
