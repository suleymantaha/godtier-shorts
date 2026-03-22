from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes import jobs as jobs_routes
from backend.api.websocket import manager
from backend.api.security import authenticate_websocket_token


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(jobs_routes.router)
    return app


def test_jobs_endpoint_omits_runtime_task_objects(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:viewer")
    manager.jobs.clear()
    auth = authenticate_websocket_token("token123")
    manager.jobs["job-1"] = {
        "job_id": "job-1",
        "url": "https://example.com",
        "style": "TIKTOK",
        "status": "processing",
        "progress": 50,
        "last_message": "running",
        "created_at": 123.0,
        "subject": auth.subject,
        "download_progress": {
            "phase": "download",
            "downloaded_bytes": 1024,
            "total_bytes": 2048,
            "percent": 50,
            "speed_text": "1.00MiB/s",
            "eta_text": "00:03",
            "status": "downloading",
        },
        "timeline": [
            {
                "id": "job-1:queued",
                "at": "2026-03-20T00:00:00+00:00",
                "job_id": "job-1",
                "status": "queued",
                "progress": 0,
                "message": "queued",
                "source": "api",
            },
        ],
        "task": object(),
    }

    client = TestClient(_build_app())
    response = client.get("/api/jobs", headers={"Authorization": "Bearer token123"})

    assert response.status_code == 200
    body = response.json()
    assert "jobs" in body and len(body["jobs"]) == 1
    assert body["jobs"][0]["job_id"] == "job-1"
    assert "task" not in body["jobs"][0]
    assert body["jobs"][0]["download_progress"]["percent"] == 50
    assert body["jobs"][0]["timeline"][0]["id"] == "job-1:queued"


def test_start_job_returns_cached_without_creating_queue_entry(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:operator")
    manager.jobs.clear()
    async def _fake_cache_probe(*_args, **_kwargs):
        return {
            "project_id": "yt_subject_video",
            "project_cached": True,
            "analysis_cached": True,
            "render_cached": True,
            "cache_scope": "full_render",
            "clip_count": 3,
        }

    monkeypatch.setattr(jobs_routes, "_inspect_pipeline_cache_state", _fake_cache_probe)

    client = TestClient(_build_app())
    response = client.post(
        "/api/start-job",
        headers={"Authorization": "Bearer token123"},
        json={"youtube_url": "https://youtube.com/watch?v=test123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "cached",
        "job_id": None,
        "project_id": "yt_subject_video",
        "cache_hit": True,
        "cache_scope": "full_render",
        "message": "Hazir videolar bulundu. Mevcut sonuclar simdi getiriliyor.",
        "processing_locked": False,
        "gpu_locked": False,
    }
    assert manager.jobs == {}


def test_cache_status_endpoint_reports_project_and_render_cache(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:operator")

    async def _fake_cache_probe(*_args, **_kwargs):
        return {
            "project_id": "yt_subject_video",
            "project_cached": True,
            "analysis_cached": True,
            "render_cached": True,
            "cache_scope": "full_render",
            "clip_count": 3,
        }

    monkeypatch.setattr(jobs_routes, "_inspect_pipeline_cache_state", _fake_cache_probe)

    client = TestClient(_build_app())
    response = client.post(
        "/api/cache-status",
        headers={"Authorization": "Bearer token123"},
        json={"youtube_url": "https://youtube.com/watch?v=test123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "project_id": "yt_subject_video",
        "project_cached": True,
        "analysis_cached": True,
        "render_cached": True,
        "cache_scope": "full_render",
        "clip_count": 3,
        "message": "Bu video icin ayni ayarlarla hazir videolar bulundu.",
    }


def test_start_job_returns_starting_message_when_processing_slot_is_free(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:operator")
    manager.jobs.clear()

    async def _fake_cache_probe(*_args, **_kwargs):
        return {
            "project_id": "yt_subject_video",
            "project_cached": False,
            "analysis_cached": False,
            "render_cached": False,
            "cache_scope": "none",
            "clip_count": 0,
        }

    async def _noop_run_gpu_job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_routes, "_inspect_pipeline_cache_state", _fake_cache_probe)
    monkeypatch.setattr(jobs_routes, "run_gpu_job", _noop_run_gpu_job)

    client = TestClient(_build_app())
    response = client.post(
        "/api/start-job",
        headers={"Authorization": "Bearer token123"},
        json={"youtube_url": "https://youtube.com/watch?v=test123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["processing_locked"] is False
    assert body["message"] == "İşlem başlatılıyor. Hazırlık aşamaları yürütülüyor..."
    assert len(manager.jobs) == 1
    created_job = next(iter(manager.jobs.values()))
    assert created_job["last_message"] == "İşlem başlatılıyor. Hazırlık aşamaları yürütülüyor..."
    assert created_job["timeline"][0]["message"] == "İşlem başlatılıyor. Hazırlık aşamaları yürütülüyor..."


def test_start_job_reuses_existing_active_request_instead_of_enqueuing_duplicate(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKENS", "token123:operator")
    manager.jobs.clear()

    async def _fake_cache_probe(*_args, **_kwargs):
        return {
            "project_id": "yt_subject_video",
            "project_cached": False,
            "analysis_cached": False,
            "render_cached": False,
            "cache_scope": "none",
            "clip_count": 0,
        }

    async def _noop_run_gpu_job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(jobs_routes, "_inspect_pipeline_cache_state", _fake_cache_probe)
    monkeypatch.setattr(jobs_routes, "run_gpu_job", _noop_run_gpu_job)

    client = TestClient(_build_app())
    first_response = client.post(
        "/api/start-job",
        headers={"Authorization": "Bearer token123"},
        json={"youtube_url": "https://youtube.com/watch?v=test123"},
    )
    first_body = first_response.json()
    assert first_response.status_code == 200

    created_job = manager.jobs[first_body["job_id"]]
    created_job["status"] = "processing"

    second_response = client.post(
        "/api/start-job",
        headers={"Authorization": "Bearer token123"},
        json={"youtube_url": "https://youtube.com/watch?v=test123"},
    )

    assert second_response.status_code == 200
    assert second_response.json() == {
        "status": "queued",
        "job_id": first_body["job_id"],
        "project_id": "yt_subject_video",
        "cache_hit": False,
        "cache_scope": "none",
        "message": "Bu ayarlarla zaten aktif bir islem var. Mevcut is takip ediliyor.",
        "processing_locked": True,
        "gpu_locked": False,
        "existing_job": True,
    }
    assert len(manager.jobs) == 1
