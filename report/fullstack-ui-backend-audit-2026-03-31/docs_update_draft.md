# Documentation Update Draft

## Status Update 2026-04-01

Bu taslak uygulanmistir. Kaynak kod ve ilgili kaynak dokumantasyon dosyalari guncellenmis, dogrulama tekrar alinmistir.

- Backend full suite: `321 passed, 2 skipped`
- Frontend full suite: `302 passed, 4 skipped`
- Frontend build: pass
- Frontend lint: `0 error, 35 warning`
- Marketing build: pass

Uygulanan hedefler:

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

Asagidaki bolumler, `2026-03-31` tarihli orijinal draft icerigini iz kaydi icin korur.

## Durum

- Bu satirlar orijinal audit fazinin draft notlaridir.
- Guncel uygulama durumu bu dosyanin ustundeki `Status Update 2026-04-01` bolumundedir.

## Onerilen Dokumantasyon Guncellemeleri

### `README.md`

- Oncelik: High
- Neden: Canli dogrulamada upload sonrasi proje kimligi ve dosya yerlesimi mevcut anlatimdan farkli. `cache-status`, `start-job` ve subject-scoped proje davranisi netlestirilmeli.
- Guncellenecek bolumler:
  - Hizli Baslangic
  - Islem Akislari
  - API Ozeti
  - Guvenli dosya erisimi
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_pipeline_scenario.json`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/jobs_live_controls.json`

### `docs/README.md`

- Oncelik: Medium
- Neden: Ana dokuman girisinde bu audit raporuna, bilinen kirik akislara ve tekrar calistirilmasi gereken test paketlerine link verilmesi gerekiyor.
- Guncellenecek bolumler:
  - Sayfalar (UI)
  - Is Akislari
  - Kalite ve Tani
- Kanit:
  - `report/FULLSTACK_UI_BACKEND_AUDIT_2026-03-31.md`

### `docs/flows/upload-transcribe.md`

- Oncelik: High
- Neden: Dokuman eski duz proje dizin yapisini anlatiyor. Canli sistemde proje yolu subject-scoped gorunuyor: `workspace/projects/<subject_hash>/<project_id>/...`
- Guncellenecek bolumler:
  - Akis
  - Adimlar
  - Proje Yapisi
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_pipeline_scenario.json`

### `docs/pages/auto-cut.md`

- Oncelik: High
- Neden: Happy path anlatimi canli davranisla uyusmuyor. `manual-cut-upload` 200 donmesine ragmen terminalde error ile bitiyor; `process-batch` makul surede terminal duruma ulasmiyor.
- Guncellenecek bolumler:
  - API Endpointleri
  - Kullanici Akisi
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/manual_cut_upload_scenario.json`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_request_evidence_extended.json`

### `docs/flows/manual-cut.md`

- Oncelik: High
- Neden: Optimistic response davranisi ve `score=None` kaynakli crash riski mevcut dokumanda yok.
- Guncellenecek bolumler:
  - Tek Klip Akisi
  - API Parametreleri
  - Cikti
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/runtime/backend_stderr.log`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/manual_cut_upload_scenario.json`

### `docs/pages/clip-editor.md`

- Oncelik: Medium
- Neden: Reburn ve clip uzerinden devam eden editor akisi canlida clip olusmadigi icin tam dogrulanamadi. Onkosullar ve bilinen blokajlar acik yazilmali.
- Guncellenecek bolumler:
  - API Endpointleri
  - Kullanici Akisi
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_request_evidence_extended.json`

### `docs/pages/subtitle-editor.md`

- Oncelik: Medium
- Neden: Project transcript save/recover canli olarak dogrulandi; clip transcript recovery ve reburn ise clip uretim blokaji nedeniyle dogrulanamadi. Ayrim netlestirilmeli.
- Guncellenecek bolumler:
  - API Endpointleri
  - Kullanici Akisi
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_request_evidence_extended.json`

### `docs/flows/reburn.md`

- Oncelik: Medium
- Neden: Reburn happy path canli ortamda tamamlanamadi; clip olusmadan bu akis dogrulanamiyor.
- Guncellenecek bolumler:
  - Kullanim Senaryolari
  - Kalite Ozeti
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/api/live_request_evidence_extended.json`

### `docs/operations/postiz-global-oauth-standard.md`

- Oncelik: High
- Neden: Windows/IANA timezone verisi eksigi social publish/calendar testlerini kiriyor. Operasyon notlarina `tzdata` veya fallback zorunlulugu eklenmeli.
- Guncellenecek bolumler:
  - Global Olanlar
  - Kesin Kurallar
  - Operasyon Akisi
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/tests/backend_target_suite.log`

### `marketing/README.md`

- Oncelik: Medium
- Neden: Marketing build smoke ve route health beklentileri yazili degil. `compare/opus-clip-alternative` route'u eksik `Link` importu nedeniyle build ve runtime seviyesinde kirik.
- Guncellenecek bolumler:
  - Commands
  - Environment
- Kanit:
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/tests/marketing_build.log`
  - `report/fullstack-ui-backend-audit-2026-03-31/evidence/ui/http_route_checks.json`

## Dokumanlara Eklenecek Genel Notlar

- Canli audit tarihi: `2026-03-31`
- Auth modu: `static_token`
- Audit subject hash: `3462292b60860538b5a07d5d89e1eb94`
- Ortam notu:
  - `ffmpeg`, `yt-dlp`, `nvidia-smi` dogrulandi
  - `torch.cuda` warning seviyesinde
- Bilinen kritik blokajlar:
  - `process-manual` background crash
  - `manual-cut-upload` optimistic success, terminal error
  - `process-batch` hanging
  - marketing compare route build/runtime failure
  - social timezone bagimlilik problemi

## Uygulama Sirasi

1. Once runtime davranisini etkileyen kirik akislari duzelt.
2. Ardindan bloklu canli endpointleri tekrar dogrula.
3. Son olarak kaynak dokumantasyon dosyalarini guncelle ve bu taslaktaki referanslari kalici dokumanlara tasi.

## Referans Ekler

- `report/fullstack-ui-backend-audit-2026-03-31/source_doc_change_map.json`
- `report/fullstack-ui-backend-audit-2026-03-31/risk_register.json`
- `report/fullstack-ui-backend-audit-2026-03-31/live_request_evidence.json`

