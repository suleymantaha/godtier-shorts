from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

import backend.config as config
from backend.api.routes.clips import prepare_uploaded_project
from backend.services.ownership import build_subject_hash, read_project_manifest


def test_prepare_uploaded_project_streams_to_project_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("backend.api.routes.clips._validate_video_with_ffprobe", lambda _path: None)
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")

    payload = b"streamed-video-payload"
    upload = UploadFile(
        filename="video.mp4",
        file=BytesIO(payload),
        headers={"content-type": "video/mp4"},
    )

    project, project_id, is_cached = prepare_uploaded_project(upload, owner_subject="subject-a")

    expected_hash = hashlib.sha256(payload).hexdigest()
    assert project_id == f"up_{build_subject_hash('subject-a')}_{expected_hash[:12]}"
    assert is_cached is False
    assert project.master_video.read_bytes() == payload
    manifest = read_project_manifest(project_id)
    assert manifest is not None
    assert manifest.owner_subject_hash == build_subject_hash("subject-a")


def test_prepare_uploaded_project_reuses_existing_cached_project(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("backend.api.routes.clips._validate_video_with_ffprobe", lambda _path: None)
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")

    payload = b"cached-streamed-video"
    expected_hash = hashlib.sha256(payload).hexdigest()
    project_id = f"up_{build_subject_hash('subject-a')}_{expected_hash[:12]}"
    cached_root = config.get_project_dir(project_id)
    cached_root.mkdir(parents=True, exist_ok=True)
    (cached_root / "master.mp4").write_bytes(payload)
    (cached_root / "transcript.json").write_text("[]", encoding="utf-8")
    manifest = read_project_manifest(project_id)
    if manifest is None:
        from backend.services.ownership import ensure_project_manifest
        ensure_project_manifest(project_id, owner_subject="subject-a", source="upload")

    upload = UploadFile(
        filename="video.mp4",
        file=BytesIO(payload),
        headers={"content-type": "video/mp4"},
    )

    project, resolved_project_id, is_cached = prepare_uploaded_project(upload, owner_subject="subject-a")

    assert resolved_project_id == project_id
    assert is_cached is True
    assert project.master_video.read_bytes() == payload


def test_prepare_uploaded_project_isolated_by_subject(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("backend.api.routes.clips._validate_video_with_ffprobe", lambda _path: None)
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "ownership-test-secret")

    payload = b"shared-video-payload"
    first_upload = UploadFile(
        filename="video.mp4",
        file=BytesIO(payload),
        headers={"content-type": "video/mp4"},
    )
    second_upload = UploadFile(
        filename="video.mp4",
        file=BytesIO(payload),
        headers={"content-type": "video/mp4"},
    )

    _project_a, project_id_a, cached_a = prepare_uploaded_project(first_upload, owner_subject="subject-a")
    _project_b, project_id_b, cached_b = prepare_uploaded_project(second_upload, owner_subject="subject-b")

    assert cached_a is False
    assert cached_b is False
    assert project_id_a != project_id_b
    assert project_id_a.startswith(f"up_{build_subject_hash('subject-a')}_")
    assert project_id_b.startswith(f"up_{build_subject_hash('subject-b')}_")
