from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

import backend.config as config
from backend.api.routes.clips import prepare_uploaded_project


def test_prepare_uploaded_project_streams_to_project_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("backend.api.routes.clips._validate_video_with_ffprobe", lambda _path: None)

    payload = b"streamed-video-payload"
    upload = UploadFile(
        filename="video.mp4",
        file=BytesIO(payload),
        headers={"content-type": "video/mp4"},
    )

    project, project_id, is_cached = prepare_uploaded_project(upload)

    expected_hash = hashlib.sha256(payload).hexdigest()
    assert project_id == f"up_{expected_hash[:16]}"
    assert is_cached is False
    assert project.master_video.read_bytes() == payload


def test_prepare_uploaded_project_reuses_existing_cached_project(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("backend.api.routes.clips._validate_video_with_ffprobe", lambda _path: None)

    payload = b"cached-streamed-video"
    expected_hash = hashlib.sha256(payload).hexdigest()
    project_id = f"up_{expected_hash[:16]}"
    cached_root = config.PROJECTS_DIR / project_id
    cached_root.mkdir(parents=True, exist_ok=True)
    (cached_root / "master.mp4").write_bytes(payload)
    (cached_root / "transcript.json").write_text("[]", encoding="utf-8")

    upload = UploadFile(
        filename="video.mp4",
        file=BytesIO(payload),
        headers={"content-type": "video/mp4"},
    )

    project, resolved_project_id, is_cached = prepare_uploaded_project(upload)

    assert resolved_project_id == project_id
    assert is_cached is True
    assert project.master_video.read_bytes() == payload
