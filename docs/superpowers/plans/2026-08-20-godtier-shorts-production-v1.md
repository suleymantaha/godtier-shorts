# GodTier Shorts Production v1 — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GodTier Shorts'u lokal GPU uygulamasından; ödeme alan, kötüye kullanımı ekonomik olarak engelleyen, güvenli biçimde video işleyen ve NVIDIA GPU worker'larında ölçeklenebilen canlı bir SaaS'a dönüştürmek.

**Architecture:** React/Vite + Clerk frontend ve FastAPI control-plane 7/24 CPU sunucusunda çalışır. PostgreSQL kalıcı iş/ödeme/kredi verisini, Redis ise dağıtık iş kuyruğunu tutar. Video dosyaları private S3-compatible object storage'da saklanır. NVIDIA GPU worker (ilk hedef RTX 6000 Ada 48 GB veya L40S 48 GB) yalnız ücretli render işlerini tüketir. iyzico ödeme ve abonelik kaynağıdır; Cloudflare edge/WAF/Turnstile katmanı abuse ve DDoS önünde durur.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, asyncpg, Redis, ARQ (async Redis queue), boto3-compatible S3 client, PostgreSQL, React 19, Vite 7, TypeScript, Clerk, Cloudflare, iyzico, RunPod/NVIDIA GPU, FFmpeg/NVENC, faster-whisper, Ultralytics YOLO11.

**Spec:** Bu plan, mevcut `README.md`, `.env.example`, `backend/api/routes/jobs.py`, `backend/services/job_state.py`, `backend/services/transcription.py`, `backend/services/video_processor.py`, `frontend/src/*` yapısını temel alır.

## Global Constraints

- Mevcut lokal kullanım bozulmayacak; production özellikleri config/adapter katmanı ile eklenecek.
- Kart numarası/CVV GodTier backend'ine hiçbir zaman gelmeyecek; hosted/provider ödeme akışı kullanılacak.
- Ödeme/kredi artışı yalnız doğrulanmış iyzico webhook veya admin işlemi ile yapılacak.
- iyzico webhook doğrulamasında `X-IYZ-SIGNATURE-V3` kullanılacak; webhook idempotent olacak.
- Free kullanıcıya tam 1080p GPU render hakkı verilmeyecek.
- Free değer gösterimi mümkün olduğunca captions/transcript/LLM ve browser preview ile yapılacak; ağır YOLO+NVENC render ödeme sonrasına bırakılacak.
- GPU worker public internete açık API olmayacak.
- Kullanıcı A hiçbir koşulda kullanıcı B'nin project/job/asset/billing verisini göremeyecek.
- Job başlamadan önce kredi/entitlement rezervasyonu yapılacak; hata/iptalde rezervasyon iade edilecek.
- Source URL'lerde yalnız izin verilen `https` kaynakları kullanılacak; localhost/private IP/metadata/file scheme engellenecek.
- Upload'lar private object storage'a presigned URL ile gidecek; API üzerinden çok-GB dosya proxy edilmeyecek.
- Admin hesabında MFA ve step-up verification zorunlu olacak.
- Tüm kritik ödeme, kredi, admin ve güvenlik olayları append-only audit log'a yazılacak.
- Production secret'ları repo/.env dosyasına commit edilmeyecek.
- Her task TDD + bağımsız test + küçük commit ile ilerleyecek.

---

# 1. ÜRÜN VE PARA KAZANMA MODELİ

## 1.1 Funnel

```text
Landing
  ↓
YouTube URL / Upload seçimi
  ↓
Sign up / Sign in
  ↓
FREE VIRAL SCAN
  ├─ metadata
  ├─ captions varsa captions
  ├─ transcript gerekiyorsa düşük maliyetli limitli transcribe
  ├─ viral segment ranking
  └─ browser tabanlı preview
  ↓
"Videonda 3 güçlü Short bulduk"
  ↓
PAYWALL
  ↓
iyzico checkout
  ↓
Webhook doğrulaması
  ↓
Subscription/credits active
  ↓
FULL GPU RENDER
  ├─ faster-whisper large-v3 (gerekiyorsa)
  ├─ YOLO11 tracking
  ├─ 9:16 smart crop
  ├─ kinetic subtitles
  └─ NVENC 1080p
  ↓
Download / publish / next render
```

## 1.2 Free kullanıcı

Free kullanıcı **tam video üretmez**. Free teklif:

- 1 aktif ücretsiz analiz hakkı / identity cluster.
- YouTube caption varsa tam transcript üzerinden analiz; caption yoksa limitli düşük maliyetli transcribe.
- En fazla 3 viral segment adayı.
- Viral score + hook + transcript snippet + başlangıç/bitiş süresi.
- Tarayıcı içinde simüle edilmiş 9:16/caption preview.
- 1080p export, gerçek YOLO tracking, batch render, watermark'sız download ve social publish kilitli.

Bu yapı multi-account saldırısında GPU maliyetini dramatik biçimde düşürür. Risk motoru ayrı katmandır ama ana savunma ödeme duvarının ağır GPU işinden önce olmasıdır.

## 1.3 Ücretli plan modeli

Müşteriye “GPU kredisi” değil sonuç satılacak. Backend iç muhasebesi compute-credit olabilir.

- Starter: düşük kaynak saat + düşük Short kotası.
- Creator: ana paket; daha yüksek kaynak saat + batch + social publish.
- Pro: yüksek kota + priority queue + daha uzun retention.
- Add-on: ek kaynak dakika / ek Short paketi.
- Monthly + yearly abonelik.

Fiyatlar gerçek GPU benchmark + ödeme komisyonu + LLM + storage + support maliyeti ölçülmeden hard-code edilmeyecek. Veritabanında fiyat/limit config tabanlı olacak.

---

# 2. TARGET PRODUCTION MİMARİSİ

```text
                           Cloudflare
                    DNS + TLS + WAF + Rate Limit
                        + Turnstile Challenge
                                │
                    ┌───────────┴───────────┐
                    │                       │
              Static Frontend          FastAPI API
               React / Vite             CPU-only
                    │                       │
                    │                 Clerk JWT/RBAC
                    │                       │
                    │       ┌───────────────┼───────────────┐
                    │       │               │               │
                    │  PostgreSQL         Redis           iyzico
                    │       │             Queue           Billing
                    │       │               │             Webhooks
                    │       │               │
                    │       └──────────┬────┘
                    │                  │
                    │          PRIVATE GPU WORKER
                    │        RTX 6000 Ada / L40S
                    │                  │
                    │      Whisper → YOLO → NVENC
                    │                  │
                    └──────────── Private R2/S3
                                     │
                              Short-lived signed URLs
```

### İlk deployment seçimi

- Edge/DNS/WAF: Cloudflare.
- CPU control plane: tek Linux VPS + Docker Compose ile başlamak.
- DB: PostgreSQL container veya managed PostgreSQL; production beta için backup zorunlu.
- Queue: Redis.
- Storage: Cloudflare R2/S3-compatible private bucket.
- GPU: RunPod NVIDIA GPU worker; ilk benchmark RTX 6000 Ada 48 GB vs L40S 48 GB.
- Auth: mevcut Clerk.
- Payment: iyzico Subscription + hosted/payment form.

Kubernetes, çok-region, Kafka ve mikroservis patlaması v1 kapsamı dışındadır.

---

# 3. VERİ MODELİ

## 3.1 Tablolar

### `users`
- `id UUID PK`
- `clerk_subject TEXT UNIQUE NOT NULL`
- `email_normalized TEXT NULL`
- `status ENUM(active, suspended, deleted)`
- `role ENUM(user, support, admin)`
- `created_at`, `updated_at`

### `plans`
- `id UUID PK`
- `code TEXT UNIQUE` (`starter`, `creator`, `pro`)
- `name`
- `monthly_price_minor`
- `currency`
- `monthly_compute_credits`
- `max_source_minutes_per_job`
- `max_clips_per_job`
- `max_active_jobs`
- `retention_days`
- `priority`
- `active`

### `subscriptions`
- `id UUID PK`
- `user_id FK`
- `provider = iyzico`
- `provider_subscription_ref UNIQUE`
- `plan_id FK`
- `status ENUM(pending, active, past_due, cancelled, expired)`
- `period_start`, `period_end`
- `cancel_at_period_end`
- `created_at`, `updated_at`

### `payments`
- `id UUID PK`
- `user_id FK`
- `provider_payment_id UNIQUE`
- `provider_conversation_id`
- `amount_minor`
- `currency`
- `status`
- `event_type`
- `raw_event_hash`
- `created_at`

### `credit_wallets`
- `user_id PK/FK`
- `available BIGINT`
- `reserved BIGINT`
- `updated_at`

### `credit_ledger`
Append-only.
- `id UUID PK`
- `user_id FK`
- `kind ENUM(grant,reserve,release,settle,refund,adjustment,expire)`
- `amount BIGINT`
- `job_id UUID NULL`
- `payment_id UUID NULL`
- `idempotency_key TEXT UNIQUE`
- `metadata JSONB`
- `created_at`

### `jobs`
Mevcut JSON job state'in production karşılığı.
- `id UUID PK`
- `user_id FK`
- `project_id UUID`
- `type ENUM(preview,full_render,reburn,batch)`
- `status ENUM(queued,processing,completed,error,cancelled,review_required)`
- `request JSONB`
- `progress SMALLINT`
- `last_message`
- `error_code`, `error_message`
- `reserved_credits`
- `settled_credits`
- `gpu_seconds`
- `gpu_model`
- `started_at`, `finished_at`, `created_at`

### `job_events`
- `id BIGSERIAL PK`
- `job_id FK`
- `status`
- `progress`
- `message`
- `source`
- `created_at`

### `projects`
- `id UUID PK`
- `user_id FK`
- `source_type ENUM(youtube,upload)`
- `source_ref`
- `source_fingerprint`
- `title`
- `duration_seconds`
- `created_at`

### `assets`
- `id UUID PK`
- `user_id FK`
- `project_id FK`
- `job_id FK NULL`
- `kind ENUM(source,transcript,preview,short,thumbnail,debug)`
- `storage_key UNIQUE`
- `mime_type`
- `size_bytes`
- `sha256`
- `expires_at NULL`
- `created_at`

### `trial_entitlements`
- `id UUID PK`
- `user_id FK`
- `identity_key_hash`
- `status ENUM(available,claimed,blocked)`
- `claimed_at`
- `reason`

### `risk_events`
- `id BIGSERIAL PK`
- `user_id FK NULL`
- `request_id`
- `signal`
- `weight`
- `value_hash NULL`
- `metadata JSONB`
- `created_at`

### `webhook_events`
- `id UUID PK`
- `provider`
- `provider_event_key UNIQUE`
- `signature_valid BOOLEAN`
- `payload_hash`
- `processed_at NULL`
- `created_at`

### `audit_logs`
Append-only.
- `id BIGSERIAL PK`
- `actor_type`
- `actor_id`
- `action`
- `target_type`
- `target_id`
- `request_id`
- `ip_hash`
- `metadata JSONB`
- `created_at`

---

# 4. DOSYA YAPISI

## Backend — yeni

```text
backend/db/
  __init__.py
  base.py
  session.py
  models.py

backend/services/billing/
  __init__.py
  iyzico_client.py
  pricing.py
  ledger.py
  subscription_service.py
  webhook_service.py

backend/services/abuse/
  __init__.py
  risk_engine.py
  trial_service.py
  source_fingerprint.py

backend/services/storage/
  __init__.py
  object_store.py
  r2_store.py

backend/services/queue/
  __init__.py
  client.py
  job_service.py

backend/workers/
  gpu_worker.py
  gpu_tasks.py

backend/api/routes/
  billing.py
  webhooks.py
  preview.py
  uploads.py
  admin.py

backend/core/
  source_url_policy.py
  usage_metering.py

alembic/
  env.py
  versions/...

Dockerfile.api
Dockerfile.gpu
compose.production.yml
```

## Backend — değişecek

```text
requirements.txt
.env.example
backend/config.py
backend/api/server.py
backend/api/routes/jobs.py
backend/api/security.py
backend/api/websocket.py
backend/services/job_state.py
backend/core/orchestrator.py
backend/services/ownership.py
```

## Frontend — yeni/değişecek

```text
frontend/src/pages/LandingPage.tsx
frontend/src/pages/PricingPage.tsx
frontend/src/pages/BillingPage.tsx
frontend/src/pages/PreviewPage.tsx
frontend/src/pages/AdminPage.tsx

frontend/src/components/paywall/Paywall.tsx
frontend/src/components/paywall/PlanCard.tsx
frontend/src/components/billing/UsageMeter.tsx
frontend/src/components/security/TurnstileGate.tsx
frontend/src/components/preview/ViralCandidateCard.tsx

frontend/src/api/billing.ts
frontend/src/api/preview.ts
frontend/src/api/uploads.ts

frontend/src/types/billing.ts
frontend/src/types/preview.ts

frontend/src/App.tsx
frontend/src/app/sections.tsx
frontend/src/app/lazyComponents.ts
frontend/src/config.ts
```

## Tests

```text
backend/tests/test_billing_ledger.py
backend/tests/test_iyzico_webhook.py
backend/tests/test_subscription_service.py
backend/tests/test_risk_engine.py
backend/tests/test_trial_entitlement.py
backend/tests/test_source_url_policy.py
backend/tests/test_job_reservation.py
backend/tests/test_job_worker_contract.py
backend/tests/test_object_store.py
backend/tests/test_authorization_isolation.py
backend/tests/test_admin_audit.py

frontend/src/test/unit/paywall.test.tsx
frontend/src/test/unit/usage-meter.test.tsx
frontend/src/test/integration/preview-paywall-flow.test.tsx
frontend/src/test/integration/billing-flow.test.tsx
```

---

# 5. IMPLEMENTATION TASKS

## Task 1 — Production configuration + dependency foundation

**Files:** `requirements.txt`, `.env.example`, `backend/config.py`, `Dockerfile.api`, `compose.production.yml`.

**Produces:** PostgreSQL/Redis/R2/iyzico/Turnstile config sözleşmesi ve CPU-only API container.

- [x] SQLAlchemy, Alembic, asyncpg, redis, arq, boto3-compatible client ve iyzico HTTP client bağımlılıklarını ekle.
- [x] `.env.example` içine `DATABASE_URL`, `REDIS_URL`, `R2_*`, `IYZICO_*`, `TURNSTILE_*`, `APP_ENV`, `WORKER_MODE` değişkenlerini ekle.
- [x] `backend/config.py` içinde production validation ekle; prod'da eksik secret varsa fail-fast.
- [x] CPU API image'ında Torch/YOLO model yüklemesinin startup'ı gereksiz yere GPU aramamasını garanti et.
- [x] Docker healthcheck: `GET /health/live` ve `GET /health/ready`.
- [x] Test: production config eksik secret ile başlamamalı; dev mod lokal çalışmaya devam etmeli.

**Commit:** `chore: add production runtime foundation`

## Task 2 — PostgreSQL + Alembic

**Files:** `backend/db/*`, `alembic/*`, `backend/tests/test_db_models.py`.

**Produces:** `get_db_session()` async session factory ve ilk schema migration.

- [ ] Önce model constraints için failing tests yaz.
- [ ] UUID PK, unique webhook/payment/idempotency constraints ve FK'leri oluştur.
- [ ] İlk migration'ı oluştur ve boş DB'ye uygula.
- [ ] Migration downgrade/upgrade smoke test çalıştır.
- [ ] Lokal Docker Compose ile DB restart sonrası verinin kaldığını doğrula.

**Commit:** `feat: add postgres persistence model`

## Task 3 — Clerk user sync + authorization isolation

**Files:** `backend/api/security.py`, `backend/api/routes/clerk.py`, `backend/services/ownership.py`, `backend/tests/test_authorization_isolation.py`.

**Produces:** `get_or_create_user(clerk_subject)` ve DB user identity.

- [ ] Valid JWT -> internal `user_id` mapping testi.
- [ ] User A'nın User B project/job/asset endpoint'inden 404 aldığını test et.
- [ ] Admin/support/user role mapping ekle.
- [ ] Admin için step-up/MFA claim kontrolü ekle.
- [ ] Clerk bot protection dashboard ayarını launch checklist'e ekle.

**Commit:** `feat: persist users and enforce ownership`

## Task 4 — Immutable credit ledger

**Files:** `backend/services/billing/ledger.py`, `backend/tests/test_billing_ledger.py`.

**Interfaces:**

```python
async def grant(user_id: UUID, amount: int, idempotency_key: str, metadata: dict) -> None
async def reserve(user_id: UUID, amount: int, job_id: UUID, idempotency_key: str) -> None
async def settle(user_id: UUID, job_id: UUID, actual_amount: int, idempotency_key: str) -> None
async def release(user_id: UUID, job_id: UUID, idempotency_key: str) -> None
```

- [ ] Aynı idempotency key iki kere balance değiştirmemeli.
- [ ] `reserve` DB transaction + row lock ile concurrent overspend'i engellemeli.
- [ ] 100 balance ile eşzamanlı iki `80` reservation'dan yalnız biri başarılı olmalı.
- [ ] Failed/cancelled job reservation release etmeli.
- [ ] Ledger satırları update/delete edilmemeli; düzeltmeler adjustment/refund satırı olmalı.

**Commit:** `feat: add atomic credit ledger`

## Task 5 — Pricing/entitlement engine

**Files:** `backend/services/billing/pricing.py`, `backend/tests/test_pricing.py`.

**Produces:** `estimate_job_cost(request, plan) -> CostEstimate`.

Cost bileşenleri:
- source duration bucket,
- requested clip count,
- resolution,
- premium layout/feature multiplier,
- priority multiplier.

Free preview maliyeti müşteri wallet'ından düşülmez fakat abuse telemetry'ye yazılır.

**Commit:** `feat: add job pricing and entitlements`

## Task 6 — iyzico subscription integration

**Files:** `backend/services/billing/iyzico_client.py`, `subscription_service.py`, `backend/api/routes/billing.py`, tests.

**Produces:** checkout/subscribe, subscription query, cancellation, billing status endpoints.

- [ ] Hosted/payment form kullan; kart detayı backend modeline eklenmesin.
- [ ] Product + pricing-plan reference'larını config/DB ile eşleştir.
- [ ] `POST /api/billing/checkout` yalnız authenticated user için.
- [ ] Frontend'den gelen `success=true` hiçbir entitlement vermemeli.
- [ ] Subscription status yalnız provider query/webhook ile değişmeli.
- [ ] Monthly/yearly plan mapping testleri.

**Commit:** `feat: integrate iyzico subscriptions`

## Task 7 — iyzico webhook V3 + idempotency

**Files:** `backend/api/routes/webhooks.py`, `backend/services/billing/webhook_service.py`, tests.

- [ ] `X-IYZ-SIGNATURE-V3` invalid -> 401/400 ve hiçbir DB mutation yok.
- [ ] Valid event -> `webhook_events` kaydı -> provider state reconcile -> payment/subscription mutation.
- [ ] Aynı webhook 5 kez gelirse yalnız bir credit grant.
- [ ] Webhook body/log içinde secret veya kart verisi yazma.
- [ ] Başarısız recurring payment -> `past_due`, premium entitlement kapanış politikasına göre grace window.

**Commit:** `feat: secure iyzico webhooks`

## Task 8 — Free viral scan

**Files:** `backend/api/routes/preview.py`, `backend/services/preview/*` veya mevcut viral analyzer adapter'ı, frontend PreviewPage.

**Produces:** `POST /api/preview/analyze`.

Akış:
1. URL policy validation.
2. yt-dlp metadata.
3. YouTube captions bulunuyorsa caption kullan.
4. Caption yoksa configurable düşük maliyetli limited transcription.
5. Viral analyzer ile maksimum 3 candidate.
6. Browser preview için timestamps + transcript + visual metadata dön.
7. Final mp4 üretme.

- [ ] Free preview gerçek YOLO/NVENC full render çağırmamalı.
- [ ] Identity başına limit.
- [ ] Max source duration / request frequency limit.
- [ ] Candidate data yalnız owner'a görünmeli.

**Commit:** `feat: add low-cost viral preview funnel`

## Task 9 — Source URL SSRF policy

**Files:** `backend/core/source_url_policy.py`, `backend/tests/test_source_url_policy.py`.

- [ ] Yalnız `https`.
- [ ] İlk v1 allowlist: YouTube hostnames + açıkça desteklenen platformlar.
- [ ] `localhost`, loopback, RFC1918, link-local, IPv6 local ve cloud metadata adresleri reddet.
- [ ] Redirect sonrası destination tekrar validate edilsin.
- [ ] `file://`, `ftp://`, `gopher://` ve custom scheme reddedilsin.
- [ ] URL userinfo (`user:pass@host`) reddedilsin.

**Commit:** `security: enforce source url policy`

## Task 10 — Abuse Risk Engine v1

**Files:** `backend/services/abuse/risk_engine.py`, `trial_service.py`, tests.

Signals v1:
- Clerk bot/human sonucu.
- Turnstile validation.
- Account age.
- Signup/render velocity.
- IP prefix hash velocity (raw IP uzun süre saklanmayacak).
- Known trial identity.
- Disposable/blocked email signal Clerk tarafından.
- Same source fingerprint tekrarları.

Risk kararları:

```text
LOW     -> free scan
MEDIUM  -> Turnstile/extra challenge
HIGH    -> free scan yok; payment required
BLOCK   -> request reject / admin review
```

V1'de agresif browser fingerprinting ve telefon zorunluluğu yok. Bunlar yalnız gerçek abuse verisi gerekirse Phase 2'ye alınacak.

**Commit:** `feat: add abuse risk scoring`

## Task 11 — Cloudflare Turnstile server validation

**Files:** `backend/services/abuse/turnstile.py`, `frontend/src/components/security/TurnstileGate.tsx`, tests.

- [ ] Token server-side doğrulanmadan free scan çalışmasın.
- [ ] Token expiry/replay başarısız olmalı.
- [ ] Production secret frontend'e gitmemeli; yalnız site key public.
- [ ] `/sign-up`, `/preview/analyze` ve riskli request akışlarına challenge bağla.

**Commit:** `security: add turnstile abuse gate`

## Task 12 — Private object storage

**Files:** `backend/services/storage/object_store.py`, `r2_store.py`, `backend/api/routes/uploads.py`, tests.

Interfaces:

```python
async def create_upload_url(user_id, filename, content_type, size_bytes) -> PresignedUpload
async def create_download_url(user_id, asset_id, expires_seconds=600) -> str
async def put_internal(key, file_path, content_type) -> None
async def delete(key) -> None
```

- [ ] Bucket private.
- [ ] User filename storage key olarak kullanılmasın; UUID key.
- [ ] Upload request size/MIME allowlist kontrolü.
- [ ] Upload sonrası ffprobe/media validation worker işi.
- [ ] Signed download URL default 10 dakika.
- [ ] User A user B asset signed URL alamaz.

**Commit:** `feat: add private object storage`

## Task 13 — Redis/ARQ distributed queue

**Files:** `backend/services/queue/client.py`, `job_service.py`, `backend/workers/gpu_worker.py`, `gpu_tasks.py`, tests.

**Produces:** API process'i artık doğrudan `asyncio.create_task(run_gpu_job(...))` ile GPU pipeline çalıştırmayacak.

- [ ] API job'ı PostgreSQL'e `queued` yazar.
- [ ] Credit reservation tamamlanmadan Redis'e job gönderme.
- [ ] Worker `job_id` alır, DB'den request okur.
- [ ] Worker heartbeat ve `started_at` yazar.
- [ ] Worker progress -> `job_events` + pub/sub.
- [ ] Retry yalnız transient sınıflar için; deterministic validation errors retry edilmez.
- [ ] Worker crash sonrası stuck job recovery politikası.

**Commit:** `feat: move gpu jobs to distributed queue`

## Task 14 — Refactor existing jobs route

**Files:** `backend/api/routes/jobs.py`, `backend/services/job_state.py`, websocket manager tests.

- [ ] `/api/start-job` sırası:

```text
auth
→ ownership
→ source validation
→ abuse/entitlement
→ price estimate
→ credit reserve
→ DB job create
→ queue enqueue
```

- [ ] JSON `JobStateRepository` lokal/dev compatibility için kalabilir; production source of truth PostgreSQL.
- [ ] Existing cache hit'te gereksiz credit alınmamalı.
- [ ] Cancel queued job -> queue cancel + reserve release.
- [ ] Cancel processing -> cooperative cancellation; actual consumed amount policy ile settle.

**Commit:** `refactor: route jobs through production job service`

## Task 15 — GPU worker container

**Files:** `Dockerfile.gpu`, worker entrypoint, `.env.example`, runtime validation.

- [ ] CUDA + CTranslate2 + Torch + Ultralytics + ffmpeg NVENC smoke test.
- [ ] `REQUIRE_CUDA_FOR_APP=1` ve `REQUIRE_NVENC_FOR_APP=1` worker'da zorunlu.
- [ ] Whisper model cache volume.
- [ ] YOLO model cache volume.
- [ ] Job başlangıcında source R2'den local NVMe scratch'e indirilir.
- [ ] Render bitince outputs R2'ye yüklenir; temp temizlenir.
- [ ] GPU metrics: model, duration, peak VRAM mümkünse, gpu_seconds.

**Commit:** `feat: add production gpu worker image`

## Task 16 — GPU cost telemetry

**Files:** `backend/core/usage_metering.py`, worker instrumentation, admin API.

Her job için:
- source seconds,
- transcript seconds,
- tracking seconds,
- render seconds,
- total wall time,
- gpu model,
- gpu seconds,
- outputs,
- retry count,
- estimated internal cost.

Dashboard KPI:
- $/source-hour,
- $/Short,
- success rate,
- review_required rate,
- average queue wait,
- average render time.

**Commit:** `feat: meter gpu and job economics`

## Task 17 — Frontend landing + pricing + paywall

**Files:** listed frontend pages/components.

Landing CTA:
- “YouTube linkini yapıştır” ana CTA.
- Ürünün 3 adımlık vaadi.
- örnek before/after.
- pricing.

Paywall trigger:
- Viral candidates gösterildikten sonra.
- “3 güçlü Short bulundu” gerçek veri.
- 1080p/smart tracking/batch/download kilitleri.
- Creator plan visual default/highlight; dark pattern yok.

**Commit:** `feat: add conversion funnel and paywall`

## Task 18 — Billing/usage UI

- [ ] Current plan.
- [ ] Current period usage.
- [ ] Remaining source/compute entitlement.
- [ ] Upgrade/downgrade/cancel.
- [ ] Payment history.
- [ ] Past-due state.
- [ ] Checkout return URL hiçbir zaman payment truth olarak kullanılmamalı; backend status polling/re-fetch yapmalı.

**Commit:** `feat: add billing account experience`

## Task 19 — Security headers + CORS + cookie/session posture

**Files:** `backend/api/server.py`, reverse proxy config, Clerk frontend config.

- [ ] HSTS production.
- [ ] CSP Clerk/Turnstile gerekli originlerle strict allowlist.
- [ ] `X-Content-Type-Options: nosniff` korunur.
- [ ] `frame-ancestors 'none'` / uygun CSP.
- [ ] `Referrer-Policy`.
- [ ] Production CORS yalnız gerçek frontend originleri.
- [ ] Debug docs/admin endpoint exposure policy.
- [ ] Request ID her response/logda.

**Commit:** `security: harden browser and api headers`

## Task 20 — API rate limiting

Edge Cloudflare kuralları:
- `/sign-up`: sıkı.
- `/api/preview/analyze`: sıkı.
- `/api/billing/checkout`: orta.
- `/api/start-job`: user/account limit + edge burst control.
- webhook endpoint: signature-based; Cloudflare block rule provider davranışına zarar vermeyecek.

App-level Redis limits:
- per-user active jobs,
- per-user pending jobs,
- trial scan frequency,
- failed checkout velocity.

**Commit:** `security: add distributed request limits`

## Task 21 — Audit + admin panel

Admin panel:
- users,
- subscriptions,
- jobs,
- failed jobs,
- credit adjustments,
- risk events,
- GPU economics.

Critical actions:
- credit adjustment requires reason,
- user suspend requires reason,
- subscription manual sync,
- retry failed job.

Her kritik işlem `audit_logs` kaydı üretir.

**Commit:** `feat: add audited admin operations`

## Task 22 — Observability

- [ ] Structured JSON production logs.
- [ ] Sentry-compatible error reporting.
- [ ] Health endpoints.
- [ ] DB/Redis/R2 connectivity readiness.
- [ ] GPU worker heartbeat.
- [ ] Queue depth alert.
- [ ] payment webhook failure alert.
- [ ] GPU daily budget alert.
- [ ] disk/temp cleanup alert.

**Commit:** `ops: add production observability`

## Task 23 — CI/CD

Pipeline:

```text
PR
→ backend unit tests
→ frontend lint/test/build
→ security/static checks
→ Docker API build
→ Docker GPU build smoke (without requiring GPU)
→ merge main
→ deploy CPU control-plane
→ worker image publish
→ migration
→ health check
```

Production deploy migration önce backup, sonra Alembic upgrade; health fail olursa app rollback, destructive schema migration v1'de yasak.

**Commit:** `ci: add production build and deploy gates`

## Task 24 — Cloud deployment

### CPU VPS
Docker Compose:
- reverse proxy (Caddy/Nginx),
- API,
- PostgreSQL,
- Redis,
- optional frontend static server.

Firewall:
- 80/443 only public.
- DB/Redis public kapalı.
- SSH key only, password login disabled.

### Cloudflare
- DNS proxy.
- TLS full strict.
- WAF.
- Turnstile.
- rate rules.

### R2
- private bucket.
- lifecycle cleanup.
- CORS only app upload requirements.

### RunPod
- GPU worker container.
- no public product API.
- outbound Redis/DB erişimini mümkünse TLS/tunnel/private path ile sınırla.
- model cache volume.

**Commit:** infrastructure repository/config changes only; provider secrets commit edilmez.

## Task 25 — Launch E2E acceptance suite

Aşağıdaki senaryoların hepsi PASS olmadan “production ready” denmez:

1. Yeni user signup -> Clerk verification -> app.
2. Bot-like signup -> challenge.
3. Free URL -> viral scan -> 3 candidate -> paywall.
4. Free user doğrudan `/api/start-job` çağırır -> denied/payment required.
5. iyzico success redirect olup webhook gelmez -> kredi verilmez.
6. Valid signed webhook -> subscription active + grant exactly once.
7. Aynı webhook 3 kere -> balance bir kez değişir.
8. Paid user job -> credits reserve -> queue -> GPU -> output -> settle.
9. Worker crash -> job recover/retry, double charge yok.
10. Job fail -> unused reserve release.
11. User A, User B job/project/asset -> 404.
12. SSRF `http://127.0.0.1` -> reject.
13. SSRF metadata IP -> reject.
14. Invalid upload masquerading as mp4 -> reject.
15. Signed download URL expires.
16. Admin endpoint normal user -> reject.
17. Admin without MFA/step-up -> reject.
18. Credit admin adjustment -> audit log.
19. Redis unavailable -> readiness fail, job lost olmaz.
20. PostgreSQL restart -> data persists.
21. API restart -> queued job state persists.
22. GPU worker restart -> queue continues.
23. CORS unknown origin -> reject.
24. Secret/log scan -> payment secret/JWT/raw card data yok.
25. End-to-end gerçek video -> 1080p Short downloadable.

---

# 6. AKŞAM UYGULAMA SIRASI / CRITICAL PATH

Aynı oturumda en hızlı canlı beta yolumuz:

```text
A. Branch/worktree
B. Docker production foundation
C. PostgreSQL + migrations
D. Billing ledger
E. iyzico checkout + webhook
F. Free preview/paywall gate
G. Redis distributed queue
H. R2 storage
I. GPU worker container
J. start-job refactor
K. Frontend paywall/billing
L. Cloudflare security
M. Deploy
N. E2E production smoke
```

Bu sıranın nedeni: önce para ve entitlement doğru kurulmadan GPU'yu internete açmıyoruz.

### Beta için zorunlu

- Auth.
- PostgreSQL.
- iyzico.
- immutable credits.
- free preview/paywall.
- Redis queue.
- private storage.
- GPU worker.
- owner isolation.
- webhook idempotency.
- SSRF protection.
- rate limit/Turnstile.
- backups/logging.

### Beta sonrası eklenebilir

- gelişmiş device fingerprint,
- SMS/telefon verification,
- sophisticated identity graph,
- automated multi-GPU autoscaler,
- annual billing optimization experiments,
- enterprise teams,
- referral system,
- affiliate program,
- advanced A/B testing,
- Kubernetes.

---

# 7. ABUSE STRATEJİSİ — EKONOMİK SAVUNMA

Ana prensip: saldırganı %100 tanımaya çalışmak yerine bedava GPU kazancını yok et.

```text
50 hesap açtı
        ↓
Her biri yalnız viral scan aldı
        ↓
Full render? PAYMENT REQUIRED
        ↓
VPN değişimi ekonomik avantaj sağlamıyor
```

V1 free abuse kontrolü:
- Clerk bot protection.
- Turnstile.
- account velocity.
- source fingerprint.
- IP prefix hash velocity.
- trial entitlement identity key.
- free scan cap.
- full render = paid entitlement.

Yüksek riskli ama ödeme yapan kullanıcı otomatik banlanmaz; fraud/payment provider sonucuna ve kullanım kurallarına göre değerlendirilir.

---

# 8. PAYMENT SECURITY

- GodTier hiçbir zaman PAN/CVV saklamaz.
- iyzico hosted/payment form tercih edilir.
- Subscription state backend'de provider state ile reconcile edilir.
- Webhook signature V3 zorunlu.
- Webhook event idempotency DB unique constraint ile zorunlu.
- Checkout request'e server-generated `conversationId`/reference.
- Amount/plan frontend'den güvenilmez; plan code backend'den fiyat çözer.
- Refund/cancel/upgrade backend üzerinden provider API ile yapılır.
- Admin manuel kredi ekleme ödeme kaydı gibi davranmaz; `adjustment` ledger kaydı olur.

---

# 9. DATA & PRIVACY

- Object storage private.
- Raw video retention plan bazlı ve açıkça tanımlı.
- Free kaynakların kısa retention süresi.
- Delete account -> aktif job cancel, sosyal credential purge, scheduled retention delete.
- Logs'ta raw auth token, secret, card, full webhook sensitive payload yok.
- IP'ler abuse için mümkün olduğunca hash/prefix ve kısa retention ile tutulur.
- KVKK/Gizlilik/Kullanım Koşulları launch öncesi yayınlanır; hukuki metinler profesyonel gözden geçirmeye uygundur.

---

# 10. BACKUP / RECOVERY

- PostgreSQL günlük backup + restore testi.
- R2 versioning/lifecycle ihtiyaca göre.
- Redis source of truth değildir; kaybolursa DB'den queued jobs recover edilebilir.
- Payment/webhook source of truth DB + iyzico reconciliation.
- Job state source of truth PostgreSQL.
- GPU local NVMe yalnız scratch/cache.

Recovery hedefi v1:
- API restart: kullanıcı/ödeme/job kaybolmaz.
- Redis restart: queued state DB'den yeniden reconcile edilebilir.
- GPU worker ölümü: job stuck detector retry/release politikası çalışır.

---

# 11. GO-LIVE CHECKLIST

## Product
- [ ] Landing açık.
- [ ] Sign up/sign in çalışıyor.
- [ ] Viral scan çalışıyor.
- [ ] Paywall doğru yerde.
- [ ] Pricing doğru.
- [ ] Checkout çalışıyor.
- [ ] Full render yalnız paid.
- [ ] Download signed URL.

## Payment
- [ ] iyzico production credentials.
- [ ] Monthly plan.
- [ ] Yearly plan.
- [ ] Webhook V3.
- [ ] Duplicate webhook test.
- [ ] Failed renewal test.
- [ ] Cancel test.

## Security
- [ ] Cloudflare proxied.
- [ ] TLS full strict.
- [ ] WAF/rate limits.
- [ ] Turnstile.
- [ ] Clerk bot protection.
- [ ] Admin MFA.
- [ ] CORS allowlist.
- [ ] SSRF tests.
- [ ] Upload validation.
- [ ] R2 private.
- [ ] DB/Redis public değil.
- [ ] secret scan.

## GPU
- [ ] CUDA smoke.
- [ ] NVENC smoke.
- [ ] faster-whisper smoke.
- [ ] YOLO smoke.
- [ ] 1 gerçek end-to-end video.
- [ ] GPU telemetry.
- [ ] cost/job kaydı.

## Ops
- [ ] DB backup.
- [ ] error tracking.
- [ ] health checks.
- [ ] queue depth metric.
- [ ] payment failure alert.
- [ ] daily GPU spend alert.

---

# 12. DEFINITION OF DONE

Production v1 ancak aşağıdaki cümle kesintisiz doğruysa tamamdır:

> Yeni bir kullanıcı gerçek sitede hesap açabiliyor, videosunu ücretsiz düşük maliyetli biçimde analiz ettirip viral adayları görebiliyor; tam üretim istediğinde iyzico ile ödeme yapıyor; doğrulanmış webhook abonelik/kredisini tek sefer tanımlıyor; API krediyi atomik olarak rezerve edip işi Redis üzerinden private NVIDIA GPU worker'a gönderiyor; worker videoyu private object storage üzerinden alıp Whisper/YOLO/NVENC pipeline'ını çalıştırıyor; sonuç yalnız sahibine kısa ömürlü signed URL ile sunuluyor; hata/iptal/tekrar webhook/çoklu hesap/SSRF/yetkisiz erişim senaryoları testlerle kontrol ediliyor ve her job'ın gerçek maliyeti ölçülüyor.

Bu cümledeki herhangi bir halka yoksa sistem “canlı demo” olabilir ama “production SaaS” değildir.

---

# 13. EXECUTION RULES

- Default branch üzerinde doğrudan geliştirme yapılmayacak.
- İzole worktree + `feat/production-saas-v1` branch.
- Task başına test -> implement -> verify -> commit.
- Büyük tek commit yok.
- Her 3-4 task sonunda full backend + frontend verify.
- Payment/GPU/deploy değişikliklerinde ayrı smoke gate.
- Main'e merge ancak E2E acceptance tamamlanınca.
- Production credentials hiçbir commit/issue/log içine yazılmayacak.
