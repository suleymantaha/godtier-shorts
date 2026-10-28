"""Real-thread cancellation coverage for uploaded video transcription."""
import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from backend.api.routes import editor, jobs
from backend.api.security import AuthContext
from backend.models.schemas import CancelJobRequest


def test_upload_cancel_waits_for_transcription_thread_before_releasing_slot(monkeypatch, tmp_path):
    import functools
    import threading
    worker_started = threading.Event()
    worker_release = threading.Event()
    worker_finished = threading.Event()
    transcript = tmp_path / 'transcript.json'
    transcript.write_text('[]')

    def prepare_transcript(*args, **kwargs):
        worker_started.set()
        assert worker_release.wait(3)
        worker_finished.set()

    async def real_to_thread(func, /, *args, **kwargs):
        return await asyncio.get_running_loop().run_in_executor(None, functools.partial(func, *args, **kwargs))

    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
    monkeypatch.delenv('WORKFLOW_INLINE_BLOCKING', raising=False)
    monkeypatch.setattr(asyncio, 'to_thread', real_to_thread)
    monkeypatch.setattr(editor, 'prepare_uploaded_project', lambda *args, **kwargs: (
        SimpleNamespace(master_video=tmp_path / 'video.mp4', transcript=transcript), 'owned-project', False,
    ))
    monkeypatch.setattr(editor, 'ensure_project_transcript', prepare_transcript)
    monkeypatch.setattr(editor, 'GodTierShortsCreator', lambda **kwargs: pytest.fail('cancelled upload started renderer'))
    monkeypatch.setattr(editor, 'thread_safe_broadcast', lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs, 'thread_safe_broadcast', lambda *args, **kwargs: None)
    auth = AuthContext(subject='test-owner', roles={'editor'}, token_type='bearer')
    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/test', 'headers': []})

    async def run():
        lock = asyncio.Lock()
        monkeypatch.setattr(editor.manager, 'processing_lock', lock)
        response = await editor.manual_cut_upload(
            request, file=object(), start_time=0, end_time=60, num_clips=1,
            style_name='HORMOZI', animation_type='default', skip_subtitles=False,
            cut_points=None, cut_as_short=True, layout='auto', duration_min=None,
            duration_max=None, auth=auth,
        )
        task = editor.manager.jobs[response['job_id']]['task']
        try:
            async with asyncio.timeout(2):
                while not worker_started.is_set():
                    await asyncio.sleep(0.001)
            await jobs.cancel_job(response['job_id'], request, CancelJobRequest(confirmed=True), auth=auth)
            await asyncio.sleep(0.01)
            assert not task.done()
            assert lock.locked()
            worker_release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
            assert worker_finished.is_set()
            assert not lock.locked()
            assert editor.manager.jobs[response['job_id']]['status'] == 'cancelled'
        finally:
            worker_release.set()
            await asyncio.gather(task, return_exceptions=True)

    editor.manager.jobs.clear()
    try:
        asyncio.run(run())
    finally:
        worker_release.set()
        editor.manager.jobs.clear()
