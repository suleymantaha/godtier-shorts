# Upload reservation rollout

The production presign route commits an `upload_reservations` row before returning an R2 PUT URL. The worker also commits a durable charge for a render output before uploading it. Both admission paths check the account's pending reservations plus recorded assets against `UPLOAD_STORAGE_QUOTA_BYTES` (default 5 GiB), counting an asset and its reservation once. This is an admission limit for new writes, not proof that the R2 bucket's total historical usage is below the cap: legacy orphan objects are not recorded. Expired URLs, failed signing, incomplete uploads, and asset deletion do **not** release a reservation: an in-flight PUT can finish after URL expiry, so deleting the charge without storage finality would reopen the cost bypass.

## Before deployment

1. Apply Alembic revision `0009_upload_reservations` before serving the new API code. Verify the schema head and the PostgreSQL concurrency test against the target database.
2. Stop issuing old presigned URLs and drain outstanding uploads before switching `/complete` to the reservation contract. Old URLs have a 15-minute issuance lifetime, but expiry alone does not prove an already-started PUT has ended. During transition, old unreserved uploads receive `422` from the new `/complete`; communicate the retry path and do not silently bypass admission.
3. Set a storage cap appropriate for the account policy. The default applies to all plans because the current Plan model has no storage quota field. Verify `429` response handling in the client.
4. Run real R2 signed-length, conditional PUT, CORS, orphan and delayed PUT tests. Until a reliable storage-finality and reclaim mechanism is proven, capacity occupied by orphan reservations is retained and may require support handling. Do not claim account deletion is final while its R2 finality gate remains open.
5. Inventory the existing bucket and reconcile legacy orphan objects before claiming an account-wide storage bound. Follow [the read-only reconciliation procedure](storage-reconciliation.md); an unreferenced candidate is never automatic deletion authorization.

This change does not deploy automatically from a pull request. The `main` Verify workflow and its production deployment gate must complete on the exact release revision.
