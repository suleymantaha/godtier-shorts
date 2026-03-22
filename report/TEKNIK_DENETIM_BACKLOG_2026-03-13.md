# GodTier Shorts Teknik Denetim Backlog'u

**Tarih:** 13 Mart 2026  
**Kaynak:** `report/TEKNIK_DENETIM_RAPORU_2026-03-13.md`

## Önceliklendirilmiş İş Listesi


| ID      | Öncelik | Alan                  | Problem                                                                                           | Etki                                                                   | Kanıt                                                                                                                                                                                   | Kök neden                                                   | Önerilen çözüm                                                                                 | Zorluk | Bağımlılıklar                            |
| ------- | ------- | --------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------ | ---------------------------------------- |
| GTS-A01 | P0      | Harici entegrasyon    | Postiz/Temporal compose düz metin secret ve zayıf varsayılan taşıyor                              | Credential sızıntısı, yetkisiz erişim, yayın yüzeyinin ele geçirilmesi | `/home/arch/postiz-docker-compose/docker-compose.yaml:11-18`, `:50-51`, `:145-147`, `:206-207`, `:262-263`                                                                              | Local dev compose zamanla operasyonel yüzey haline gelmiş   | Secret’ları dış kaynağa taşı, açık kaydı kapat, ağ erişimini sınırla, credential rotasyonu yap | M      | Deploy script, compose yönetimi          |
| GTS-A02 | P1      | Upload                | Body limiti akış seviyesinde garanti edilmiyor, temp copy + ikinci okuma var                      | Disk baskısı, büyük yüklerde DoS yüzeyi, gereksiz I/O                  | `backend/api/server.py:85-104`, `backend/api/upload_validation.py:24-30`, `backend/api/routes/clips.py:259-266`                                                                         | `Content-Length` tabanlı erken ret ve geç doğrulama         | Reverse proxy hard limit, streaming hash, chunk bazlı write/validation                         | M      | API gateway/proxy, upload route refactor |
| GTS-A03 | P1      | Security / Social     | Social credential şifreleme varsayılan secret ile çalışabiliyor; env-wide Postiz key fallback var | Çok kullanıcılı modelde credential izolasyonu zayıflar                 | `backend/services/social/crypto.py:11-19`, `backend/services/social/service.py:116-147`                                                                                                 | Dev modu kolaylığı güvenlikten önce gelmiş                  | `SOCIAL_ENCRYPTION_SECRET` zorunlu olsun, env fallback’i opt-in dev modu yap                   | S      | Startup validation                       |
| GTS-A04 | P1      | Dependency management | `requirements.txt` çalışma zamanını tam yansıtmıyor; Python hedefi drift’li                       | Temiz kurulum, CI ve container reproducibility bozulur                 | `requirements.txt`, `backend/api/security.py:13-14`, `backend/services/social/crypto.py:9`, `pyproject.toml:1-3`                                                                        | Manifest güncellemeleri import yüzeyiyle senkron tutulmamış | Eksik bağımlılıkları ekle, Python sürümünü tekilleştir, taze install smoke ekle                | S      | Packaging/CI                             |
| GTS-A05 | P2      | Backend architecture  | Orchestrator ve route katmanı hâlâ büyük; guardrail testi kırık                                   | Refactor güveni düşer, değişiklik maliyeti artar                       | `backend/core/orchestrator.py` 352 satır, `backend/api/routes/clips.py` 675 satır, pytest failure                                                                                       | Refactor yarım kalmış                                       | Orchestrator facade incelt, clips route’u alt modüllere ayır, guardrail’i tekrar yeşile döndür | M      | Workflow/modül sınırları                 |
| GTS-A06 | P2      | Frontend architecture | Büyük editör bileşenleri ve 35 lint warning kalıcı hale gelmiş                                    | UI regresyonları, bakım yükü, yavaş onboarding                         | `AutoCutEditor.tsx` 632, `Editor.tsx` 567, `ShareComposerModal.tsx` 556, `SubtitleEditor.tsx` 403, ESLint warnings                                                                      | Feature logic tek dosyada birikmiş                          | Hook + feature-slice ayrımı, warning budget, testleri bileşen alt katmanına taşı               | M      | UI tasarım kararı                        |
| GTS-A07 | P2      | Documentation / UX    | faster-whisper ve WhisperX terminolojisi karışmış                                                 | Kullanıcı mesajları ve incident triage yanıltıcı olur                  | `backend/core/workflows_pipeline.py:119-133`, `backend/core/orchestrator.py:327-344`, `frontend/src/components/AutoCutEditor.tsx:595-600`, `frontend/src/components/Editor.tsx:384-389` | Eski isimlendirme parça parça kalmış                        | Tek terminoloji sweep’i yap, docs/test types/UI copy’yi birlikte güncelle                      | S      | Docs + UI + backend metinler             |
| GTS-A08 | P2      | Scalability           | Job state process içinde, medya state yerel disk üzerinde                                         | Yatay ölçekleme ve multi-worker senaryoları zor                        | `backend/api/websocket.py:25-29`, `:99-115`, `backend/api/routes/jobs.py:44-97`                                                                                                         | Single-node local-first varsayımı                           | Job repository soyutla, kalıcı job state ekle, worker boundary tasarla                         | M      | Storage seçimi                           |
| GTS-A09 | P2      | UX correctness        | `/api/projects` hatasında UI sentetik sağlıklı durum üretiyor                                     | Sorun anında yanlış sağlık sinyali                                     | `frontend/src/api/client.ts:143-159`                                                                                                                                                    | Degraded mode modeli yok                                    | `unknown/degraded` alanı ekle, fallback state’i görünür yap                                    | S      | Frontend state modeli                    |
| GTS-A10 | P2      | Testing               | Coverage yüzdesi ve threshold görünmüyor                                                          | Testlerin nerede zayıf kaldığı ölçülemiyor                             | Repo script/manifests; coverage collector yok                                                                                                                                           | Test var ama coverage governance yok                        | Backend için `pytest-cov`, frontend için Vitest coverage ekle, threshold koy                   | S      | CI                                       |
| GTS-A11 | P3      | Docs                  | Frontend README şablon halinde kalmış                                                             | Katkı/onboarding kalitesi düşer                                        | `frontend/README.md`                                                                                                                                                                    | Template temizlenmemiş                                      | Proje özel README yaz                                                                          | XS     | Yok                                      |
| GTS-A12 | P3      | Ops                   | `run.sh` Conda varsayıyor                                                                         | Ortam taşınabilirliği düşer                                            | `run.sh:9-13`                                                                                                                                                                           | Tek geliştirici ortamına optimize edilmiş script            | Conda opsiyonel hale getir veya env detection ekle                                             | XS     | Developer tooling                        |


## Sprint Bazlı Öneri

### Sprint 1

- GTS-A01
- GTS-A02
- GTS-A03
- GTS-A04

### Sprint 2

- GTS-A05
- GTS-A06
- GTS-A07

### Sprint 3

- GTS-A08
- GTS-A09
- GTS-A10
- GTS-A11
- GTS-A12

## Kabul Kriterleri

### Güvenlik / Operasyon

- Postiz compose içinde düz metin secret kalmamalı.
- `SOCIAL_ENCRYPTION_SECRET` yoksa uygulama startup’ta fail etmeli.
- Upload limiti proxy + uygulama katmanında ölçülebilir şekilde enforce edilmeli.

### Kod Kalitesi

- `test_orchestrator_file_line_budget` tekrar geçmeli.
- Frontend lint warning sayısı en azından kritik editör dosyalarında anlamlı biçimde düşmeli.
- faster-whisper / WhisperX terminolojisi tekilleşmeli.

### Ölçeklenebilirlik / Gözlemlenebilirlik

- Job state soyutlama katmanı tanımlanmalı.
- Coverage raporu CI’da görünür ve threshold’lu olmalı.

## İlerleme Notu (2026-03-20)

- Faz 1 tamamlandı:
  - AUD-001 remediation uygulandı; verify hattını kıran üç frontend lint error kapatıldı.
  - AUD-002 remediation uygulandı; sosyal approval testi göreli gelecek zamanla deterministik hale getirildi.
- Faz 2 tamamlandı:
  - `GTS-A05` guardrail refactor işi kapatıldı; orchestrator ve workflow bütçeleri tekrar yeşile döndü.
- Faz 3 tamamlandı:
  - `backend.core -> backend.api` bağımlılığı port/adaptor sınırına taşındı.
  - Subtitle planning için frontend/backend ortak parity fixture ve test zemini kuruldu.
- Faz 4 tamamlandı:
  - docs link checker eklendi ve docs relative link drift'i temizlendi.
  - `requirements.lock` ve Python dependency audit akışı tanımlandı; audit temiz.
- Sonraki aktif backlog odağı:
  - `GTS-A06` aktif olarak ele alınmaya başlandı; ilk warning-reduction checkpoint'inde frontend lint yükü `53` warning'den `45` warning'e indirildi.
  - Refactor edilen ilk küme: resilient auth, holo terminal, subtitle preview, video overlay ve auto-cut editor state.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `45` warning; hedefli 5 Vitest dosyası temiz.
  - İkinci warning-reduction checkpoint'inde auth client, websocket ve auto-cut controller/state kümesi sadeleştirildi; frontend lint yükü `37` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `37` warning; `client`, `useWebSocket` ve `AutoCutEditor` hedefli testleri temiz.
  - Üçüncü warning-reduction checkpoint'inde `autoCutEditor/sections.tsx` ve `clipGallery/*` kümesi sadeleştirildi; frontend lint yükü `34` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `34` warning; `ClipGallery` ve `AutoCutEditor` hedefli testleri temiz.
  - Dördüncü warning-reduction checkpoint'inde `editor/helpers.ts` ve `jobForm/*` kümesi sadeleştirildi; frontend lint yükü `32` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `32` warning; `editor helpers` ve `JobForm` hedefli testleri temiz.
  - Beşinci warning-reduction checkpoint'inde `jobForm` kümesindeki kalan küçük warning kapatıldı ve `subtitleEditor` için ilk sadeleştirme dilimi atıldı; frontend lint yükü `30` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `30` warning; `JobForm` + `SubtitleEditor` hedefli testleri temiz.
  - Altıncı warning-reduction checkpoint'inde `frontend/src/components/subtitleEditor/sections.tsx` içindeki preview/transcript wiring, render warning kuralları ve transcript durum kartları ayrıştırıldı; frontend lint yükü `26` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `26` warning; `SubtitleEditor.project/auth/clip` hedefli testleri temiz.
  - Yedinci warning-reduction checkpoint'inde `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde locked-clip dependency zinciri düzeltildi, transcript loader helper'lara bölündü ve editor action parametre yüzeyi daraltıldı; frontend lint yükü `19` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `19` warning; `SubtitleEditor.project/auth/clip` hedefli testleri temiz.
  - Sekizinci warning-reduction checkpoint'inde `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içindeki job-tracking/recovery kararları helper'lara ayrıldı ve controller build çıktısı state/handler katmanlarına bölündü; subtitle-editor controller dosyası warning'siz hale geldi ve frontend lint yükü `16` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `16` warning; `SubtitleEditor.project/auth/clip` hedefli testleri temiz.
  - Dokuzuncu warning-reduction checkpoint'inde `frontend/src/components/subtitlePreview/helpers.ts` ve `frontend/src/hooks/useWebSocket.helpers.ts` içindeki complexity adaları yardımcı çözücülere bölündü; frontend lint yükü `14` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> `0` error, `14` warning; `subtitlePreview helpers` ve `useWebSocket helpers` hedefli testleri temiz.
  - Onuncu ve kapanış checkpoint'inde kalan `subtitleStyles`, `useJobStore`, bütün test dosyası warning'leri ve build-blocker TypeScript hataları temizlendi; frontend lint yükü `0` warning seviyesine indi.
  - Doğrulama: `cd frontend && npm run lint` -> temiz; `cd frontend && npm run test -- --reporter=dot` -> `232 passed`; `cd frontend && npm run build` -> başarılı.
  - Kapanış checkpoint'inde `frontend/src/test/components/ClipGallery.test.tsx` içindeki `act(...)` console-noise temizlendi; hedefli `ClipGallery` test dosyası `11 passed` ile geçti.
  - `GTS-A07` terminoloji sweep'i tamamlandı; `scripts/test_subtitle_styles.py`, `README.md` ve `docs/refactor/workflow-failure-modes.md` aktif terminolojiyi `faster-whisper` etrafında tekilleştirdi.
  - Doğrulama: `python -m py_compile scripts/test_subtitle_styles.py` temiz; aktif dosya taramasında `WhisperX|whisperx|whisperx_json_path` eşleşmesi kalmadı; `bash scripts/verify.sh` tamamı geçti.
  - `GTS-A08` için `backend/services/job_state.py` ile kalıcı job repository katmanı eklendi; singleton websocket manager artık `workspace/state/jobs.json` üzerinden serializable job state saklıyor.
  - Restart sonrası yarım kalan `queued/processing` işler güvenli biçimde `error` durumuna çekilecek şekilde recovery kuralı eklendi; runtime-only alanlar (`cancel_event`, `task`, `task_handle`) persist edilmiyor.
  - Doğrulama: hedefli job/websocket testleri `15 passed`, route/recovery/purge odaklı ikinci paket `22 passed`; tam `bash scripts/verify.sh` sonucu `frontend 232 passed`, `backend 256 passed, 2 skipped`, build başarılı.
  - `GTS-A09` için `frontend/src/api/client.ts` proje listeleme çağrısı `good/degraded/unknown` modeline geçirildi; başarılı sonuçlar cache'leniyor, hata anında son senkron liste varsa `degraded`, yoksa `unknown` dönüyor.
  - `SubtitleEditor` seçim kartı artık `/api/projects` hatasında sentetik "Henüz proje yok" sağlıklı boş durumu göstermiyor; degrade durumda cache'lenmiş proje listesi görünür uyarıyla kullanılabiliyor.
  - Doğrulama: hedefli frontend testleri `16 passed`; ilgili ESLint yüzeyi temiz; tam `bash scripts/verify.sh` sonucu `frontend 237 passed`, `backend 256 passed, 2 skipped`, build başarılı.
- 21 Mart 2026 checkpoint'leri:
  - `GTS-A10` tamamlandı; `scripts/check_coverage.sh` ile backend/frontend coverage threshold kapısı eklendi, `verify.yml` dependency kurulum + coverage artifact yükleme ile genişletildi. Doğrulama: backend coverage `73.48%`, frontend coverage `78.1 / 69.15 / 79.8 / 78.47`, tam `bash scripts/verify.sh` temiz.
  - `GTS-A11` tamamlandı; `frontend/README.md` proje özel env/komut/feature/test rehberine dönüştürüldü. Doğrulama: `python scripts/check_markdown_links.py docs README.md frontend/README.md scripts/README.md` temiz.
  - `GTS-A12` tamamlandı; `run.sh` Conda zorunluluğundan çıkarıldı, aktif env / `APP_ENV_NAME` Conda / `.venv` / `venv` / sistem fallback sırası eklendi, `SKIP_ENV_ACTIVATION=1` desteği getirildi. Doğrulama: `bash -n run.sh`; `timeout 35 ./run.sh` startup smoke temiz.
  - `GTS-A03` tamamlandı; `POSTIZ_API_KEY` env fallback varsayılan olarak kapatıldı, yalnız `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1` ile dev opt-in hale getirildi. Doğrulama: `pytest backend/tests/test_social_crypto.py backend/tests/test_runtime_validation.py backend/tests/test_social_routes.py -q` -> `31 passed`; `bash scripts/verify.sh` -> `backend 260 passed, 2 skipped`.
  - `GTS-A03` için ikinci izolasyon checkpoint'i tamamlandı; social publish target'ları artık request payload'ından kör kabul edilmiyor, subject'e bağlı Postiz account listesiyle eşleştirilerek doğrulanıyor. Aynı turda `social-share-buffer` local draft anahtarı auth identity ile scope edildi; aynı tarayıcıdaki kullanıcı değişiminde paylaşım taslağı sızıntısı önlendi. Doğrulama: `pytest backend/tests/test_social_routes.py -q` -> `13 passed`; `cd frontend && npm run test -- src/test/App.test.tsx src/test/components/shareComposer.helpers.test.ts src/test/components/ShareComposerModal.connection.test.tsx src/test/components/ShareComposerModal.publish.test.tsx src/test/components/ShareComposerModal.drafts.test.tsx --reporter=dot` -> `16 passed`; `bash scripts/verify.sh` -> `backend 263 passed, 2 skipped`, `frontend 237 passed`.
  - `GTS-A02` repo içi guardrail checkpoint'i kayda alındı; `/api/upload` ve `/api/manual-cut-upload` için erken `413` middleware kapısı entegrasyon testine bağlandı. Doğrulama: upload hedefli paket `10 passed`; tam `bash scripts/verify.sh` sonucu `backend 262 passed, 2 skipped`.
  - `GTS-A01` sibling compose repo'da tekrar doğrulandı; düz metin `JWT_SECRET`, DB parolaları, gerçek YouTube OAuth credential'ı ve host'a açık `4007/8969/7233/8080` yüzeyi hâlâ duruyor. Dış repo kirli worktree taşıdığı için otomatik remediation patch'i bu turda uygulanmadı.
  - `GTS-A01` için sibling repo'ya additive `docker-compose.secure.yaml` overlay'i, `.env.secure.example` ve `HARDENING.md` eklendi. Render doğrulaması temiz; bu adım mevcut stack'i bozmadan secret externalization + localhost bind geçişini hazırlıyor.
  - `GTS-A01` için secure rollout checkpoint'i tamamlandı; sibling repo'da `.env.secure` üretildi, `spotlight pull_policy` ağı bloklamayacak şekilde `missing` yapıldı ve overlay ile `up -d` rollout başarıyla tamamlandı. Doğrulama: `docker compose ... ps` içinde `postiz`, `spotlight`, `temporal`, `temporal-ui` up; `ss -ltn` yalnız `127.0.0.1:4007/8969/7233/8080` dinliyor; `curl -I http://127.0.0.1:4007` -> `307 /auth`.
  - `GTS-A01` için secret rotation checkpoint'i tamamlandı; yeni JWT/Postiz DB/Temporal DB secret'ları üretildi, DB rollerine canlı `ALTER ROLE` uygulandı ve overlay restart sonrası yeni parolaların network içinden çalıştığı, eskilerin reddedildiği kanıtlandı. Doğrulama: transient `postgres` client container'larıyla `new password -> select 1`, `old password -> password authentication failed`; `curl -I http://127.0.0.1:4007` -> `307 /auth`.
  - `GTS-A01` için canlı OAuth smoke checkpoint'i tamamlandı; `http://127.0.0.1:4007/auth` üzerinden Google butonu CORS ile düştü çünkü uygulama OAuth fetch'ini `http://localhost:4007/api/auth/oauth/GOOGLE` adresine yapıyor. Aynı akış `http://localhost:4007/auth` üzerinden tekrarlandığında Google giriş ekranına başarılı yönlendirme geldi ve `redirect_uri=http://localhost:4007/integrations/social/youtube` kanıtlandı.
  - `GTS-A01` için manuel multi-account validation tamamlandı; kullanıcı doğrulamasına göre iki farklı hesap ayrı ayrı giriş yaptığında her kullanıcı yalnız kendi bağlı hesabını kendi alanında gördü. Böylece hem Postiz OAuth akışı hem de hesap izolasyonu operasyonel olarak doğrulandı.
  - `GTS-A01` için ürün yüzeyinde `managed` connection-mode ilk dilimi tamamlandı; backend `connection_mode` yayınlıyor, `managed` modda manuel API key kaydı `403` ile kapanıyor ve `ShareComposer` bu modda API key alanını gizleyip yönetilen bağlantı metnine geçiyor. Doğrulama: backend hedefli paket `28 passed`, frontend bağlantı modal testi `2 passed`.
- Son kapanan alanlar:
  - `GTS-A06` frontend warning yükü remediation'ı tamamlandı
  - `GTS-A07` terminoloji sweep'i tamamlandı
  - `ClipGallery` test console-noise temizliği tamamlandı
  - `GTS-A08` job state repository ve kalıcı state checkpoint'i tamamlandı
  - `GTS-A09` `/api/projects` degrade-mode checkpoint'i tamamlandı
  - `GTS-A10` coverage governance tamamlandı
  - `GTS-A11` frontend README remediation'ı tamamlandı
  - `GTS-A12` run.sh portability remediation'ı tamamlandı
  - `GTS-A03` social credential env fallback hardening tamamlandı
  - `GTS-A02` repo içi upload hard-limit guardrail kanıtı sabitlendi
- Açık kalan ana operasyonel alan:
  - Operasyon notu: Postiz UI localhost host adıyla kullanılmalı; `127.0.0.1` üzerinden OAuth başlangıcı CORS'a düşüyor
- Açık kalan ürün alanı:
  - `managed` mod için gerçek subject-bazlı OAuth callback/storage akışı henüz uygulama içine taşınmadı
