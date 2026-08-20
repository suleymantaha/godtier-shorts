---
name: shipping-godtier-saas
description: Use when changing GodTier Shorts in ways that affect production deployment, monetization, payments, credits, free-trial behavior, abuse prevention, storage, queues, GPU workers, authentication, authorization, cost control, or launch readiness.
---

# Shipping GodTier SaaS

## Overview

Ship GodTier Shorts as a profitable SaaS without sacrificing security, gross margin, reliability, or output quality.

**Core principle:** expensive compute starts only after entitlement is proven, abuse risk is accepted, and usage/cost is atomically reserved.

Use test-driven development for code changes, systematic debugging for failures, and verification before claiming completion.

Read `references/production-contract.md` when work touches billing, abuse, GPU execution, queues, storage, pricing or deployment. If present, also read `docs/superpowers/plans/2026-08-20-godtier-shorts-production-v1.md` before architectural changes.

## Non-Negotiables

- Show useful free analysis/preview; do not make expensive full production the default free trial.
- Browser state is never authoritative for payment, credits, roles, prices or permissions.
- Verified provider webhook/event is authoritative for paid entitlement; handlers are signature-verified and idempotent.
- Reserve credits/usage before queueing GPU work; settle/release afterward.
- PostgreSQL is durable source of truth. Redis is dispatch/coordination, not permanent accounting.
- Long GPU work does not run inside the public FastAPI process.
- GPU workers are private; object storage is private; downloads use ownership-checked signed URLs.
- User URLs require SSRF protection; uploads require size/type/media validation.
- Abuse decisions combine signals. IP or VPN alone never proves identity.
- High-risk users may lose free entitlement without being automatically banned from legitimate paid use.
- Select GPU by measured cost per successful workload, not prestige.
- Record per-job COGS signals before finalizing pricing.
- Do not use fake scarcity, hidden charges, misleading previews, or other dark patterns.

## Required Job Gate

```text
auth
→ validate
→ entitlement
→ abuse/risk
→ quota/concurrency
→ atomic reservation
→ durable job
→ distributed queue
→ GPU worker
→ private storage
→ settlement
```

Never enqueue first and validate later.

## Red Flags — Stop

- “React says payment succeeded, add credits.”
- “Run the GPU job with asyncio.create_task for production.”
- “Make the bucket public; easier.”
- “Give full 1080p renders free; abuse can wait.”
- “Block all VPN users.”
- “Charge credits after rendering.”
- “Use H100 because it is fastest.”
- “Add security/cost telemetry after MVP.”

## Completion Definition

A production change is complete only when tests cover authorization/ownership, retry/idempotency and failure settlement; costly work cannot bypass entitlement/reservation; cost telemetry is recorded; secrets stay out of code/logs; and full verification passes with observed output.

## Skill Verification

Before deployment, run the pressure scenarios in `references/production-contract.md` first without this skill and then with it. Do not call the skill verified until the expected decisions are consistent.
