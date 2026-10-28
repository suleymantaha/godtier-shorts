from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from backend.db.models import Job, JobStatus
from backend.tests.test_output_storage_accounting import postgres, scenario


@pytest.mark.integration
def test_postgres_post_render_quota_failure_charges_once_and_stays_failed(postgres, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.db.models import CreditLedgerEntry, CreditWallet, LedgerKind
    from backend.services.billing import ledger
    from backend.workers import gpu_tasks, gpu_worker

    async def check(factory, repo, kwargs, reserve, uploaded):
        for module in (ledger, gpu_tasks, gpu_worker):
            monkeypatch.setattr(module, "get_session_factory", lambda: factory)
        context = kwargs["context"]
        await ledger.grant(context.user_id, 100, "grant", {})
        await ledger.reserve(context.user_id, 20, context.job_id, "reserve")
        await reserve(10)
        events = []
        async def runner(request, report):
            events.append("pipeline_finished")
            await repo.publish_output(**kwargs)
        store = gpu_tasks.SqlAlchemyWorkerJobStore()
        await gpu_tasks.GpuJobWorker(store, SimpleNamespace(publish_progress=AsyncMock()), runner).execute(context.job_id)
        async with factory() as session:
            job = await session.get(Job, context.job_id)
            wallet = await session.get(CreditWallet, context.user_id)
            assert (wallet.available, wallet.reserved, job.reserved_credits, job.settled_credits) == (80, 0, 0, 20)
            assert job.status is JobStatus.ERROR
            assert job.error_code == "OUTPUT_STORAGE_QUOTA_EXCEEDED"
            assert "storage limit" in job.error_message.lower()
            assert "credits were charged" in job.error_message
            entries = (await session.scalars(select(CreditLedgerEntry))).all()
            assert sum(row.kind is LedgerKind.SETTLE for row in entries) == 1
            assert sum(row.kind is LedgerKind.RELEASE for row in entries) == 0
        # Lost acknowledgement/replayed failure cannot double-charge or refund.
        await store.settle_failure(context.job_id, "OUTPUT_STORAGE_QUOTA_EXCEEDED", "storage limit")
        queue = SimpleNamespace(enqueue_gpu_job=AsyncMock())
        assert await gpu_worker.recover_dispatchable_jobs(queue) == 0
        async with factory() as session:
            assert (await session.get(Job, context.job_id)).status is JobStatus.ERROR
        assert events == ["pipeline_finished"] and uploaded == []
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))

@pytest.mark.integration
@pytest.mark.parametrize("pre_render", [True, False])
def test_postgres_failure_settlement_is_atomic_and_pre_render_refunds(postgres, monkeypatch, tmp_path, pre_render):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.db.models import CreditLedgerEntry, CreditWallet, LedgerKind
    from backend.services.billing import ledger
    from backend.workers import gpu_tasks

    async def check(factory, repo, kwargs, reserve, uploaded):
        for module in (ledger, gpu_tasks):
            monkeypatch.setattr(module, "get_session_factory", lambda: factory)
        context = kwargs["context"]
        await ledger.grant(context.user_id, 100, "grant", {})
        await ledger.reserve(context.user_id, 20, context.job_id, "reserve")
        store = gpu_tasks.SqlAlchemyWorkerJobStore()
        if pre_render:
            async def runner(request, report):
                raise gpu_tasks.DeterministicJobError("invalid source before render")
            await gpu_tasks.GpuJobWorker(store, SimpleNamespace(publish_progress=AsyncMock()), runner).execute(context.job_id)
            expected = (100, 0, 0, 0, JobStatus.ERROR)
        else:
            original = store._finish_in_session
            async def crash(*args):
                raise RuntimeError("failure marker commit interrupted")
            store._finish_in_session = crash
            with pytest.raises(RuntimeError, match="commit interrupted"):
                await store.settle_failure(context.job_id, "OUTPUT_STORAGE_QUOTA_EXCEEDED", "storage limit")
            async with factory() as session:
                job = await session.get(Job, context.job_id)
                wallet = await session.get(CreditWallet, context.user_id)
                assert (wallet.available, wallet.reserved, job.reserved_credits, job.settled_credits, job.status) == (80, 20, 20, 0, JobStatus.PROCESSING)
                assert (await session.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.kind == LedgerKind.SETTLE))).all() == []
            store._finish_in_session = original
            await store.settle_failure(context.job_id, "OUTPUT_STORAGE_QUOTA_EXCEEDED", "storage limit")
            expected = (80, 0, 0, 20, JobStatus.ERROR)
        async with factory() as session:
            job = await session.get(Job, context.job_id)
            wallet = await session.get(CreditWallet, context.user_id)
            assert (wallet.available, wallet.reserved, job.reserved_credits, job.settled_credits, job.status) == expected
    asyncio.run(scenario(postgres, monkeypatch, tmp_path, check))
