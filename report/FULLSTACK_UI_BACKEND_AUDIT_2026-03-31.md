# Full-Stack UI-Backend Audit Report

- Tarih: `2026-03-31`
- Repo: `godtier-shorts`
- Kapsam: `frontend/`, `marketing/`, backend API yuzeyleri, ilgili testler, ilgili dokumantasyon referanslari
- Bu fazin kural seti: Kaynak kod ve kaynak dokumantasyon degistirilmedi; yalnizca `report/` altinda audit ciktilari uretildi.

## Executive Summary

Genel sonuc `partial / blocked` seviyesindedir. Auth, temel job kontrolleri, upload, transcript save/recover, social discovery ve account purge canli ortamda calisti. Buna karsilik clip uretim zinciri, marketing build sagligi ve social scheduler testleri kabul seviyesinde degil.

En kritik runtime sorunu `POST /api/process-manual` kabul edildikten sonra background worker'in `float(NoneType)` exception ile dusmesi ve job'un terminal state almamasidir. Buna ek olarak `POST /api/manual-cut-upload` optimistic basari verisi donup ileride error ile sonlaniyor, `POST /api/process-batch` ise makul surede terminale ulasmiyor. Bu uc sorun cozulmeden clip tabanli editor, reburn, social prefill/publish ve clip delete akislari tam olarak dogrulanamaz.

## Scope ve Yontem

Audit su adimlarla yurutuldu:

1. Ortam baseline dogrulamasi alindi.
2. Frontend, marketing ve backend otomasyon paketleri calistirildi.
3. Canli API snapshot/export kayitlari alindi.
4. Dosya bazli statik analiz yapildi.
5. UI -> API -> backend route -> auth policy -> test -> docs esleme matrisi uretildi.
6. Canli upload, transcript, editor, social ve destructive akislar izlenerek kanit kayitlari toplandi.
7. Bulgular risk kaydina, kontrat matrisine ve bu rapora indirgendi.

## Ortam Baseline

- Auth mode: `static_token`
- Roles: `admin`, `editor`, `operator`, `producer`, `uploader`, `viewer`
- Subject hash: `3462292b60860538b5a07d5d89e1eb94`
- Sistem bagimliliklari:
  - `ffmpeg`: pass
  - `yt-dlp`: pass
  - `nvidia-smi`: pass
  - `torch.cuda`: warning
- WebSocket handshake: pass

Detay: `report/fullstack-ui-backend-audit-2026-03-31/environment_baseline.json`

## Kapsam Ozet Sayilari

- Dosya bazli envanter: `263` dosya
- Katman dagilimi:
  - backend: `8`
  - frontend: `83`
  - backend_test: `70`
  - frontend_test: `59`
  - marketing: `27`
  - docs: `16`
- API kontrat matrisi: `41` public surface
- Live status dagilimi:
  - pass: `23`
  - fail: `4`
  - warn: `1`
  - blocked: `11`
  - not_tested: `2`
- Risk kaydi: `9` risk
  - critical: `1`
  - high: `4`
  - medium: `3`
  - low: `1`

Detay:

- `report/fullstack-ui-backend-audit-2026-03-31/file_inventory.csv`
- `report/fullstack-ui-backend-audit-2026-03-31/endpoint_contract_matrix.csv`
- `report/fullstack-ui-backend-audit-2026-03-31/ui_backend_matrix.json`
- `report/fullstack-ui-backend-audit-2026-03-31/risk_register.json`

## En Kritik Bulgular

### 1. Critical: `process-manual` kabul edildikten sonra background crash

- Etki: Clip editor ve subtitle editor akisi gercekte tamamlanamiyor; job terminal state almadan asili kaliyor.
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_request_evidence_extended.json`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/runtime/backend_stderr.log`
- Teknik bulgu:
  - `backend/core/subtitle_timing.py` icinde `float(word.get("score", 1.0))`
  - `score=None` geldigi durumda `TypeError`
- Etkilenen dosyalar:
  - `backend/api/routes/editor.py`
  - `backend/core/subtitle_timing.py`
  - `frontend/src/components/editor/useEditorController.ts`
  - `frontend/src/components/subtitleEditor/actions.ts`
- Sonuc: `POST /api/process-manual` live status `fail`

### 2. High: `manual-cut-upload` optimistic basari, terminalde error

- Etki: UI 200 response ile clip/output bilgisi aliyor; gercekte job 45% seviyesinde error ile bitiyor.
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/manual_cut_upload_scenario.json`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/runtime/backend_stderr.log`
- Sonuc: Auto Cut happy path kabul edilemez.

### 3. High: `process-batch` 30% seviyesinde hanging

- Etki: Batch clip uretimi makul surede terminale ulasmiyor; downstream clip bagimli dogrulamalar bloklu kaliyor.
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_request_evidence_extended.json`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/runtime/backend_stderr.log`
- Gozlem:
  - Job `AI 1 adet viral an buldu, kurgu basliyor...` mesajinda kaldi.
  - Runtime log icinde `OPENROUTER_API_KEY` eksigi fallback davranisini etkiliyor.

### 4. High: Marketing compare route build ve runtime seviyesinde kirik

- Etki: Marketing paketi release gate'inden gecemiyor; ilgili route canlida `500` donuyor.
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/tests/marketing_build.log`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/ui/http_route_checks.json`
- Teknik bulgu:
  - `marketing/src/app/compare/opus-clip-alternative/page.tsx`
  - `Cannot find name 'Link'`

### 5. High: Social scheduler testleri timezone bagimliligi nedeniyle kirik

- Etki: Publish/calendar davranisi Windows ortaminda guvenilir degil.
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/tests/backend_target_suite.log`
- Gozlem:
  - `93` hedef backend testinin `89` adedi gecti, `4` adedi fail
  - Tum failure'lar `Gecersiz timezone` / IANA timezone cozumlemesi ekseninde toplaniyor
- Teknik odak:
  - `backend/api/routes/social.py`
  - Windows `tzdata` / `ZoneInfo()` davranisi

## Feature Verdict

| Alan | Verdict | Ozet |
| --- | --- | --- |
| Auth & App Shell | Pass with warning | Auth bootstrap ve WebSocket connect/reconnect dogrulandi; lint seviyesinde hook dependency warning var. |
| Configure / Jobs | Pass | `cache-status`, `start-job`, `list`, `cancel`, `styles` canli olarak dogrulandi. |
| Upload & Transcript | Pass with warning | Upload ve transcript save/recover calisti; upload sonrasi ilk `GET /api/projects` okumada eventual consistency goruldu. |
| Auto Cut / Manual Cut | Fail | `manual-cut-upload` terminal error verdi, `process-batch` hanging kaldi. |
| Clip Editor | Fail | `process-manual` background crash nedeniyle clip olusmadi. |
| Subtitle Editor | Partial | Project transcript save/recover gecti; clip transcript recovery clip yoklugu nedeniyle bloklu. |
| Social Workspace & Compose | Partial | Discovery/list/analytics gecti; publish/prefill/approve/cancel akislari clip ve timezone blokajlari nedeniyle tamamlanamadi. |
| Account Deletion | Pass | Subject scoped purge iki kez canli dogrulandi ve veri temizligi saglandi. |
| Marketing | Fail | Build kapiyor ve bir route canlida 500 donuyor. |

## Otomasyon Sonuclari

| Paket | Sonuc | Ozet |
| --- | --- | --- |
| Backend runtime config | Pass | Runtime config dogrulandi. |
| System deps | Pass with warning | `torch.cuda` warning disinda temel bagimliliklar OK. |
| Frontend lint | Warn | `0` error, `44` warning. |
| Frontend build | Pass | Production build tamamlandi. |
| Marketing build | Fail | Eksik `Link` importu. |
| Target backend pytest suite | Fail | `93` testten `89` pass, `4` fail. |
| Frontend smoke | Pass | `1/1` gecti. |
| Frontend feature suites | Fail | `45` testten `37` pass, `8` fail; stale label beklentileri. |
| Frontend integration suites | Fail | `2` testten `1` pass, `1` fail; label drift. |
| Full frontend suite | Timeout | `20` dakika gate asildi. |

Detay: `report/fullstack-ui-backend-audit-2026-03-31/test_execution_log.csv`

## Canli API ve UI Dogrulama Ozetleri

### Gecen Akislar

- `GET /api/auth/whoami`
- `GET /api/projects`
- `GET /api/clips`
- `GET /api/social/providers`
- `GET /api/social/accounts`
- `GET /api/social/connections`
- `GET /api/social/publish-jobs`
- `GET /api/social/queue`
- `GET /api/social/calendar`
- `POST /api/cache-status`
- `POST /api/start-job`
- `POST /api/cancel-job/{job_id}`
- `POST /api/upload`
- `GET /api/transcript`
- `POST /api/transcript`
- `POST /api/transcript/recover`
- Social discovery ve analytics endpointleri
- `DELETE /api/account/me/data`

### Fail / Warn / Blocked Akislar

- `POST /api/process-manual`: fail
- `POST /api/manual-cut-upload`: fail
- `POST /api/process-batch`: fail
- `PATCH /api/social/calendar/{job_id}`: fail in automated suite
- `GET /api/clip-transcript/{clip_name}`: blocked
- `POST /api/clip-transcript/recover`: blocked
- `POST /api/reburn`: blocked
- `DELETE /api/projects/{project_id}/shorts/{clip_name}`: blocked
- `GET /api/social/prefill`: blocked
- `PUT /api/social/drafts`: blocked
- `DELETE /api/social/drafts`: blocked
- `POST /api/social/publish`: blocked
- `POST /api/social/publish-jobs/{job_id}/approve`: blocked
- `POST /api/social/publish-jobs/{job_id}/cancel`: blocked
- `POST /api/social/credentials`: not tested
- `DELETE /api/social/credentials`: not tested

Detay: `report/fullstack-ui-backend-audit-2026-03-31/live_request_evidence.json`

## Statik Analiz Ozetleri

Dosya bazli analiz her dosya icin su alanlari cikardi:

- amac ve sorumluluk
- bagimliliklar
- baglandigi endpointler
- ilgili testler
- ilgili dokumantasyon
- risk seviyesi

One cikan statik riskler:

- `frontend/src/hooks/useWebSocket.ts`: lint seviyesinde dependency warning
- `frontend/src/components/SocialWorkspace.tsx`: complexity ve memo dependency warning'lari
- `backend/api/routes/editor.py`: clip uretim zincirinin birden fazla failure noktasini ayni route katmaninda topluyor
- `backend/api/routes/social.py`: timezone/ZoneInfo davranisi runtime bagimliligina hassas
- `marketing/src/app/compare/opus-clip-alternative/page.tsx`: build kirici missing import

Detay:

- `report/fullstack-ui-backend-audit-2026-03-31/file_inventory.csv`
- `report/fullstack-ui-backend-audit-2026-03-31/ui_backend_matrix.json`

## Test Drift ve Kapsam Aciklari

Frontend test failure'larinin tamami urun regression degil. En az iki failure grubu test drift kaynakli:

- `frontend/src/test/components/JobForm.submission.test.tsx`
  - Beklenti TR etiketler uzerinden kurulmus
  - UI erisilebilir metinleri EN oldugu icin `8` test fail
- `frontend/src/test/integration/Editor.api-error.test.tsx`
  - Test eski label metnine bagli
  - UI tarafinda `GENERATE IN BATCH WITH AI` gorunuyor

Bu durum su anki test setinin release signal kalitesini dusuruyor. Testler guncellenmeden suite sonuclari tamamen guvenilir kabul edilmemeli.

## Destructive Flow Dogrulamasi

Destructive akislar plan geregi snapshot sonrasi ve en sonda kosuldu.

### Clip Delete

- Sonuc: `blocked`
- Neden: Canli clip olusmadi; bu nedenle subject scoped clip delete akisi guvenli sekilde dogrulanamadi.

### Account Purge

- Sonuc: `pass`
- Birinci purge ozet:
  - deleted_projects: `1`
  - deleted_social_rows: `5`
  - cancelled_jobs: `5`
- Ikinci purge ozet:
  - deleted_projects: `1`
  - deleted_social_rows: `0`
  - cancelled_jobs: `1`
- Son durum:
  - Audit subject icin proje ve clip kalmadi
  - Proje klasoru silindi
  - Subject parent klasoru kaldi
  - Ilgili olmayan baska subject verilerine dokunulmadi

Detay: `report/fullstack-ui-backend-audit-2026-03-31/destructive_flow_audit.json`

## Dokumantasyon Guncelleme Ihtiyaci

Bu fazda kaynak dokumantasyon degistirilmedi. Ancak asagidaki dokumanlar icin guncelleme ihtiyaci netlestirildi:

- `README.md`
- `docs/README.md`
- `docs/flows/upload-transcribe.md`
- `docs/pages/auto-cut.md`
- `docs/flows/manual-cut.md`
- `docs/pages/clip-editor.md`
- `docs/pages/subtitle-editor.md`
- `docs/flows/reburn.md`
- `docs/operations/postiz-global-oauth-standard.md`
- `marketing/README.md`

Taslak ve kanit eslemesi:

- `report/fullstack-ui-backend-audit-2026-03-31/docs_update_draft.md`
- `report/fullstack-ui-backend-audit-2026-03-31/source_doc_change_map.json`

## Onerilen Sonraki Adimlar

1. `process-manual` icin nullable transcript score normalizasyonu ve terminal error garantisi ekleyin.
2. `manual-cut-upload` response modelini gercek cikti olusmadan basari gibi gorunmeyecek sekilde duzeltin.
3. `process-batch` icin progress timeout, heartbeat ve fallback terminal state davranisini netlestirin.
4. `marketing/src/app/compare/opus-clip-alternative/page.tsx` icin missing `Link` importunu duzeltin ve marketing build smoke testini CI gate yapin.
5. Social scheduler icin `tzdata` veya explicit timezone fallback ekleyin; backend testlerini yeniden kosturun.
6. Frontend test drift'ini temizleyin; stale TR/EN label beklentilerini UI'nin mevcut contractina hizalayin.
7. Clip olusumu yeniden calisir hale geldikten sonra bloklu endpointleri tekrar canli dogrulayin:
   - clip transcript
   - clip transcript recovery
   - reburn
   - clip delete
   - social prefill/publish/approve/cancel
8. Son adim olarak kaynak dokumantasyonu `docs_update_draft.md` baz alarak guncelleyin.

## Teslimatlar

Ana rapor:

- `report/FULLSTACK_UI_BACKEND_AUDIT_2026-03-31.md`

Ekler:

- `report/fullstack-ui-backend-audit-2026-03-31/environment_baseline.json`
- `report/fullstack-ui-backend-audit-2026-03-31/test_execution_log.csv`
- `report/fullstack-ui-backend-audit-2026-03-31/file_inventory.csv`
- `report/fullstack-ui-backend-audit-2026-03-31/endpoint_contract_matrix.csv`
- `report/fullstack-ui-backend-audit-2026-03-31/ui_backend_matrix.json`
- `report/fullstack-ui-backend-audit-2026-03-31/live_request_evidence.json`
- `report/fullstack-ui-backend-audit-2026-03-31/destructive_flow_audit.json`
- `report/fullstack-ui-backend-audit-2026-03-31/risk_register.json`
- `report/fullstack-ui-backend-audit-2026-03-31/source_doc_change_map.json`
- `report/fullstack-ui-backend-audit-2026-03-31/docs_update_draft.md`
