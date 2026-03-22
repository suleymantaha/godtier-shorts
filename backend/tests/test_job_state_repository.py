from __future__ import annotations

import json
import threading
from pathlib import Path

from backend.api.websocket import ConnectionManager
from backend.services.job_state import JobStateRepository


def _load_jobs_payload(path: Path) -> dict[str, dict]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["jobs"]


def test_job_repository_persists_serializable_fields_and_tracks_nested_mutations(tmp_path: Path) -> None:
    state_path = tmp_path / "jobs.json"
    repository = JobStateRepository(state_path)

    repository["job-1"] = {
        "job_id": "job-1",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "subject": "subject-a",
        "cancel_event": threading.Event(),
    }
    repository["job-1"]["status"] = "processing"
    repository["job-1"]["task_handle"] = object()
    repository["job-1"]["last_message"] = "running"

    persisted = _load_jobs_payload(state_path)["job-1"]

    assert persisted["status"] == "processing"
    assert persisted["last_message"] == "running"
    assert "cancel_event" not in persisted
    assert "task_handle" not in persisted


def test_connection_manager_recovers_interrupted_jobs_from_persistent_state(tmp_path: Path) -> None:
    state_path = tmp_path / "jobs.json"
    repository = JobStateRepository(state_path)
    repository["job-1"] = {
        "job_id": "job-1",
        "status": "processing",
        "progress": 42,
        "last_message": "running",
        "subject": "subject-a",
    }

    recovered_manager = ConnectionManager(job_repository=JobStateRepository(state_path))
    recovered_job = recovered_manager.jobs["job-1"]

    assert recovered_job["status"] == "error"
    assert recovered_job["progress"] == 42
    assert recovered_job["error"] == "İş sunucu yeniden başlatıldığı için kesildi."
    assert recovered_job["timeline"][-1]["id"] == "job-1:recovered"
    assert recovered_job["timeline"][-1]["status"] == "error"


def test_connection_manager_uses_explicit_empty_repository_for_persistence(tmp_path: Path) -> None:
    state_path = tmp_path / "jobs.json"
    repository = JobStateRepository(state_path)

    manager = ConnectionManager(job_repository=repository)
    manager.jobs["job-1"] = {
        "job_id": "job-1",
        "status": "queued",
        "progress": 0,
        "last_message": "queued",
        "subject": "subject-a",
    }

    persisted = _load_jobs_payload(state_path)

    assert "job-1" in persisted
