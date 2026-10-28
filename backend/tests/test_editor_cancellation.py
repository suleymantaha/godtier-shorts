"""Cancellation must reach local editor tasks and their blocking render workers."""
import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from backend.api.routes import editor, jobs
from backend.api.security import AuthContext
from backend.models.schemas import BatchJobRequest, CancelJobRequest, ManualJobRequest, ReburnRequest


@pytest.mark.parametrize('mode', ['manual', 'batch', 'reburn', 'upload'])
@pytest.mark.parametrize('queued', [False, True])
def test_editor_cancellation_reaches_task_and_shared_event(monkeypatch, tmp_path, mode, queued):
    started = None
    instances = []

    class FakeOrchestrator:
        def __init__(self, **kwargs):
            self.cancel_event = kwargs.get('cancel_event')
            instances.append(self)

        async def render(self, **kwargs):
            started.set()
            await asyncio.Event().wait()
            pytest.fail('cancelled renderer resumed publication')

        run_manual_clip_async = render
        run_batch_manual_clips_async = render
        reburn_subtitles_async = render

        def cleanup_gpu(self):
            pass

    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setattr(editor, 'GodTierShortsCreator', FakeOrchestrator)
    monkeypatch.setattr(editor, 'thread_safe_broadcast', lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs, 'thread_safe_broadcast', lambda *args, **kwargs: None)
    transcript = tmp_path / 'transcript.json'
    transcript.write_text('[]')
    monkeypatch.setattr(editor, 'prepare_uploaded_project', lambda *args, **kwargs: (
        SimpleNamespace(master_video=tmp_path / 'video.mp4', transcript=transcript), 'owned-project', False,
    ))
    monkeypatch.setattr(editor, 'ensure_project_transcript', lambda *args, **kwargs: None)
    auth = AuthContext(subject='test-owner', roles={'editor'}, token_type='bearer')
    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/test', 'headers': []})

    async def run():
        nonlocal started
        started = asyncio.Event()
        lock = asyncio.Lock()
        monkeypatch.setattr(editor.manager, 'processing_lock', lock)
        if queued:
            await lock.acquire()
        if mode == 'manual':
            result = await editor.process_manual_clip(request, ManualJobRequest(start_time=0, end_time=10), auth=auth)
        elif mode == 'batch':
            result = await editor.process_batch_clips(request, BatchJobRequest(start_time=0, end_time=60, num_clips=2), auth=auth)
        elif mode == 'reburn':
            result = await editor.reburn_clip(request, ReburnRequest(clip_name='clip.mp4', transcript=[]), auth=auth)
        else:
            result = await editor.manual_cut_upload(
                request, file=object(), start_time=0, end_time=60, num_clips=1,
                style_name='HORMOZI', animation_type='default', skip_subtitles=False,
                cut_points=None, cut_as_short=True, layout='auto', duration_min=None,
                duration_max=None, auth=auth,
            )
        job_id = result['job_id']
        task = editor.manager.jobs[job_id]['task']
        try:
            if not queued:
                await asyncio.wait_for(started.wait(), 1)
            await jobs.cancel_job(job_id, request, CancelJobRequest(confirmed=True), auth=auth)
            assert editor.manager.jobs[job_id]['cancel_event'].is_set()
            if instances:
                assert instances[0].cancel_event is editor.manager.jobs[job_id]['cancel_event']
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 1)
            assert task.done()
            assert editor.manager.jobs[job_id]['status'] == 'cancelled'
            if queued:
                assert instances == []
        finally:
            task.cancel()
            if queued and lock.locked():
                lock.release()
            await asyncio.gather(task, return_exceptions=True)

    editor.manager.jobs.clear()
    try:
        asyncio.run(run())
    finally:
        editor.manager.jobs.clear()


def test_timeout_signals_worker_before_waiting_for_its_cleanup():
    import threading
    from backend.core.exceptions import JobExecutionError
    event = threading.Event()
    cleaned = []

    async def render():
        try:
            await asyncio.Event().wait()
        finally:
            assert event.is_set()
            await asyncio.sleep(0)
            cleaned.append(True)

    async def run():
        with pytest.raises(JobExecutionError):
            await editor._await_with_job_timeout(
                render(), timeout_seconds=0.01, timeout_message='timeout', cancel_event=event,
            )
        assert cleaned == [True]

    asyncio.run(run())


def test_reburn_unexpected_subprocess_failure_reaches_error_state(monkeypatch):
    import subprocess
    class BrokenOrchestrator:
        def __init__(self, **kwargs):
            pass
        async def reburn_subtitles_async(self, **kwargs):
            raise subprocess.CalledProcessError(1, ['ffmpeg'])
        def cleanup_gpu(self):
            pass
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setattr(editor, 'GodTierShortsCreator', BrokenOrchestrator)
    monkeypatch.setattr(editor, 'thread_safe_broadcast', lambda *args, **kwargs: None)
    auth = AuthContext(subject='test-owner', roles={'editor'}, token_type='bearer')
    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/reburn', 'headers': []})
    async def run():
        result = await editor.reburn_clip(request, ReburnRequest(clip_name='clip.mp4', transcript=[]), auth=auth)
        await editor.manager.jobs[result['job_id']]['task']
        assert editor.manager.jobs[result['job_id']]['status'] == 'error'
    editor.manager.jobs.clear()
    try:
        asyncio.run(run())
    finally:
        editor.manager.jobs.clear()
