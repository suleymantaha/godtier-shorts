# Durum Raporu - 21 Mart 2026

## 1) GTS-A06 subtitle-editor checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/components/subtitleEditor/sections.tsx` içinde preview ve transcript bölümlerine giden prop wiring yardımcı fonksiyonlara taşındı; ana içerik bileşeni satır bütçesi altına çekildi.
- `buildRenderWarnings` veri odaklı kural listesi ve küçük context çözücülerine bölündü; render kalite uyarıları aynı davranışla daha okunabilir hale geldi.
- `TranscriptCard` içindeki durum kararları ayrı state çözümleyicisine taşındı; transcript durum kartları ve reburn uyarısı daha net sorumluluk sınırlarıyla korunmuş oldu.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `26` warning
- `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
  - Sonuç: `3 files passed`, `17 passed`

### Kalan riskler / blokajlar

- Kalan warning borcunun en yoğun kısmı artık `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde toplandı.
- `subtitleEditor` görünüm katmanı temizlenmiş olsa da controller tarafındaki hook bağımlılıkları ve async akışlar daha dikkatli, test korumalı refactor gerektiriyor.

### Sonraki net adım

- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde önce `useTranscriptLoader`, sonra `useSubtitleEditorActions` sorumluluklarını böl.
- Ardından daha küçük helper adaları olan `frontend/src/components/subtitlePreview/helpers.ts` ve `frontend/src/hooks/useWebSocket.helpers.ts` warning’lerine geç.

## 2) GTS-A06 subtitle-editor controller checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde locked-clip seçimi için setter bağımlılıkları ayrıştırıldı; `react-hooks/exhaustive-deps` uyarısı kaldırıldı.
- Transcript loader akışı proje/klip/no-selection dallarına ayrılan küçük yardımcı fonksiyonlara bölündü; error-reset ve workspace reset davranışı ortaklaştırıldı.
- Editor action katmanında parametre yüzeyi daraltıldı, text updater ayrı helper hook'a taşındı ve save akışında clip project çözümleme tek noktaya indirildi.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `19` warning
- `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
  - Sonuç: `3 files passed`, `17 passed`

### Kalan riskler / blokajlar

- `subtitleEditor` tarafında kalan warning'ler artık daha dar üç noktada toplandı: `useSubtitleJobTrackingEffect`, `useSubtitleRecoveryAction` ve `buildSubtitleEditorController`.
- Repo genelinde kalan warning borcunun büyük kısmı artık test dosyaları, `useWebSocket.helpers.ts`, `subtitlePreview/helpers.ts` ve `useJobStore.ts` çevresinde.

### Sonraki net adım

- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde job tracking ve recovery akışlarını ayrı karar yardımcılarına böl.
- Ardından `frontend/src/components/subtitlePreview/helpers.ts` ve `frontend/src/hooks/useWebSocket.helpers.ts` complexity warning’lerini kapat.

## 3) GTS-A06 subtitle-editor controller kapanış checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde job completion/error kararları ayrı helper fonksiyonlara taşındı; `useSubtitleJobTrackingEffect` daha okunur hale geldi.
- Recovery akışında eligibility ve project-id çözümleme tek noktalı yardımcı fonksiyonlara ayrıldı; `useSubtitleRecoveryAction` içindeki karar karmaşıklığı azaltıldı.
- Controller çıktısı `state` ve `handler` builder'larına bölündü; subtitle-editor controller dosyası kendi lint warning'lerinden tamamen temizlendi.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `16` warning
- `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
  - Sonuç: `3 files passed`, `17 passed`

### Kalan riskler / blokajlar

- Kalan warning borcu artık subtitle-editor dışına taşındı; ana küçük adalar `subtitlePreview/helpers.ts`, `useWebSocket.helpers.ts` ve `useJobStore.ts`.
- Kalan warning’lerin büyük bölümü test dosyalarındaki `max-lines-per-function` kuralından geliyor; davranış riski düşük ama temizlik hacmi daha geniş.

### Sonraki net adım

- `frontend/src/components/subtitlePreview/helpers.ts` ve `frontend/src/hooks/useWebSocket.helpers.ts` complexity warning’lerini kapat.
- Ardından `frontend/src/store/useJobStore.ts` içindeki `normalizeJob` ve büyük store action gövdesini parçala.

## 4) GTS-A06 preview and websocket helpers checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/components/subtitlePreview/helpers.ts` içinde preview shell/base-style üretimi daha küçük yardımcı fonksiyonlara ayrıldı; preview model üretimi aynı davranışla daha okunur hale geldi.
- `frontend/src/hooks/useWebSocket.helpers.ts` içinde parse, schema doğrulama, event-id ve source çözümleme ayrı helper’lara taşındı; `parseProgressMessage` complexity uyarısı kapandı.
- Bu adımla subtitle preview ve websocket helper adaları temizlendi; kalan warning borcu daha çok `subtitleStyles`, `useJobStore` ve büyük test dosyalarında toplandı.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: `0` error, `14` warning
- `cd frontend && npm run test -- src/test/components/subtitlePreview.helpers.test.ts src/test/unit/useWebSocket.helpers.test.ts --reporter=dot`
  - Sonuç: `2 files passed`, `10 passed`

### Kalan riskler / blokajlar

- Kalan üretim kodu warning’leri artık daha küçük sayıda ama daha merkezi dosyalarda: `frontend/src/config/subtitleStyles.ts` ve `frontend/src/store/useJobStore.ts`.
- Kalan warning’lerin önemli kısmı test dosyalarındaki `max-lines-per-function` kuralından geliyor; risk düşük ama hacim geniş.

### Sonraki net adım

- `frontend/src/config/subtitleStyles.ts` içindeki `getSubtitleBoxStyle` complexity warning’ini kapat.
- Ardından `frontend/src/store/useJobStore.ts` içindeki `normalizeJob` ve büyük store action akışını parçala.

## 5) GTS-A06 frontend warning kapanış checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/config/subtitleStyles.ts` ve `frontend/src/store/useJobStore.ts` içindeki kalan üretim kodu warning’leri kapatıldı; ardından tüm test dosyaları konu bazlı daha küçük `describe` bloklarına ayrılarak `max-lines-per-function` warning’leri temizlendi.
- Lint temizliği sonrası ortaya çıkan frontend TypeScript build blocker’ları da aynı turda giderildi; özellikle `api/client`, `useResilientAuth`, `HoloTerminal`, `useWebSocket`, `SubtitlePreview`, `VideoOverlay` ve `jobForm` tip yüzeyleri düzeltildi.
- Sonuçta frontend tarafında lint, tam test paketi ve production build birlikte yeşile döndü; `GTS-A06` remediation kapanmış oldu.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run lint`
  - Sonuç: temiz
- `cd frontend && npm run test -- --reporter=dot`
  - Sonuç: `50` test dosyası geçti, `232 passed`
- `cd frontend && npm run build`
  - Sonuç: başarılı

### Kalan riskler / blokajlar

- Frontend lint warning borcu kalmadı; ana kalan frontend riski test çıktısındaki `ClipGallery` `act(...)` console-noise uyarıları, fakat bunlar şu anda test başarısını etkilemiyor.
- Repo seviyesinde sonraki doğal teknik borç odağı artık terminoloji sweep ve test ergonomisi temizliği.

### Sonraki net adım

- `GTS-A06` kapandı; sonraki sırayı `GTS-A07` terminoloji sweep veya test console-noise temizliği alabilir.
- Geniş repo verify kapısı istenirse bu noktadan sonra yeniden tam `bash scripts/verify.sh` koşulabilir.

## 6) GTS-A07 ve test ergonomisi kapanış checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/test/components/ClipGallery.test.tsx` içinde varsayılan test zamanlayıcısı gerçek zamana çekildi; yalnız zaman atlatması gereken auth-blocked senaryosu lokal fake timer ile sınırlandı. Böylece tam frontend test koşusundaki `ClipGallery` `act(...)` console-noise temizlendi.
- Aktif repo yüzeyindeki terminoloji sweep tamamlandı; `scripts/test_subtitle_styles.py` içindeki eski `whisperx_json_path` çağrısı `transcript_json_path` olarak güncellendi.
- `README.md` ve `docs/refactor/workflow-failure-modes.md` içindeki kullanıcıya dönük operasyonel dil tek terminolojiye çekildi; aktif dokümanlarda transkripsiyon motoru adı artık tutarlı biçimde `faster-whisper`.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run test -- src/test/components/ClipGallery.test.tsx --reporter=dot`
  - Sonuç: `11 passed`
- `cd frontend && npm run lint -- src/test/components/ClipGallery.test.tsx`
  - Sonuç: temiz
- `python -m py_compile scripts/test_subtitle_styles.py`
  - Sonuç: temiz
- `rg -n "WhisperX|whisperx|whisperx_json_path" backend frontend scripts docs README.md .agents .github --glob '!report/**' --glob '!docs/analysis/**' --glob '!legacy/**'`
  - Sonuç: aktif dosyalarda eşleşme yok
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti; frontend lint temiz, frontend test `232 passed`, backend pytest `254 passed, 2 skipped`, frontend build başarılı

### Kalan riskler / blokajlar

- Tam `verify` kapısında kırmızı kalan alan yok.
- Backend pytest sırasında görülen iki `Swig*` deprecation warning üçüncü taraf binding kaynaklı; bu turdaki iş kapsamını ve geçerlilik kapısını etkilemiyor.

### Sonraki net adım

- `GTS-A07` ve `ClipGallery` test ergonomisi temizliği kapandı.
- Bir sonraki gerçek backlog odağı artık `GTS-A08` ve sonrası; yeni iş seçimi bunlar arasından yapılabilir.

## 7) GTS-A08 job state kalıcılığı checkpoint

### Bu adımda tamamlanan işler

- `backend/services/job_state.py` ile kalıcı bir job repository katmanı eklendi; job kayıtları artık runtime-only alanları ayıklanmış biçimde `workspace/state/jobs.json` altında saklanıyor.
- `backend/api/websocket.py` içindeki singleton manager bu repository ile başlatıldı; izole test manager'ları ise in-memory çalışmaya devam edecek şekilde mevcut test yüzeyi korunmuş oldu.
- Persist edilen yarım işler restart sonrası güvenli biçimde `error` durumuna alınacak şekilde normalize edildi; böylece process içi task handle kaybolduğunda yanlışlıkla sonsuz `queued/processing` kayıtları kalmayacak.

### Çalıştırılan doğrulamalar

- `pytest backend/tests/test_job_state_repository.py backend/tests/test_job_fairness.py backend/tests/test_job_ownership.py backend/tests/test_jobs_api_serialization.py backend/tests/unit/test_job_lifecycle.py backend/tests/test_websocket_subject_isolation.py -q`
  - Sonuç: `15 passed`
- `pytest backend/tests/test_subject_purge.py backend/tests/test_jobs_cache_invalidation.py backend/tests/test_clip_ready_routing.py backend/tests/test_editor_batch_visibility.py backend/tests/test_clip_transcript_recovery.py backend/tests/test_clip_transcript_routes.py backend/tests/test_clips_cache.py -q`
  - Sonuç: `22 passed`
- `python -m py_compile backend/api/routes/jobs.py backend/api/routes/editor.py backend/api/routes/clips.py backend/api/websocket.py backend/services/job_state.py`
  - Sonuç: temiz
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti; frontend lint temiz, frontend test `232 passed`, backend pytest `256 passed, 2 skipped`, frontend build başarılı

### Kalan riskler / blokajlar

- Job state artık kalıcı ama hâlâ tek-node yerel JSON store üzerinden tutuluyor; çoklu worker veya dış queue/repository henüz yok.
- Backend pytest sırasında görülen iki `Swig*` deprecation warning üçüncü taraf binding kaynaklı ve bu checkpoint’i bloke etmiyor.

### Sonraki net adım

- `GTS-A08` için repo içi ilk güvenli kesit kapandı: job repository soyutlaması ve kalıcı state devrede.
- Sıradaki backlog odağı `GTS-A09` olabilir; `/api/projects` hata anında degrade durumunu doğru modellemek en mantıklı sonraki adım.

## 8) GTS-A09 `/api/projects` degrade-mode checkpoint

### Bu adımda tamamlanan işler

- `frontend/src/api/client.ts` içinde proje listeleme çağrısı `good/degraded/unknown` durum modeliyle genişletildi; başarılı sonuçlar local cache'e yazılıyor, hata anında varsa son senkron liste `degraded`, yoksa `unknown` olarak dönüyor.
- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` ve `frontend/src/components/subtitleEditor/sections.tsx` tarafında bu yeni durum modeli UI'ye taşındı; artık `/api/projects` bozulduğunda "Henüz proje yok" gibi sentetik sağlıklı boş durum gösterilmiyor.
- `SubtitleEditor` akışı degrade durumda son senkron proje listesini kullanmaya devam ederken kullanıcıya görünür uyarı veriyor; unknown durumda ise boş-state yerine hata gösteriliyor.

### Çalıştırılan doğrulamalar

- `cd frontend && npm run test -- src/test/api/client.test.ts src/test/components/SubtitleEditor.project.test.tsx --reporter=dot`
  - Sonuç: `16 passed`
- `cd frontend && npx eslint src/api/client.ts src/components/subtitleEditor/useSubtitleEditorController.ts src/components/subtitleEditor/sections.tsx src/test/api/client.test.ts src/test/components/SubtitleEditor.project.test.tsx src/test/components/subtitleEditor.test-helpers.tsx`
  - Sonuç: temiz
- `cd frontend && npm run build`
  - Sonuç: başarılı
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti; frontend lint temiz, frontend test `237 passed`, backend pytest `256 passed, 2 skipped`, frontend build başarılı

### Kalan riskler / blokajlar

- Degraded proje listesi şu an local cache tabanlı; farklı cihaz/sekme senaryolarında merkezi bir sync katmanı yok.
- Backend pytest sırasında görülen iki `Swig*` deprecation warning üçüncü taraf binding kaynaklı ve bu checkpoint’i bloke etmiyor.

### Sonraki net adım

- `GTS-A09` kapandı; `/api/projects` hata anında UI artık sağlıklı boş durum üretmiyor.
- Sıradaki backlog odağı `GTS-A10`: coverage görünürlüğü ve threshold governance.

## 9) GTS-A10 coverage governance checkpoint

### Bu adımda tamamlanan işler

- Backend için `pytest-cov`, frontend için Vitest coverage eşiği tanımlandı; `scripts/check_coverage.sh` ile iki taraflı coverage kapısı tek komutta çalışır hale getirildi.
- `.github/workflows/verify.yml` artık backend/frontend bağımlılıklarını kuruyor, `verify` kapısından sonra coverage kapısını da çalıştırıyor ve backend/frontend coverage artifact'larını yüklüyor.
- Coverage çıktılarının lint yüzeyine sızmaması için `frontend/eslint.config.js` içinde `build`, `coverage` ve `dist` klasörleri global ignore listesine alındı; böylece coverage sonrası lint temiz kalıyor.

### Çalıştırılan doğrulamalar

- `bash scripts/check_coverage.sh`
  - Sonuç: backend coverage `73.48%`, frontend coverage `statements 78.1 / branches 69.15 / functions 79.8 / lines 78.47`
- `cd frontend && npm run lint`
  - Sonuç: coverage çıktı klasörleri varken de temiz
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti

### Kalan riskler / blokajlar

- Coverage governance artık görünür ve threshold'lu, fakat düşük coverage adaları hâlâ özellikle `backend/api/routes/editor.py`, `backend/core/workflow_helpers.py` ve bazı büyük frontend controller dosyalarında yoğunlaşıyor.
- Backend coverage koşusunda görülen `Swig*` ve bazı `ResourceWarning` kayıtları üçüncü taraf binding/test fixture kaynaklı; bu checkpoint'i bloke etmiyor ama ayrı temizlik adayı.

### Sonraki net adım

- `GTS-A10` kapandı; coverage görünürlüğü ve eşikleri artık repo + CI seviyesinde aktif.
- Sıradaki backlog odağı `GTS-A11` frontend onboarding dokümantasyonu ve `GTS-A12` run.sh taşınabilirliği.

## 10) GTS-A11 frontend README checkpoint

### Bu adımda tamamlanan işler

- `frontend/README.md` şablon içeriğinden çıkarılıp gerçek proje rehberine dönüştürüldü; komutlar, env alanları, feature yüzeyleri, dizin rehberi ve test stratejisi tek dokümanda toplandı.
- Frontend dokümanı parity fixture'ları, büyük feature klasörleri ve repo kök doğrulama komutlarıyla ilişkilendirildi; onboarding için doğrudan kullanılabilir hale geldi.

### Çalıştırılan doğrulamalar

- `python scripts/check_markdown_links.py docs README.md frontend/README.md scripts/README.md`
  - Sonuç: `Markdown links ok: 51 files checked`

### Kalan riskler / blokajlar

- README artık proje özel, ancak ileride yeni feature eklenirse dizin rehberi ve env listesi aynı turda güncel tutulmalı.

### Sonraki net adım

- `GTS-A11` kapandı.
- Hemen ardından `GTS-A12` için `run.sh` portability kontrolü uygulanacak.

## 11) GTS-A12 run.sh portability checkpoint

### Bu adımda tamamlanan işler

- `run.sh` artık Conda'yı zorunlu varsaymıyor; sırasıyla mevcut aktif env, `APP_ENV_NAME` ile verilen Conda env'i, proje kökündeki `.venv`, proje kökündeki `venv` ve son olarak sistem `python`/`npm` yolunu deniyor.
- `SKIP_ENV_ACTIVATION=1` ile otomatik env aktivasyonu tamamen kapatılabilir hale geldi; ayrıca aktif `base` Conda ortamı yanlışlıkla hedef env sayılmayacak şekilde özel-case düzeltildi.
- Root README ve `scripts/README.md` bu yeni davranışı, polling fallback ve doğrulama komutlarıyla birlikte açıklayacak şekilde güncellendi.

### Çalıştırılan doğrulamalar

- `bash -n run.sh`
  - Sonuç: temiz
- `timeout 35 ./run.sh`
  - Sonuç: backend ve frontend başarıyla ayağa kalktı; startup smoke temiz

### Kalan riskler / blokajlar

- `run.sh` hâlâ yerel geliştirme kolaylığı için tasarlanmış bir orchestrator script; production service manager yerine geçmiyor.
- Startup smoke mevcut makinedeki toolchain ile doğrulandı; farklı hostlarda yine `python` ve `npm` komutlarının PATH'te bulunması gerekiyor.

### Sonraki net adım

- `GTS-A12` kapandı.
- Repo içindeki sıradaki güvenlik backlog odağı `GTS-A03` env-wide Postiz fallback hardening.

## 12) GTS-A03 social credential hardening checkpoint

### Bu adımda tamamlanan işler

- `backend/services/social/crypto.py` ve `backend/services/social/service.py` içinde `POSTIZ_API_KEY` env fallback varsayılan olarak kapatıldı; artık yalnız explicit `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1` ile açılabiliyor.
- Startup güvenlik doğrulaması bu fallback'i opt-in olmayan konfigürasyonlarda fail-fast edecek şekilde sıkılaştırıldı; `backend/runtime_validation.py` de yeni boolean env alanını tanıyor.
- `docs/api-key-setup.md`, `README.md` ve `docs/operations/fresh-install-checklist.md` tek kullanıcılı dev fallback ile çok kullanıcılı subject-bazlı credential akışı arasındaki ayrımı netleştirecek şekilde güncellendi.

### Çalıştırılan doğrulamalar

- `pytest backend/tests/test_social_crypto.py backend/tests/test_runtime_validation.py backend/tests/test_social_routes.py -q`
  - Sonuç: `31 passed`
- `python scripts/check_markdown_links.py docs README.md frontend/README.md scripts/README.md`
  - Sonuç: `Markdown links ok: 51 files checked`
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti; frontend test `237 passed`, backend pytest `260 passed, 2 skipped`, frontend build başarılı

### Kalan riskler / blokajlar

- Subject-bazlı social credential modeli güçlendi, ancak sibling `postiz-docker-compose` repo tarafındaki düz metin secret ve ağ yüzeyi (`GTS-A01`) ayrı operasyonel çalışma gerektiriyor.
- `POSTIZ_API_KEY` env fallback artık yalnız dev opt-in olduğu için çok kullanıcılı paylaşımlı ortamlarda yanlış konfigürasyon daha erken fail edecek; deploy rehberleri buna göre güncel tutulmalı.

### Sonraki net adım

- `GTS-A03` kapandı.
- Repo içinde kalan ana açık backlog artık `GTS-A01` dış compose yüzeyi ve `GTS-A02` upload hard-limit/proxy katmanı.

## 13) GTS-A02 upload hard-limit guardrail checkpoint

### Bu adımda tamamlanan işler

- `backend/tests/integration/test_api_upload_limits.py` eklendi; `/api/upload` ve `/api/manual-cut-upload` yollarında `Content-Length` üstünden erken `413 REQUEST_TOO_LARGE` cevabı artık entegrasyon testiyle sabitlendi.
- Mevcut `stream_upload_to_path` ve `prepare_uploaded_project` testleriyle birlikte repo içindeki upload yolu için iki katmanlı koruma kaydı netleşti: middleware seviyesinde erken ret, stream seviyesinde chunk bazlı hard-limit ve tek geçişte hash/yazma.
- Böylece denetimde listelenen repo içi kanıt drift'i temizlendi; kalan risk daha çok reverse proxy/ingress hard-limit ayarının deploy katmanında aynı sınırla hizalanması.

### Çalıştırılan doğrulamalar

- `pytest backend/tests/integration/test_api_upload_limits.py backend/tests/unit/test_upload_validation.py backend/tests/unit/test_upload_prepare_project.py -q`
  - Sonuç: `10 passed`
- `python -m py_compile backend/api/server.py backend/api/routes/clips.py backend/api/routes/editor.py backend/tests/integration/test_api_upload_limits.py`
  - Sonuç: temiz
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti; frontend test `237 passed`, backend pytest `262 passed, 2 skipped`, frontend build başarılı

### Kalan riskler / blokajlar

- Uygulama içi guardrail artık testli, ancak reverse proxy veya ingress tarafında eşleşen body-limit ayarı repo dışında yönetiliyor.
- Upload akışı hâlâ geçici dosya + `ffprobe` doğrulaması kullanıyor; bu güvenlik kapısını bozmasa da I/O optimizasyonu için ileride ayrı refactor alanı olabilir.

### Sonraki net adım

- `GTS-A02` repo içi guardrail seviyesiyle büyük ölçüde güvence altına alındı; dış deploy/proxy ayağı ayrıca operasyonel takip gerektiriyor.
- Kalan ana açık teknik denetim odağı artık sibling compose yüzeyi olan `GTS-A01`.

## 14) GTS-A01 external compose audit checkpoint

### Bu adımda tamamlanan işler

- `/home/arch/postiz-docker-compose` sibling repo'su tekrar incelendi; üretim benzeri `docker-compose.yaml` ve eski `docker-compose.dev.yaml` üzerindeki secret/network yüzeyi güncel haliyle doğrulandı.
- İnceleme sırasında dış repo'nun kirli worktree taşıdığı görüldü: `docker-compose.yaml` kullanıcı tarafından değiştirilmiş, `.env` ise untracked. Bu nedenle kullanıcı değişikliklerinin üstüne basmamak için otomatik remediation patch'i uygulanmadı.
- Güncel riskler netleşti: düz metin `JWT_SECRET`, Postgres parolaları, gerçek YouTube OAuth credential'ı, host'a açık portlar ve debug/dev servislerinin gereğinden geniş yayınlanması.

### Çalıştırılan doğrulamalar

- `git -C /home/arch/postiz-docker-compose status --short`
  - Sonuç: `docker-compose.yaml` modified, `.env` untracked
- `git -C /home/arch/postiz-docker-compose diff -- docker-compose.yaml`
  - Sonuç: public URL/image parametrizasyonu ve command override eklenmiş; secret/network sertleştirmesi hâlâ yapılmamış
- `nl -ba /home/arch/postiz-docker-compose/docker-compose.yaml | sed -n '1,220p'`
  - Sonuç: düz metin secret ve host port yayınları doğrulandı
- `nl -ba /home/arch/postiz-docker-compose/docker-compose.dev.yaml | sed -n '1,220p'`
  - Sonuç: eski dev stack içinde DB/Redis/pgAdmin/Temporal/RedisInsight portları ve varsayılan credential'lar doğrulandı

### Kalan riskler / blokajlar

- `docker-compose.yaml` içinde düz metin secret yüzeyi sürüyor:
  - `JWT_SECRET`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `POSTGRES_PWD`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`
- Host'a açık servis yüzeyi sürüyor:
  - `4007`, `8969`, `7233`, `8080`
- Eski `docker-compose.dev.yaml` daha da geniş açılıyor:
  - `5432`, `6379`, `8081`, `5540`, `7233`, `8080`
- Dış repo kirli olduğu için kontrollü patch ayrı branch/commit disipliniyle yapılmalı; aksi halde kullanıcı değişikliği üzerine yazma riski var.

### Sonraki net adım

- Sibling repo içinde ayrı çalışma aç:
  - Secret'ları `.env`/secret mount'a taşı, `:?required` sözleşmesi koy
  - Gerçek YouTube credential'ı compose'tan çıkar ve rotasyon yap
  - `ports:` yayınlarını `127.0.0.1:` ile sınırla veya tamamen internal `expose` modeline çek
  - `docker-compose.dev.yaml` için açık debug servislerini profil/opsiyonel hale getir
- Bu adım current repo içinde değil, `/home/arch/postiz-docker-compose` tarafında kontrollü remediation gerektiriyor.

## 15) GTS-A01 secure overlay checkpoint

### Bu adımda tamamlanan işler

- Kirli worktree içindeki mevcut `docker-compose.yaml` dosyasını doğrudan bozmamak için sibling repo'ya additive güvenlik overlay'i eklendi: `docker-compose.secure.yaml`.
- Secret externalization ve port daraltma için örnek env sözleşmesi `/.env.secure.example` altında oluşturuldu; kullanım akışı `HARDENING.md` içinde dokümante edildi.
- Overlay şu güvenli farkları getiriyor:
  - `JWT_SECRET`, Postiz DB password ve Temporal DB password artık compose literal'i yerine env dosyasından okunuyor
  - `YOUTUBE_CLIENT_ID` ve `YOUTUBE_CLIENT_SECRET` overlay altında varsayılan boş değere çekiliyor
  - `postiz`, `spotlight`, `temporal` ve `temporal-ui` portları `127.0.0.1` bind ile override ediliyor

### Çalıştırılan doğrulamalar

- `docker compose --env-file .env --env-file .env.secure.example -f docker-compose.yaml -f docker-compose.secure.yaml config`
  - Sonuç: render başarılı
- Render çıktısında doğrulanan kritik sonuçlar:
  - `JWT_SECRET` compose literal yerine env placeholder değerinden geliyor
  - `YOUTUBE_CLIENT_ID` ve `YOUTUBE_CLIENT_SECRET` boş render oluyor
  - yayınlanan portlar yalnız `host_ip: 127.0.0.1` ile görünüyor

### Kalan riskler / blokajlar

- Bu adım henüz canlı stack'i değiştirmedi; yalnız güvenli overlay ve env sözleşmesini hazırladı.
- Gerçek geçişte `JWT_SECRET` ve DB credential rotasyonu veri ve oturum etkisi doğurabileceği için mevcut değerler bilinçli migration ile `.env.secure` içine taşınmalı.

### Sonraki net adım

- `/home/arch/postiz-docker-compose/.env.secure` dosyasını üret.
- Ardından `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml up -d` ile kontrollü smoke başlat ve health/log doğrulaması yap.

## 16) Social account isolation checkpoint

### Bu adımda tamamlanan işler

- Postiz publish hedefleri artık sunucuda da kullanıcı bazında doğrulanıyor; istek içindeki `account_id` yalnız o an bağlı kullanıcının Postiz integration listesinde varsa kabul ediliyor.
- `backend/services/social/service.py` içinde subject-scope account çözümleme ve target validation helper'ları eklendi; `backend/api/routes/social.py` publish ve dry-run akışları bu guardrail ile bağlandı.
- `frontend/src/components/shareComposer/helpers.ts` içindeki local draft buffer anahtarı auth identity ile scope edildi. Böylece aynı tarayıcıda kullanıcı değişirse paylaşım taslakları kullanıcılar arasında görünmüyor.
- Backend ve frontend test yüzeyine yeni izolasyon kanıtları eklendi; cross-user Postiz account görünürlüğü ve foreign target publish denemesi artık testle korunuyor.

### Çalıştırılan doğrulamalar

- `pytest backend/tests/test_social_routes.py -q`
  - Sonuç: `13 passed`
- `pytest backend/tests/test_social_crypto.py backend/tests/test_account_deletion_api.py backend/tests/test_subject_purge.py -q`
  - Sonuç: `11 passed`
- `python -m py_compile backend/services/social/service.py backend/api/routes/social.py backend/tests/test_social_routes.py`
  - Sonuç: temiz
- `cd frontend && npm run test -- src/test/App.test.tsx src/test/components/shareComposer.helpers.test.ts src/test/components/ShareComposerModal.connection.test.tsx src/test/components/ShareComposerModal.publish.test.tsx src/test/components/ShareComposerModal.drafts.test.tsx --reporter=dot`
  - Sonuç: `16 passed`
- `cd frontend && npx eslint src/components/shareComposer/helpers.ts src/components/shareComposer/useShareComposerController.ts src/test/components/shareComposer.helpers.test.ts src/test/App.test.tsx`
  - Sonuç: temiz
- `bash scripts/verify.sh`
  - Sonuç: tamamı geçti; frontend test `237 passed`, backend pytest `263 passed, 2 skipped`, frontend build başarılı

### Kalan riskler / blokajlar

- Uygulama içi Postiz izolasyonu artık daha sıkı, ancak sibling Postiz compose yüzeyindeki gerçek secret/network sertleştirmesi hâlâ dış repo işi olarak açık duruyor.
- Kullanıcıların kendi Postiz tenant/workspace yaşam döngüsü uygulama içinde izole, fakat Postiz tarafında yanlış paylaşılan ortak admin credential kullanılırsa dış sistem politikası yine risk üretir.

### Sonraki net adım

- Repo içi sosyal izolasyon guardrail'i yeşile döndü; dış operasyonel odak yine `GTS-A01`.
- Sibling compose repo'da `.env.secure` üretip kontrollü `up -d` smoke adımına geçmek en mantıklı sıradaki hareket.

## 17) GTS-A01 secure rollout checkpoint

### Bu adımda tamamlanan işler

- Sibling `/home/arch/postiz-docker-compose` repo içinde gerçek `.env.secure` dosyası üretildi; ilk rollout veri kaybısız olsun diye mevcut çalışan JWT/DB/OAuth değerleri compose literal'larından aynen taşındı.
- Yanlışlıkla secret commitlenmemesi için sibling repo'ya dar kapsamlı `.gitignore` eklendi ve `HARDENING.md` mevcut değerlerle ilk migration, ayrı secret rotation yaklaşımını anlatacak şekilde netleştirildi.
- `docker-compose.secure.yaml` içindeki `spotlight` servisine `pull_policy: missing` eklendi; böylece mevcut local image varken gereksiz registry bekleyişi rollout'u bloklamıyor.
- Overlay ile `up -d` rollout tamamlandı; `postiz`, `spotlight`, `temporal` ve `temporal-ui` servisleri artık `127.0.0.1` bind ile ayağa kalkıyor.

### Çalıştırılan doğrulamalar

- `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml config`
  - Sonuç: render temiz; `JWT_SECRET` ve YouTube OAuth env'den geliyor, tüm publish portları `127.0.0.1`
- `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml up -d`
  - Sonuç: rollout tamamlandı
- `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml ps`
  - Sonuç: `postiz`, `spotlight`, `temporal`, `temporal-ui` up
- `ss -ltn '( sport = :4007 or sport = :8969 or sport = :7233 or sport = :8080 )'`
  - Sonuç: yalnız `127.0.0.1:4007/8969/7233/8080` listen ediyor
- `curl -I --max-time 10 http://127.0.0.1:4007`
  - Sonuç: `HTTP/1.1 307 Temporary Redirect` ve `location: /auth`
- `docker compose ... logs --tail=60 postiz`
  - Sonuç: Postiz backend `Nest application successfully started`

### Kalan riskler / blokajlar

- Secret externalization tamamlandı ama rotasyon tamamlanmadı; `.env.secure` ilk rollout için mevcut çalışan değerleri taşıyor.
- YouTube OAuth credential artık compose literal'ında değil; fakat aynı değerler `.env.secure` içinde duruyor. Gerçek risk kapanışı için rotation + yeni app credential planı gerekiyor.
- `spotlight` sağlık sinyali geldi, ancak dış erişim kapandığı için uzak cihazlardan erişecek operasyon ekibi varsa erişim deseni ayrıca planlanmalı.

### Sonraki net adım

- `GTS-A01` için son operasyonel kapanış adımı secret rotation:
- yeni `POSTIZ_JWT_SECRET`
- yeni DB password'leri
- yeni veya kontrollü yönetilen YouTube OAuth app credential'ı
- Rotation sonrası ikinci bir kısa `up -d` smoke ve login/social connect akışı doğrulanmalı.

## 18) GTS-A01 secret rotation checkpoint

### Bu adımda tamamlanan işler

- Sibling Postiz stack için yerelde yönetilebilir secret'lar gerçekten döndürüldü:
  - `POSTIZ_JWT_SECRET`
  - Postiz Postgres kullanıcı parolası
  - Temporal Postgres kullanıcı parolası
- Yeni değerler `/home/arch/postiz-docker-compose/.env.secure` içine yazıldı.
- Her iki veritabanında ilgili roller `ALTER ROLE ... PASSWORD` ile canlıda güncellendi.
- Ardından secure overlay ile kontrollü restart yapıldı; Postiz/Temporal yeni secret'larla tekrar ayağa kalktı.

### Çalıştırılan doğrulamalar

- `docker exec postiz-postgres ... ALTER ROLE "postiz-user" ...`
  - Sonuç: `ALTER ROLE`
- `docker exec temporal-postgresql ... ALTER ROLE temporal ...`
  - Sonuç: `ALTER ROLE`
- `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml up -d`
  - Sonuç: restart tamamlandı
- `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml ps`
  - Sonuç: `postiz`, `postiz-postgres`, `temporal`, `temporal-postgresql`, `spotlight`, `temporal-ui` up
- `docker run --rm --network postiz-docker-compose_postiz-network -e PGPASSWORD=<new> postgres:17-alpine psql ...`
  - Sonuç: yeni Postiz DB parolasıyla bağlantı başarılı
- `docker run --rm --network postiz-docker-compose_postiz-network -e PGPASSWORD=<old> postgres:17-alpine psql ...`
  - Sonuç: eski Postiz DB parolası reddedildi
- `docker run --rm --network temporal-network -e PGPASSWORD=<new> postgres:16 psql ...`
  - Sonuç: yeni Temporal DB parolasıyla bağlantı başarılı
- `docker run --rm --network temporal-network -e PGPASSWORD=<old> postgres:16 psql ...`
  - Sonuç: eski Temporal DB parolası reddedildi
- `curl -I --max-time 10 http://127.0.0.1:4007`
  - Sonuç: `HTTP/1.1 307 Temporary Redirect`, `location: /auth`
- `docker compose ... logs --tail=80 postiz`
  - Sonuç: `Nest application successfully started`

### Kalan riskler / blokajlar

- Yerel olarak döndürülemeyen son parça YouTube OAuth app credential rotation; bunun için Google/harici sağlayıcı tarafında yeni client üretimi gerekiyor.
- JWT rotation doğal olarak mevcut Postiz oturumlarını düşürmüş olabilir; bu beklenen bir sonuç.

### Sonraki net adım

- `GTS-A01` için kalan son manuel iş: yeni YouTube OAuth app credential üret ve `/home/arch/postiz-docker-compose/.env.secure` içine taşı.
- Sonrasında kısa bir `up -d` smoke ve gerçek social connect akışı kontrolü yeterli olacak.

## 19) GTS-A01 OAuth smoke checkpoint

### Bu adımda tamamlanan işler

- Canlı browser smoke ile Postiz Google OAuth giriş akışı doğrulandı.
- İlk denemede `http://127.0.0.1:4007/auth` üzerinden açılan sayfanın OAuth isteğini `http://localhost:4007/api/auth/oauth/GOOGLE` adresine attığı ve host farkı nedeniyle CORS'a düştüğü kanıtlandı.
- Aynı akış `http://localhost:4007/auth` üzerinden tekrarlandığında Google kimlik doğrulama ekranına başarılı yönlendirme alındı.
- Böylece YouTube/Google OAuth env wiring'in çalıştığı, fakat operasyonel erişim notu olarak Postiz UI'nin `localhost` host adıyla kullanılmasının gerektiği netleştirildi.

### Çalıştırılan doğrulamalar

- Playwright smoke: `http://127.0.0.1:4007/auth` -> `Google`
  - Sonuç: frontend `http://localhost:4007/api/auth/oauth/GOOGLE` isteğinde CORS/fetch error
- Playwright smoke: `http://localhost:4007/auth` -> `Google`
  - Sonuç: `https://accounts.google.com/...redirect_uri=http://localhost:4007/integrations/social/youtube...` adresine başarılı yönlendirme
- Görsel kanıt:
  - Sonuç: Google sayfasında `Oturum açın` ekranı açıldı, client id ve redirect URI akışta mevcut

### Kalan riskler / blokajlar

- Bu smoke yalnız OAuth başlangıç yönlendirmesini doğruluyor; gerçek bağlama tamamlanması için kullanıcı hesabıyla Google consent adımı manuel kalıyor.
- `127.0.0.1` ile erişim kullanıcı tarafında yanıltıcı hata üretebilir; operasyon notlarında `localhost` kullanımı net yazılmalı.
- Son açık operasyonel borç hâlâ YouTube OAuth app credential rotation; mevcut env wiring çalışıyor ama credential'ın harici sağlayıcı tarafında gerçekten yenilenip yenilenmediği bu adımda döngüsel olarak kanıtlanmadı.

### Sonraki net adım

- `HARDENING.md` ve operasyon runbook'una `localhost` erişim notunu ekle.
- Google tarafında yeni OAuth app gerekiyorsa rotate et, ardından aynı smoke'u tekrar çalıştır.
- Son kullanıcı hesabıyla tek bir kontrollü social connect denemesi yapıp bağlantı ekranını tamamla.

## 20) GTS-A01 manuel multi-account validation checkpoint

### Bu adımda tamamlanan işler

- Kullanıcı tarafından canlı ortamda iki farklı hesapla Postiz bağlantı akışı manuel doğrulandı.
- Her kullanıcı kendi oturum alanında yalnız kendi bağlı hesabını gördü.
- Böylece daha önce eklenen subject-scope hesap izolasyonu ile dış Postiz OAuth akışının birlikte doğru çalıştığı operasyonel olarak doğrulanmış oldu.

### Çalıştırılan doğrulamalar

- Manuel kullanıcı doğrulaması: birinci hesapla giriş + Google/Postiz bağlantı kontrolü
  - Sonuç: kullanıcı kendi hesabını kendi alanında görüyor
- Manuel kullanıcı doğrulaması: ikinci hesapla giriş + Google/Postiz bağlantı kontrolü
  - Sonuç: ikinci kullanıcı yalnız kendi hesabını görüyor; hesaplar birbirine sızmıyor

### Kalan riskler / blokajlar

- OAuth client'ın Google tarafında ayrıca rotate edilip edilmediği bu adımın kapsamı dışında; mevcut credential setiyle akışın doğru çalıştığı kanıtlandı.
- `localhost` kullanım notu operasyon açısından korunmalı; `127.0.0.1` üzerinden açılış yine yanıltıcı CORS hatası üretebilir.

### Sonraki net adım

- `GTS-A01` maddesini repo içi kabul kriterleri açısından kapalı işaretle.
- İleride ihtiyaç olursa yalnız harici sağlayıcı tarafında planlı OAuth client rotation yapılır.

## 21) GTS-A01 managed connection-mode checkpoint

### Bu adımda tamamlanan işler

- Uygulama tarafına `SOCIAL_CONNECTION_MODE` sözleşmesi eklendi; `managed` ve `manual_api_key` modları runtime validation ile doğrulanıyor.
- Backend `GET /api/social/accounts` yanıtı artık `connection_mode` dönüyor; `managed` modda manuel `POST /api/social/credentials` isteği `403` ile reddediliyor.
- Frontend `ShareComposer` bağlantı kartı `managed` modda Postiz API key alanını göstermiyor; bunun yerine yönetilen bağlantı açıklaması ve `Hesapları Yenile` akışı gösteriliyor.
- Yerel çalışma ortamı ve `.env.example` `SOCIAL_CONNECTION_MODE=managed` ile hizalandı; README ve kurulum rehberleri yeni sözleşmeye göre güncellendi.

### Çalıştırılan doğrulamalar

- `pytest backend/tests/test_runtime_validation.py backend/tests/test_social_routes.py -q`
  - Sonuç: `28 passed`
- `cd frontend && npm run test -- src/test/components/ShareComposerModal.connection.test.tsx --reporter=dot`
  - Sonuç: `2 passed`
- `cd frontend && npx eslint src/components/shareComposer/sections.tsx src/components/shareComposer/useShareComposerController.ts src/test/components/ShareComposerModal.connection.test.tsx src/test/components/shareComposer.test-helpers.tsx src/api/client.ts src/types/index.ts`
  - Sonuç: temiz
- `python scripts/check_markdown_links.py README.md docs/api-key-setup.md docs/operations/fresh-install-checklist.md docs/operations/postiz-global-oauth-standard.md`
  - Sonuç: `Markdown links ok: 4 files checked`

### Kalan riskler / blokajlar

- Bu checkpoint ürün yüzeyini `managed` moda hazırlıyor; tam sıfır kullanıcı müdahalesi için halen gerçek subject-bazlı OAuth callback/storage akışının uygulama içine taşınması gerekiyor.
- Şu an `managed` modda kullanıcıyı API key istemeden yönlendiriyoruz, ama gerçek otomatik bağlama henüz yok; bu nedenle bu dilim bir UX/guardrail sertleştirmesi olarak değerlendirilmeli.

### Sonraki net adım

- `ShareComposer` için gerçek `oauth/start` ve `oauth/callback` akışını tasarla.
- Subject bazlı Postiz credential üretimini API key formundan çıkarıp callback tabanlı hale getir.
- Sonrasında `managed` modda uçtan uca publish smoke testi ekle.
