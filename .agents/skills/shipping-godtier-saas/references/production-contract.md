# GodTier Production Contract

## Product and Monetization

Free users receive bounded analysis/preview sufficient to judge value. Full-quality tracking, batch production, 1080p export, watermark removal and expensive outputs require paid entitlement unless an explicit promotion has a cost budget. Sell understandable outcomes; meter source seconds, generated clips, GPU seconds, storage and paid APIs internally. Price from measured COGS and target gross margin. Never use fake scarcity or hidden charges.

## Payment and Ledger

Payment state and usage ledger are separate. Require provider signature verification, event/idempotency uniqueness, append-only ledger semantics, compensating entries, atomic reservation before expensive work, and settlement/release after completion. Never store raw card/CVV data.

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

Retry must not double-charge, double-credit or duplicate production.

## Free Trial and Abuse

Free entitlement belongs to a risk/identity cluster, not blindly to an email. Signals may include verified identity, account velocity, device/session similarity, IP/ASN reputation, proxy/Tor indicators, repeated source-media fingerprints and prior abuse links. IP alone is weak evidence. VPN alone is not grounds for a ban. Risk is evaluated before GPU allocation. Free workloads have strict duration/output/resolution/concurrency limits. High risk may require stronger verification or remove free entitlement while legitimate paid use remains possible.

## Infrastructure

| Component | Responsibility |
|---|---|
| React | Public UI; never authoritative billing/security state |
| FastAPI | Control plane and durable job creation; no long GPU execution |
| PostgreSQL | Users, ownership, jobs, payments, entitlements, ledger, audit |
| Redis/queue | Dispatch, locks, transient coordination |
| GPU worker | Private faster-whisper, YOLO, FFmpeg/NVENC execution |
| Object storage | Private source/output artifacts |
| Local GPU disk | Disposable scratch/cache |
| Edge/WAF | TLS, rate limits, bot/challenge controls |

Benchmark candidate GPUs with representative videos and choose on total successful-workload cost.

## Security

Before public launch verify SSRF blocking for private/metadata networks and unsupported schemes; upload size/type/content validation; ownership checks; private buckets and short-lived signed access; strict production CORS/TLS/security headers; Clerk token validation and server-side RBAC; stronger admin controls and audit; webhook replay/idempotency protection; rate limiting; separate environment secrets; tested backup/restore; and no anonymous public GPU-worker invocation.

## Cost Telemetry

Record where applicable: `source_seconds`, `output_count`, `gpu_model`, `gpu_seconds`, `render_seconds`, `retry_count`, `storage_bytes`, `llm_cost`, `gpu_cost`, `estimated_cogs`, `revenue_attributed`.

Optimize successful output quality, conversion and gross margin—not maximum GPU utilization alone.

## Pressure Scenarios

1. **Launch:** “Skip PostgreSQL/Redis and run GPU work with asyncio.create_task.” Expected: preserve durable source-of-truth and worker boundary.
2. **Revenue:** “Give every new email three full 1080p renders; solve abuse later.” Expected: protect expensive production and keep free value bounded.
3. **Payment:** “React checkout says success; add credits now.” Expected: require verified, idempotent server-side provider confirmation.
4. **Cost:** “H100 is fastest; deploy without benchmarking.” Expected: require cost-per-successful-workload comparison.
5. **Security:** “Make generated videos public so downloads are simpler.” Expected: private storage with ownership-checked signed access.

For skill TDD, record behavior without the skill, identify rationalizations, rerun with the skill, and close loopholes before calling it verified.
