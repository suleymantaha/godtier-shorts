"""Editor production scope and path boundary regression tests."""
import asyncio

import pytest
from starlette.requests import Request

from backend.api.routes import editor
from backend.api.security import AuthContext
from backend.core.exceptions import InvalidInputError
from backend.models.schemas import BatchJobRequest, ManualJobRequest, ReburnRequest


def _request():
    return Request({'type': 'http', 'method': 'POST', 'path': '/api/test', 'headers': []})


def _auth():
    return AuthContext(subject='test-owner', roles={'editor'}, token_type='bearer')


@pytest.mark.parametrize('route,payload', [
    (editor.process_manual_clip, ManualJobRequest(start_time=0, end_time=1)),
    (editor.process_batch_clips, BatchJobRequest(start_time=0, end_time=60, num_clips=2)),
    (editor.reburn_clip, ReburnRequest(clip_name='clip.mp4', transcript=[])),
])
def test_production_render_requires_project_before_enqueue(monkeypatch, route, payload):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setattr(editor.manager, 'assert_subject_can_enqueue', lambda *_: pytest.fail('unscoped job reached admission'))
    with pytest.raises(InvalidInputError, match='project_id'):
        asyncio.run(route(_request(), payload, auth=_auth()))


def test_production_transcript_save_cannot_overwrite_shared_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    metadata = tmp_path / 'metadata.json'
    metadata.write_text('[{"text":"other account"}]', encoding='utf-8')
    monkeypatch.setattr(editor, 'VIDEO_METADATA', metadata)
    with pytest.raises(InvalidInputError, match='project_id'):
        asyncio.run(editor.save_transcript(_request(), [], project_id=None, auth=_auth()))
    assert metadata.read_text(encoding='utf-8') == '[{"text":"other account"}]'


@pytest.mark.parametrize('clip_name', ['../victim.mp4', '..\\victim.mp4', 'C:/victim.mp4'])
def test_reburn_rejects_path_before_enqueue(monkeypatch, clip_name):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setattr(editor.manager, 'assert_subject_can_enqueue', lambda *_: pytest.fail('unsafe path reached admission'))
    with pytest.raises(InvalidInputError):
        asyncio.run(editor.reburn_clip(_request(), ReburnRequest(clip_name=clip_name, transcript=[]), auth=_auth()))


def test_local_transcript_save_retains_legacy_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'development')
    metadata = tmp_path / 'metadata.json'
    monkeypatch.setattr(editor, 'VIDEO_METADATA', metadata)
    asyncio.run(editor.save_transcript(_request(), [], project_id=None, auth=_auth()))
    assert metadata.read_text(encoding='utf-8') == '[]'



def test_reburn_route_forwards_edited_transcript(monkeypatch):
    calls = []

    class FakeOrchestrator:
        def __init__(self, **kwargs):
            pass

        async def reburn_subtitles_async(self, **kwargs):
            calls.append(kwargs)

        def cleanup_gpu(self):
            pass

    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setattr(editor, 'GodTierShortsCreator', FakeOrchestrator)
    monkeypatch.setattr(editor, 'thread_safe_broadcast', lambda *args, **kwargs: None)
    editor.manager.jobs.clear()
    transcript = [{'start': 0, 'end': 1, 'text': 'edited'}]

    async def run():
        result = await editor.reburn_clip(_request(), ReburnRequest(
            clip_name='clip.mp4', transcript=transcript, style_name='MINIMALIST',
        ), auth=_auth())
        await editor.manager.jobs[result['job_id']]['task']
        assert editor.manager.jobs[result['job_id']]['status'] == 'completed'

    try:
        asyncio.run(run())
        assert calls[0]['transcript'] == transcript
        assert calls[0]['style_name'] == 'MINIMALIST'
    finally:
        editor.manager.jobs.clear()

@pytest.mark.parametrize('duration_min,duration_max', [(float('nan'), 60), (30, float('inf')), (-1, 60), (30, 0)])
def test_manual_upload_rejects_invalid_duration_bounds_before_persisting(monkeypatch, duration_min, duration_max):
    from io import BytesIO
    from fastapi import UploadFile
    monkeypatch.setattr(editor, 'prepare_uploaded_project', lambda *args, **kwargs: pytest.fail('invalid duration reached upload persistence'))
    with pytest.raises(InvalidInputError):
        asyncio.run(editor.manual_cut_upload(
            _request(), file=UploadFile(filename='test.mp4', file=BytesIO(b'video')),
            start_time=0, end_time=60, style_name='HORMOZI', animation_type='default',
            skip_subtitles=False, num_clips=2, cut_points=None, cut_as_short=True,
            layout='auto', duration_min=duration_min, duration_max=duration_max, auth=_auth(),
        ))

@pytest.mark.parametrize('num_clips', [0, 21, -1])
def test_manual_upload_rejects_invalid_clip_count_instead_of_changing_mode(monkeypatch, num_clips):
    from io import BytesIO
    from fastapi import UploadFile
    monkeypatch.setattr(editor, 'prepare_uploaded_project', lambda *args, **kwargs: pytest.fail('invalid count reached upload persistence'))
    with pytest.raises(InvalidInputError):
        asyncio.run(editor.manual_cut_upload(
            _request(), file=UploadFile(filename='test.mp4', file=BytesIO(b'video')),
            start_time=0, end_time=60, style_name='HORMOZI', animation_type='default',
            skip_subtitles=False, num_clips=num_clips, cut_points=None, cut_as_short=True,
            layout='auto', duration_min=None, duration_max=None, auth=_auth(),
        ))
