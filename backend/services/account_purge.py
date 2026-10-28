"""Delete subject-owned runtime data while preserving security/audit logs."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from loguru import logger

import backend.config as config
from backend.db.models import Asset, Job, JobStatus, Project, Subscription, SubscriptionStatus, User, UserStatus
from backend.db.session import get_session_factory
from backend.api.websocket import manager
from backend.services.ownership import build_subject_hash, scrub_support_grants_for_subject
from backend.services.social.store import get_social_store
from backend.services.storage.object_store import DEFAULT_UPLOAD_URL_EXPIRES_SECONDS


def _delete_subject_projects(subject_hash: str) -> int:
    subject_dir = config.get_subject_projects_dir(subject_hash)
    if not subject_dir.exists():
        return 0

    deleted_projects = sum(1 for child in subject_dir.iterdir() if child.is_dir())
    shutil.rmtree(subject_dir)
    config.get_subject_projects_dir(subject_hash)
    return deleted_projects


async def purge_subject_data(subject: str) -> dict:
    normalized_subject = (subject or "").strip()
    if not normalized_subject:
        raise ValueError("subject boş olamaz")

    production = (
        os.getenv("APP_ENV", "development").strip().lower() == "production"
        or os.getenv("WORKER_MODE", "local").strip().lower() == "distributed"
        or bool(os.getenv("DATABASE_URL", "").strip())
    )
    durable = await _purge_production(normalized_subject) if production else None
    if durable and not durable.get("deletion_fenced"):
        return durable

    subject_hash = build_subject_hash(normalized_subject)
    deleted_projects = _delete_subject_projects(subject_hash)
    deleted_social_rows = get_social_store().purge_subject_data(normalized_subject)
    cancelled_jobs = manager.purge_subject_jobs(normalized_subject)
    closed_websockets = await manager.close_subject_connections(normalized_subject)
    scrubbed_grants = scrub_support_grants_for_subject(normalized_subject)

    summary = {
        "deleted_projects": deleted_projects,
        "deleted_social_rows": deleted_social_rows,
        "cancelled_jobs": cancelled_jobs,
        "closed_websockets": closed_websockets,
        "scrubbed_grants": scrubbed_grants,
    }
    return {**summary, **durable} if durable else summary


@asynccontextmanager
async def _production_remote():
    import boto3
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.jobs import Job as ArqJob, JobStatus as ArqStatus

    client = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
    bucket = os.environ["R2_BUCKET_NAME"]
    try:
        pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
    except Exception:
        client.close()
        raise

    class Remote:
        async def cancel(self, key):
            job = ArqJob(key, pool)
            state = await job.status()
            if state in {ArqStatus.not_found, ArqStatus.complete}:
                return False
            if not await job.abort(timeout=5):
                raise RuntimeError("Queue cancellation was not acknowledged")
            return True

        async def keys(self, prefix):
            def collect():
                pages = client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
                return [entry["Key"] for page in pages for entry in page.get("Contents", [])]
            return await asyncio.to_thread(collect)

        async def delete(self, key):
            await asyncio.to_thread(client.delete_object, Bucket=bucket, Key=key)

    try:
        yield Remote()
    finally:
        try:
            await pool.aclose()
        finally:
            client.close()


async def _purge_production(subject: str) -> dict:
    """Fence admission durably; retry external cleanup without erasing accounting."""
    pending = {"status": "deletion_pending", "reason": "cleanup_unavailable", "deletion_fenced": False}
    try:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            user = await session.scalar(select(User).where(User.clerk_subject == subject).with_for_update())
            if user is None:
                return {**pending, "reason": "identity_unavailable"}
            subscription = await session.scalar(select(Subscription.id).where(
                Subscription.user_id == user.id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING, SubscriptionStatus.PAST_DUE])))
            if subscription:
                return {**pending, "reason": "subscription_cancellation_required"}
            if user.status not in {UserStatus.ACTIVE, UserStatus.DELETED}:
                return {**pending, "reason": "identity_unavailable"}
            user.status = UserStatus.DELETED
            user.deletion_requested_at = user.deletion_requested_at or datetime.now(timezone.utc)
            user.email_normalized = None
            user_id, requested = user.id, user.deletion_requested_at
        pending["deletion_fenced"] = True
        async with factory() as session:
            jobs = list(await session.scalars(select(Job).where(Job.user_id == user_id)))
            assets = list(await session.scalars(select(Asset).where(Asset.user_id == user_id)))
        prefixes = (f"uploads/{user_id}/", f"outputs/{user_id}/")
        if any(not asset.storage_key.startswith(prefixes) for asset in assets):
            return {**pending, "reason": "storage_ownership_conflict"}
        async with _production_remote() as remote:
            for job in jobs:
                acknowledged = await remote.cancel(f"gpu:{job.id}")
                if job.status in {JobStatus.QUEUED, JobStatus.PROCESSING}:
                    # Missing queue metadata does not prove a running worker stopped.
                    if not acknowledged:
                        return {**pending, "reason": "worker_stop_unverified"}
                    async with factory() as session, session.begin():
                        await session.scalar(select(User).where(User.id == user_id).with_for_update())
                        await session.execute(update(Job).where(Job.id == job.id, Job.user_id == user_id).values(
                            status=JobStatus.CANCELLED, finished_at=datetime.now(timezone.utc)))
            from backend.services.billing import ledger
            async with factory() as session:
                cancelled = list(await session.scalars(select(Job).where(
                    Job.user_id == user_id, Job.status == JobStatus.CANCELLED, Job.reserved_credits > 0)))
            for job in cancelled:
                if job.started_at is None:
                    await ledger.release(user_id, job.id, f"release:cancel:{job.id}")
                else:
                    await ledger.settle(user_id, job.id, job.reserved_credits, f"settle:cancel:{job.id}")
            requested = requested.replace(tzinfo=timezone.utc) if requested.tzinfo is None else requested
            remaining = DEFAULT_UPLOAD_URL_EXPIRES_SECONDS - (datetime.now(timezone.utc) - requested).total_seconds()
            if remaining > 0:
                return {**pending, "reason": "upload_url_expiry", "retry_after_seconds": int(remaining) + 1}
            keys = set(asset.storage_key for asset in assets)
            for prefix in prefixes:
                keys.update(await remote.keys(prefix))
            for key in keys:
                if not key.startswith(prefixes):
                    return {**pending, "reason": "storage_ownership_conflict"}
                if key.startswith(prefixes[0]):
                    digest = hashlib.sha256(f"{user_id}:{key}".encode()).hexdigest()
                    await remote.cancel(f"validate:{digest}")
                await remote.delete(key)
            for prefix in prefixes:
                if await remote.keys(prefix):
                    return {**pending, "reason": "storage_not_empty"}
        # Retain User/Project/Job FK skeletons, ledger, billing, usage and audit history.
        async with factory() as session, session.begin():
            await session.scalar(select(User).where(User.id == user_id).with_for_update())
            await session.execute(delete(Asset).where(Asset.user_id == user_id))
            await session.execute(update(Project).where(Project.user_id == user_id).values(
                source_ref="", source_fingerprint="", title=None, duration_seconds=None))
            await session.execute(update(Job).where(Job.user_id == user_id).values(
                request={}, last_message=None, error_message=None))
        # R2 cannot revoke issued PUTs or prove an upload started before expiry has ended.
        # Keep the fence and retryability; never assert verified completion from an empty list.
        return {**pending, "reason": "storage_finalization_unverified"}
    except Exception as exc:
        logger.warning("event=account_purge_pending error_type={}", type(exc).__name__)
        if not pending["deletion_fenced"]:
            try:
                async with get_session_factory()() as session:
                    user = await session.scalar(select(User).where(User.clerk_subject == subject))
                    pending["deletion_fenced"] = bool(
                        user and user.status is UserStatus.DELETED and user.deletion_requested_at)
            except Exception as recovery_error:
                logger.warning("event=account_purge_fence_unavailable error_type={}", type(recovery_error).__name__)
        return pending
