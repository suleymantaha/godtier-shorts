# GodTier Shorts Production v1 — Execution Plan

**Goal:** turn the existing GodTier Shorts pipeline into a secure, measurable, paid production SaaS while keeping expensive GPU compute behind entitlement, risk and atomic usage reservation.

## Architecture Contract

```text
Cloudflare
  → React + Clerk
  → FastAPI control plane
      → PostgreSQL (source of truth)
      → Redis distributed queue
      → private NVIDIA GPU workers
      → private object storage
      → iyzico payment/webhook integration
```

The public API does not execute long GPU work in-process. Browser payment state is never authoritative. PostgreSQL owns durable jobs/accounting; Redis coordinates work only.

## Execution Order

### Phase 0 — Repository guardrails
- Keep production work isolated on `feat/production-saas-v1`.
- Install/use `.agents/skills/shipping-godtier-saas/` for production decisions.
- Never commit real secrets; keep `.env.example` placeholders only.
- Add/maintain production readiness checklist.

### Phase 1 — Persistence foundation
- Add PostgreSQL configuration and SQLAlchemy/Alembic migrations.
- Create durable models for users, subscriptions, entitlements, jobs, job events, usage reservations, immutable ledger entries, assets, payment events and audit events.
- Add ownership constraints and indexes.
- Tests first: migration, ownership isolation, atomic reservation and duplicate idempotency key.

### Phase 2 — Usage/credit ledger
- Implement append-only credit/usage ledger.
- Reserve estimated usage before enqueue.
- Settle actual usage on success and release eligible reservation on failure.
- Prevent concurrent overspend.
- Tests first: two simultaneous jobs cannot spend the same balance; retries cannot double-settle.

### Phase 3 — Distributed jobs
- Add Redis-backed queue/coordination.
- Refactor current GPU pipeline into a private worker entrypoint.
- API creates durable job then enqueues ID; worker loads job from PostgreSQL.
- Add retry/dead-letter semantics and heartbeats.
- Tests first: API restart does not lose durable job; duplicate delivery is idempotent.

### Phase 4 — Private object storage
- Add storage abstraction suitable for Cloudflare R2/S3-compatible storage.
- Use server-generated object keys, private buckets, short-lived upload/download URLs and ownership checks.
- Local worker disk is scratch only.
- Validate upload size/type/media before production.
- Tests first: user A cannot sign/download user B asset; expired URL path cannot bypass auth.

### Phase 5 — Free analysis → paywall
- Free path performs bounded, cost-controlled analysis/preview.
- Return candidate viral segments, hooks/transcript/score and limited preview.
- Full-quality YOLO tracking, subtitle burn, 1080p export and batch generation require paid entitlement.
- Apply strict source-duration/output/concurrency caps.
- Tests first: free account cannot reach paid production endpoint by modifying frontend state.

### Phase 6 — Abuse risk
- Create `AbuseRiskService` interface and decision record.
- Initial signals: account velocity, IP/ASN risk, proxy/Tor signal where available, repeated source fingerprint, prior entitlement use, verification state.
- Do not hard-ban solely for IP/VPN.
- Risk decision happens before reservation/queue.
- Tests first: repeated free entitlement cluster is denied/challenged without blocking valid paid entitlement.

### Phase 7 — iyzico billing
- Add plans/subscriptions/payment events.
- Checkout/session creation is server-owned.
- Verify provider signature/webhook and store unique provider event ID.
- Activate entitlement/credit only after verified server-side payment confirmation.
- Webhook retries must be idempotent.
- Never store card/CVV data.
- Tests first: forged frontend success grants nothing; duplicate webhook grants once.

### Phase 8 — Production security
- Cloudflare edge/TLS/WAF/Turnstile/rate limits for signup, free analysis, checkout and job creation.
- SSRF defense for user-provided URLs including private/link-local/cloud-metadata ranges and redirect revalidation.
- Strict production CORS/security headers.
- Clerk token verification and server-side RBAC; stronger admin controls.
- Append-only security/admin audit events.
- Tests first for SSRF and cross-user ownership.

### Phase 9 — Cost telemetry and pricing evidence
Every production job records, where applicable:
- source seconds
- output count
- GPU model and GPU seconds
- render seconds
- retry count
- storage bytes
- LLM/API cost
- estimated GPU cost / total COGS
- attributed revenue

Benchmark representative real videos on candidate GPUs. Choose by cost per successful workload and output quality, not peak speed.

### Phase 10 — Product surfaces
- Landing page and free analysis entry.
- Preview/results → paywall.
- Pricing, checkout, billing/subscription management.
- Projects/jobs, progress, output download.
- Usage meter and plan limits.
- Admin: queue, failed jobs, abuse decisions, payments, COGS/gross margin.

### Phase 11 — Operations
- Structured logs and request/job correlation IDs.
- Error monitoring and uptime checks.
- Database backups with tested restore.
- Object retention/deletion policy.
- Staging separated from production secrets/data.
- Runbook for payment outage, queue outage, GPU capacity outage and failed render.

## Go-Live Gate

Do not launch until a real end-to-end path succeeds:

```text
signup
→ free bounded analysis
→ preview/paywall
→ real/sandbox-equivalent verified payment flow
→ entitlement/usage reservation
→ durable queue
→ private GPU worker
→ Whisper/YOLO/NVENC production
→ private storage
→ ownership-checked signed download
→ usage settlement + COGS telemetry
```

Also require passing tests for duplicate webhooks, concurrent credit spend, cross-user access, SSRF, worker retry/idempotency and failure reservation release.

## External Readiness

Before public launch ensure: domain/DNS, Cloudflare account and R2, Clerk production app, iyzico merchant/sandbox/production credentials, GPU provider account, representative benchmark video, production support/billing/security email aliases, privacy/KVKK/terms/refund documents, and production secret inventory. Do not put secret values in this document or Git.

## Definition of Done

Production v1 is complete when a paying user can safely purchase entitlement, submit a source, survive API/worker retries without duplicate charges or work, receive a high-quality private output, and the operator can see the true cost and audit trail of that transaction.
