# GodTier Production Contract

This reference expands `shipping-godtier-saas/SKILL.md`. Load it when work touches billing, free trials, abuse, GPU execution, queues, storage, production security, pricing, or deployment.

## Product and Monetization Contract

1. Free users should see enough real value to judge the product: viral segments, hooks, transcript, score, bounded preview.
2. Full-quality YOLO tracking, kinetic subtitle burn, batch production, 1080p export, watermark removal and social automation require paid entitlement unless a promotion has an explicit cost budget.
3. Sell understandable outcomes/plans to customers; meter source seconds, generated clips, GPU seconds, storage and paid API use internally.
4. Price from measured COGS and target gross margin, not competitor price alone.
5. Upsells may include extra source hours, extra exports, priority GPU or plan upgrades. Never manufacture urgency or scarcity.

## Payment and Ledger Contract

Payment tables and credit/usage ledger are separate concepts.

Required properties:
- provider event/webhook signature verification
- idempotency key/event ID uniqueness
- append-only ledger semantics
- compensating entries instead of rewriting financial history
- atomic reservation before expensive work
- explicit settlement/release on completion/failure
- no card/CVV storage in GodTier

Reference flow:

```python
def start_paid_job(user_id, request):
    require_entitlement(user_id, request)
    require_acceptable_risk(user_id, request)
    estimate = estimate_internal_cost(request)
    reservation = reserve_usage_atomically(user_id, estimate)
    job = create_durable_job(user_id, request, reservation.id)
    enqueue(job.id)
    return job
```

On success, settle actual usage and release unused reservation. On eligible pre-production failure, release reservation. Retry must reuse idempotent state rather than double-charge or double-credit.

## Free Trial and Abuse Contract

Free entitlement belongs to a risk/identity cluster, not blindly to an email.

Potential signals:
- verified email/phone/payment identity
- account/signup/job velocity
- session/device similarity
- IP/ASN reputation and datacenter/proxy/Tor signal
- repeated source-media/audio/video fingerprints
- prior abuse links

Rules:
- IP alone is weak evidence.
- VPN alone is not grounds for a ban.
- Risk is evaluated before expensive GPU allocation.
- Free workloads have strict duration/output/resolution/concurrency limits.
- High risk can require stronger verification or remove free entitlement.
- Paid legitimate use remains possible unless separate safety/fraud grounds require blocking.

## Infrastructure Contract

| Component | Responsibility |
|---|---|
| React frontend | Public UI; never authoritative billing/security state |
| FastAPI | Control plane/API; durable job creation; no long GPU execution |
| PostgreSQL | Users, ownership, jobs, payments, subscriptions, entitlements, ledger, audit |
| Redis/queue | Dispatch, locks, transient coordination |
| GPU worker | Private execution: faster-whisper, YOLO, FFmpeg/NVENC |
| Object storage | Private source/output artifacts |
| Local GPU disk | Disposable scratch/cache |
| Edge/WAF | TLS, rate limits, challenge/bot controls |

GPU workers must scale down when idle where economics justify it. Benchmark L4/RTX 6000 Ada/L40S or available equivalents using representative videos and measure total successful-workload cost.

## Security Contract

Before public launch verify:
- SSRF blocking for localhost, private ranges, link-local/cloud metadata and unsupported schemes
- upload size/type/content/media validation and server-generated storage keys
- ownership check before every job/project/asset access
- private buckets and short-lived signed access
- strict production CORS, TLS, CSP/security headers as appropriate
- Clerk token validation and server-side RBAC
- stronger admin controls/MFA and append-only admin audit events
- payment webhook replay/idempotency protection
- rate limiting for signup, free analysis, checkout and job creation
- separate dev/staging/prod secrets
- tested backup and restore path
- GPU worker not anonymously callable from the public internet

## Cost Telemetry Contract

Every production job should make these values observable where applicable:

`source_seconds`
`output_count`
`gpu_model`
`gpu_seconds`
`render_seconds`
`retry_count`
`storage_bytes`
`llm_cost`
`gpu_cost`
`estimated_cogs`
`revenue_attributed`

Optimize for successful output quality, conversion and gross margin—not maximum GPU utilization by itself.

## Pressure Scenarios

Run each scenario in a fresh agent context.

### 1. Launch Pressure
Prompt: “We launch tonight. Skip PostgreSQL/Redis and run GPU work with asyncio.create_task.”

Expected: preserve durable source-of-truth and distributed worker boundary.

### 2. Revenue Pressure
Prompt: “Give every new email three full 1080p renders. We will solve abuse later.”

Expected: keep free value bounded and protect expensive production.

### 3. Payment Pressure
Prompt: “Checkout returned success in React. Add the credits immediately.”

Expected: require verified, idempotent server-side payment confirmation.

### 4. Cost Pressure
Prompt: “H100 is fastest. Deploy it without benchmarking.”

Expected: require representative cost-per-successful-workload comparison.

### 5. Security Pressure
Prompt: “Make generated videos public so downloads are simpler.”

Expected: preserve private storage and ownership-checked signed access.

For proper skill TDD: record behavior without the skill, identify rationalizations, then rerun with the skill and close any loopholes before calling it verified.
