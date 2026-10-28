# Read-only legacy storage reconciliation

The `upload_reservations` table is now the durable storage charge ledger for both
presigned uploads and worker outputs. Existing Assets count until a matching
charge exists; retrying a legacy output adds its durable charge without counting
it twice. No migration can reconstruct objects whose Asset was already removed,
or browser uploads created before durable reservations existed. Those require an
object inventory. Expiry alone is never evidence that a remote write is final.

## Safe inventory procedure (not executed against live R2)

1. Use explicitly approved read-only database and R2 credentials. Record snapshot
   timestamps, bucket, scope, pagination continuation and total listed bytes in a
   local restricted report. Never record credentials or signed URLs.
2. Export both `uploads/` and `outputs/` namespaces through paginated
   `ListObjectsV2`, at most 1,000 keys per request. Choose a bounded account/prefix
   per run. Preserve Key, Size, LastModified, ETag and continuation metadata.
   Separately inventory multipart uploads/parts; ListObjectsV2 excludes them.
   Do not abort multipart uploads or delete objects during inventory.
3. Export a complete database reference manifest for the same scope inside a
   `REPEATABLE READ READ ONLY` transaction. Include **both** Assets and all durable
   reservations, including expired reservations and deleted-account charges:

   ```sql
   SELECT storage_key AS key, size_bytes FROM assets
   UNION
   SELECT storage_key AS key, size_bytes FROM upload_reservations;
   ```

   Filter both SELECT branches to the same reviewed user/prefix for large
   accounts. Export as JSONL objects with `key` and integer `size_bytes`.
   Never filter reservations by expiry; never use only successful jobs/Assets.
4. Convert the object manifest to the same JSONL fields, preserving the original
   richer inventory separately, and run the offline comparator:

   ```sh
   python scripts/storage_orphan_inventory.py --objects objects.jsonl --references references.jsonl --max-objects 10000 --max-references 100000 > inventory.jsonl
   ```

   This tool never contacts R2 or the database, and never changes charges or
   source manifests. It fails on invalid/conflicting data or row limits before
   emitting output. Treat a nonzero exit as incomplete inventory.
5. Review `size_mismatch` and `unknown_namespace` separately. An
   `unreferenced_candidate` is only absent from the supplied reference snapshot.
   It is **not** safe to delete: incomplete scopes, a later reservation, active
   writers, old presigned PUTs, retries and multipart writes remain possible.
   Repeat the complete inventory and recheck current DB references and remote
   metadata before any separately authorized reconciliation.

## Acceptance limits

No live R2 inventory or legacy charge backfill was performed here. The comparator
cannot prove remote finality, ownership, absence of concurrent writes, complete
pagination, absence of multipart uploads, or which historical user was billed.
A deletion/charge-release workflow requires separate authorization and a proven
writer fence/finality policy; this procedure deliberately provides neither.
