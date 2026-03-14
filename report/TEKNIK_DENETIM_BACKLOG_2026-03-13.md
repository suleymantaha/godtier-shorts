# GodTier Shorts Teknik Denetim Backlog'u

**Tarih:** 13 Mart 2026  
**Kaynak:** `report/TEKNIK_DENETIM_RAPORU_2026-03-13.md`

## Önceliklendirilmiş İş Listesi

| ID | Öncelik | Alan | Problem | Etki | Kanıt | Kök neden | Önerilen çözüm | Zorluk | Bağımlılıklar |
|---|---|---|---|---|---|---|---|---|---|
| GTS-A01 | P0 | Harici entegrasyon | Postiz/Temporal compose düz metin secret ve zayıf varsayılan taşıyor | Credential sızıntısı, yetkisiz erişim, yayın yüzeyinin ele geçirilmesi | `/home/arch/postiz-docker-compose/docker-compose.yaml:11-18`, `:50-51`, `:145-147`, `:206-207`, `:262-263` | Local dev compose zamanla operasyonel yüzey haline gelmiş | Secret’ları dış kaynağa taşı, açık kaydı kapat, ağ erişimini sınırla, credential rotasyonu yap | M | Deploy script, compose yönetimi |
| GTS-A02 | P1 | Upload | Body limiti akış seviyesinde garanti edilmiyor, temp copy + ikinci okuma var | Disk baskısı, büyük yüklerde DoS yüzeyi, gereksiz I/O | `backend/api/server.py:85-104`, `backend/api/upload_validation.py:24-30`, `backend/api/routes/clips.py:259-266` | `Content-Length` tabanlı erken ret ve geç doğrulama | Reverse proxy hard limit, streaming hash, chunk bazlı write/validation | M | API gateway/proxy, upload route refactor |
| GTS-A03 | P1 | Security / Social | Social credential şifreleme varsayılan secret ile çalışabiliyor; env-wide Postiz key fallback var | Çok kullanıcılı modelde credential izolasyonu zayıflar | `backend/services/social/crypto.py:11-19`, `backend/services/social/service.py:116-147` | Dev modu kolaylığı güvenlikten önce gelmiş | `SOCIAL_ENCRYPTION_SECRET` zorunlu olsun, env fallback’i opt-in dev modu yap | S | Startup validation |
| GTS-A04 | P1 | Dependency management | `requirements.txt` çalışma zamanını tam yansıtmıyor; Python hedefi drift’li | Temiz kurulum, CI ve container reproducibility bozulur | `requirements.txt`, `backend/api/security.py:13-14`, `backend/services/social/crypto.py:9`, `pyproject.toml:1-3` | Manifest güncellemeleri import yüzeyiyle senkron tutulmamış | Eksik bağımlılıkları ekle, Python sürümünü tekilleştir, taze install smoke ekle | S | Packaging/CI |
| GTS-A05 | P2 | Backend architecture | Orchestrator ve route katmanı hâlâ büyük; guardrail testi kırık | Refactor güveni düşer, değişiklik maliyeti artar | `backend/core/orchestrator.py` 352 satır, `backend/api/routes/clips.py` 675 satır, pytest failure | Refactor yarım kalmış | Orchestrator facade incelt, clips route’u alt modüllere ayır, guardrail’i tekrar yeşile döndür | M | Workflow/modül sınırları |
| GTS-A06 | P2 | Frontend architecture | Büyük editör bileşenleri ve 35 lint warning kalıcı hale gelmiş | UI regresyonları, bakım yükü, yavaş onboarding | `AutoCutEditor.tsx` 632, `Editor.tsx` 567, `ShareComposerModal.tsx` 556, `SubtitleEditor.tsx` 403, ESLint warnings | Feature logic tek dosyada birikmiş | Hook + feature-slice ayrımı, warning budget, testleri bileşen alt katmanına taşı | M | UI tasarım kararı |
| GTS-A07 | P2 | Documentation / UX | faster-whisper ve WhisperX terminolojisi karışmış | Kullanıcı mesajları ve incident triage yanıltıcı olur | `backend/core/workflows_pipeline.py:119-133`, `backend/core/orchestrator.py:327-344`, `frontend/src/components/AutoCutEditor.tsx:595-600`, `frontend/src/components/Editor.tsx:384-389` | Eski isimlendirme parça parça kalmış | Tek terminoloji sweep’i yap, docs/test types/UI copy’yi birlikte güncelle | S | Docs + UI + backend metinler |
| GTS-A08 | P2 | Scalability | Job state process içinde, medya state yerel disk üzerinde | Yatay ölçekleme ve multi-worker senaryoları zor | `backend/api/websocket.py:25-29`, `:99-115`, `backend/api/routes/jobs.py:44-97` | Single-node local-first varsayımı | Job repository soyutla, kalıcı job state ekle, worker boundary tasarla | M | Storage seçimi |
| GTS-A09 | P2 | UX correctness | `/api/projects` hatasında UI sentetik sağlıklı durum üretiyor | Sorun anında yanlış sağlık sinyali | `frontend/src/api/client.ts:143-159` | Degraded mode modeli yok | `unknown/degraded` alanı ekle, fallback state’i görünür yap | S | Frontend state modeli |
| GTS-A10 | P2 | Testing | Coverage yüzdesi ve threshold görünmüyor | Testlerin nerede zayıf kaldığı ölçülemiyor | Repo script/manifests; coverage collector yok | Test var ama coverage governance yok | Backend için `pytest-cov`, frontend için Vitest coverage ekle, threshold koy | S | CI |
| GTS-A11 | P3 | Docs | Frontend README şablon halinde kalmış | Katkı/onboarding kalitesi düşer | `frontend/README.md` | Template temizlenmemiş | Proje özel README yaz | XS | Yok |
| GTS-A12 | P3 | Ops | `run.sh` Conda varsayıyor | Ortam taşınabilirliği düşer | `run.sh:9-13` | Tek geliştirici ortamına optimize edilmiş script | Conda opsiyonel hale getir veya env detection ekle | XS | Developer tooling |

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
