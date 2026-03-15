"""
backend/tests/conftest.py
=========================
Pytest fixtures ve ortak ayarlar.
"""
import asyncio

import anyio.to_thread as anyio_to_thread
import fastapi.dependencies.utils as fastapi_dependencies_utils
import fastapi.routing as fastapi_routing
import fastapi.testclient as fastapi_testclient
import pytest
import starlette.concurrency as starlette_concurrency
import starlette.routing as starlette_routing
import starlette.testclient as starlette_testclient

from backend.tests.compat_testclient import CompatTestClient


async def _run_in_threadpool_inline(func, *args, **kwargs):
    return func(*args, **kwargs)


async def _asyncio_to_thread_inline(func, /, *args, **kwargs):
    return func(*args, **kwargs)


async def _anyio_run_sync_inline(func, *args, **kwargs):
    return func(*args, **kwargs)


fastapi_testclient.TestClient = CompatTestClient
starlette_testclient.TestClient = CompatTestClient
fastapi_routing.run_in_threadpool = _run_in_threadpool_inline
fastapi_dependencies_utils.run_in_threadpool = _run_in_threadpool_inline
starlette_concurrency.run_in_threadpool = _run_in_threadpool_inline
starlette_routing.run_in_threadpool = _run_in_threadpool_inline
asyncio.to_thread = _asyncio_to_thread_inline
anyio_to_thread.run_sync = _anyio_run_sync_inline


@pytest.fixture
def sample_transcript():
    """Örnek faster-whisper transkript JSON'u."""
    return [
        {
            "text": "Merhaba dünya",
            "start": 0.0,
            "end": 1.5,
            "speaker": "SPEAKER_00",
            "words": [
                {"word": "Merhaba", "start": 0.0, "end": 0.5, "score": 0.99},
                {"word": "dünya", "start": 0.5, "end": 1.5, "score": 0.98},
            ],
        },
    ]
