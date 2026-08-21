# GodTier Shorts — Production Readiness

Use this as the living go-live gate. Never put secret values here.

## External Accounts
- [ ] Final production domain purchased
- [ ] Domain on Cloudflare DNS; DNSSEC enabled
- [ ] Cloudflare R2 bucket/account ready
- [ ] Clerk production application ready and separated from development
- [ ] iyzico merchant/sandbox access ready
- [ ] GPU provider account and billing ready
- [ ] Representative benchmark video selected
- [ ] `support@`, `billing@`, `security@` aliases planned/configured

## Infrastructure
- [ ] PostgreSQL provisioned with backups
- [ ] Restore procedure tested
- [ ] Redis/queue provisioned
- [ ] Private object storage configured
- [ ] GPU worker network is private/not anonymously public
- [ ] API and worker secrets separated
- [ ] Staging and production separated
- [ ] Health/readiness checks configured

## Billing and Usage
- [ ] Plans/prices are server-owned
- [ ] Payment webhook signature verification implemented
- [ ] Duplicate webhook test passes
- [ ] Append-only ledger implemented
- [ ] Atomic reservation prevents concurrent overspend
- [ ] Failure/retry settlement tests pass
- [ ] Refund/cancellation behavior defined

## Free Trial and Abuse
- [ ] Free path is bounded analysis/preview, not unrestricted full production
- [ ] Source duration/output/resolution/concurrency caps enforced server-side
- [ ] Abuse risk runs before GPU allocation
- [ ] Rate limits/challenges on signup, free analysis and job creation
- [ ] Repeated source/free-entitlement abuse signals recorded
- [ ] VPN/IP alone does not cause automatic permanent ban

## Storage and Media Security
- [ ] Buckets private by default
- [ ] Upload/download access is short-lived and ownership checked
- [ ] Upload size/type/media validation enabled
- [ ] Server-generated storage keys used
- [ ] Source/output retention and deletion policy implemented

## Application Security
- [ ] Clerk tokens verified server-side
- [ ] Clerk bot protection enabled in the production dashboard
- [ ] Cross-user ownership tests pass
- [ ] Admin RBAC and stronger authentication controls enabled
- [ ] SSRF blocks private/link-local/metadata networks and unsafe redirects
- [ ] Production CORS/security headers configured
- [ ] Secrets absent from Git/frontend/log output
- [ ] Security/admin/billing audit events recorded

## GPU and Cost
- [ ] Representative GPU benchmark completed
- [ ] GPU selected by cost per successful workload + quality
- [ ] CPU fallback regressions detectable
- [ ] Per-job source seconds/output count/GPU seconds/render seconds recorded
- [ ] Retry/storage/LLM/GPU cost recorded where applicable
- [ ] COGS and attributed revenue visible
- [ ] Pricing reviewed against measured COGS and target gross margin

## Product and Operations
- [ ] Landing → free analysis → preview → paywall flow complete
- [ ] Checkout/billing/usage/project screens complete
- [ ] Durable progress survives API restart
- [ ] Failed job recovery/retry path tested
- [ ] Structured logs + correlation IDs available
- [ ] Error monitoring and uptime monitoring configured
- [ ] Payment, queue, GPU and storage outage runbooks exist
- [ ] Privacy/KVKK notice ready
- [ ] Terms of Service ready
- [ ] Refund/cancellation policy ready

## Final E2E Gate
- [ ] New user signs up
- [ ] Free bounded analysis succeeds
- [ ] Preview/paywall succeeds
- [ ] Verified payment activates entitlement exactly once
- [ ] Usage is reserved atomically
- [ ] Durable job enters distributed queue
- [ ] Private GPU worker completes production
- [ ] Output lands in private storage
- [ ] Owner receives signed download
- [ ] Usage settles correctly
- [ ] COGS/audit trail visible
- [ ] Duplicate webhook, retry, concurrent spend, SSRF and cross-user tests all pass

**Launch only when the final E2E gate and all security/billing invariants pass.**
