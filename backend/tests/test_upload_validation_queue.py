from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.storage.media_validation import ArqMediaValidationQueue
from backend.services.storage.object_store import UploadedObjectMetadata


def test_duplicate_validation_uses_stable_job_id(monkeypatch):
    import arq
    pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=None), aclose=AsyncMock(), exists=AsyncMock(return_value=0), eval=AsyncMock(return_value=[1, 60]))
    monkeypatch.setattr(arq, "create_pool", AsyncMock(return_value=pool))
    user_id = uuid4()
    metadata = UploadedObjectMetadata(f"uploads/{user_id}/opaque.mp4", "video/mp4", 100)
    queue = ArqMediaValidationQueue("redis://localhost/0")
    first = asyncio.run(queue.enqueue(user_id=user_id, metadata=metadata))
    second = asyncio.run(queue.enqueue(user_id=user_id, metadata=metadata))
    assert first == second
    assert pool.enqueue_job.call_args.kwargs["_job_id"] == first


def test_validation_admission_rejects_over_limit_before_dispatch(monkeypatch):
    import arq
    from backend.services.storage import media_validation
    pool = SimpleNamespace(enqueue_job=AsyncMock(), aclose=AsyncMock(), exists=AsyncMock(return_value=0), eval=AsyncMock(return_value=[999, 60]))
    monkeypatch.setattr(arq, "create_pool", AsyncMock(return_value=pool))
    user_id = uuid4()
    with pytest.raises(media_validation.UploadAdmissionError):
        asyncio.run(ArqMediaValidationQueue("redis://localhost/0").enqueue(user_id=user_id, metadata=UploadedObjectMetadata(f"uploads/{user_id}/opaque.mp4", "video/mp4", 100)))
    pool.enqueue_job.assert_not_awaited()


@pytest.mark.parametrize(("state", "success", "expected"), [
    ("complete", False, "failed"), ("complete", True, "pending"),
    ("in_progress", None, "validating"), ("queued", None, "queued"),
    ("deferred", None, "queued"), ("not_found", None, "pending"),
])
def test_validation_status_reports_queue_and_failure_states(monkeypatch, state, success, expected):
    import arq
    import arq.jobs
    pool = SimpleNamespace(aclose=AsyncMock())
    monkeypatch.setattr(arq, "create_pool", AsyncMock(return_value=pool))
    job = SimpleNamespace(
        status=AsyncMock(return_value=arq.jobs.JobStatus(state)),
        result_info=AsyncMock(return_value=SimpleNamespace(success=success)),
    )
    monkeypatch.setattr(arq.jobs, "Job", lambda *_: job)
    user_id = uuid4()
    result = asyncio.run(ArqMediaValidationQueue("redis://localhost/0").status(
        user_id=user_id, storage_key=f"uploads/{user_id}/source.mp4",
    ))
    assert result == expected
    pool.aclose.assert_awaited_once()


def test_duplicate_complete_reuses_existing_queue_result_without_quota_charge(monkeypatch):
    import arq
    pool = SimpleNamespace(aclose=AsyncMock(), exists=AsyncMock(return_value=1), eval=AsyncMock(), enqueue_job=AsyncMock())
    monkeypatch.setattr(arq, "create_pool", AsyncMock(return_value=pool))
    user_id = uuid4()
    metadata = UploadedObjectMetadata(f"uploads/{user_id}/source.mp4", "video/mp4", 100)
    result = asyncio.run(ArqMediaValidationQueue("redis://localhost/0").enqueue(user_id=user_id, metadata=metadata))
    assert result == ArqMediaValidationQueue.job_id(user_id, metadata.storage_key)
    pool.eval.assert_not_awaited()
    pool.enqueue_job.assert_not_awaited()
