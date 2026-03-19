import asyncio
import hashlib
import json
from pathlib import Path

import backend.config as config
from backend.api.routes import clips
from backend.api.security import AuthContext
from backend.services.ownership import build_owner_scoped_project_id, ensure_project_manifest


def _static_subject(token: str) -> str:
    return f"static-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]}"


def _owned_project_id(owner_token: str, suffix: str) -> str:
    return build_owner_scoped_project_id("proj", _static_subject(owner_token), suffix)


def _create_clip(base_dir: Path, project_id: str, clip_name: str, *, owner_token: str = "token-a", title: str = "") -> None:
    shorts_dir = config.get_project_path(project_id, "shorts")
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (shorts_dir / clip_name).write_bytes(b"fake-mp4")
    if title:
        metadata = {"viral_metadata": {"ui_title": title}}
        (shorts_dir / clip_name.replace(".mp4", ".json")).write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )
    ensure_project_manifest(project_id, owner_subject=_static_subject(owner_token), source="clips_cache_test")


def _list_clips(subject: str, page: int = 1, page_size: int = 50) -> dict:
    auth = AuthContext(subject=subject, roles={"viewer"}, token_type="bearer")
    return asyncio.run(clips.list_clips(page=page, page_size=page_size, auth=auth))


def test_clips_index_cache_reuses_scan(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    _create_clip(tmp_path, _owned_project_id("token-a", "a"), "a.mp4", title="A")
    _create_clip(tmp_path, _owned_project_id("token-a", "b"), "b.mp4", title="B")
    clips.invalidate_clips_cache("test_setup")

    original_scan = clips._scan_clips_index
    scan_calls = 0

    def _wrapped_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(clips, "_scan_clips_index", _wrapped_scan)

    first = _list_clips(_static_subject("token-a"))
    second = _list_clips(_static_subject("token-a"))

    assert scan_calls == 1
    assert first == second
    assert first["total"] == 2


def test_clips_cache_invalidation_after_success(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    _create_clip(tmp_path, _owned_project_id("token-a", "a"), "a.mp4", title="A")
    monkeypatch.setattr(clips, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    clips.invalidate_clips_cache("test_setup")

    original_scan = clips._scan_clips_index
    scan_calls = 0

    def _wrapped_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(clips, "_scan_clips_index", _wrapped_scan)

    _list_clips(_static_subject("token-a"))
    assert scan_calls == 1

    job_id = "job-cache-refresh"
    clips.manager.jobs[job_id] = {}
    clips.finalize_job_success(job_id, "ok")
    clips.manager.jobs.pop(job_id, None)
    _list_clips(_static_subject("token-a"))

    assert scan_calls == 2


def test_clips_cache_ttl_refresh(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    _create_clip(tmp_path, _owned_project_id("token-a", "a"), "a.mp4", title="A")
    monkeypatch.setattr(clips, "CLIPS_CACHE_TTL_SECONDS", 0)
    clips.invalidate_clips_cache("test_setup")

    original_scan = clips._scan_clips_index
    scan_calls = 0

    def _wrapped_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(clips, "_scan_clips_index", _wrapped_scan)

    _list_clips(_static_subject("token-a"))
    _list_clips(_static_subject("token-a"))
    assert scan_calls == 2


def test_clips_pagination_contract_unchanged(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    project_id = _owned_project_id("token-a", "a")
    _create_clip(tmp_path, project_id, "a.mp4", title="A")
    _create_clip(tmp_path, project_id, "b.mp4", title="B")
    _create_clip(tmp_path, project_id, "c.mp4", title="C")
    clips.invalidate_clips_cache("test_setup")

    page_1 = _list_clips(_static_subject("token-a"), page=1, page_size=2)
    page_2 = _list_clips(_static_subject("token-a"), page=2, page_size=2)

    assert set(page_1.keys()) == {"clips", "page", "page_size", "total", "has_more"}
    assert page_1["page"] == 1
    assert page_1["page_size"] == 2
    assert page_1["total"] == 3
    assert page_1["has_more"] is True
    assert len(page_1["clips"]) == 2

    assert page_2["page"] == 2
    assert page_2["total"] == 3
    assert page_2["has_more"] is False
    assert len(page_2["clips"]) == 1


def test_clips_index_hides_internal_raw_and_reburn_assets(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    project_id = _owned_project_id("token-a", "a")
    _create_clip(tmp_path, project_id, "final.mp4", title="Visible")
    _create_clip(tmp_path, project_id, "final_raw.mp4")
    _create_clip(tmp_path, project_id, "final_temp_reburn.mp4")
    _create_clip(tmp_path, project_id, "temp_render.mp4")
    clips.invalidate_clips_cache("test_setup")

    response = _list_clips(_static_subject("token-a"))

    assert response["total"] == 1
    assert [clip["name"] for clip in response["clips"]] == ["final.mp4"]


def test_clips_index_hides_clips_without_ready_metadata(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    project_id = _owned_project_id("token-a", "a")
    _create_clip(tmp_path, project_id, "ready.mp4", title="Ready")
    _create_clip(tmp_path, project_id, "missing-meta.mp4")

    shorts_dir = config.get_project_path(project_id, "shorts")
    (shorts_dir / "broken.mp4").write_bytes(b"fake-mp4")
    (shorts_dir / "broken.json").write_text("{not-json", encoding="utf-8")

    clips.invalidate_clips_cache("test_setup")
    response = _list_clips(_static_subject("token-a"))

    assert response["total"] == 1
    assert [clip["name"] for clip in response["clips"]] == ["ready.mp4"]


def test_clips_index_excludes_legacy_flat_project_folders(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)

    strict_project = _owned_project_id("token-a", "strict")
    _create_clip(tmp_path, strict_project, "strict.mp4", title="Strict")

    legacy_flat_project = tmp_path / "legacy_flat_project"
    legacy_shorts = legacy_flat_project / "shorts"
    legacy_shorts.mkdir(parents=True, exist_ok=True)
    (legacy_shorts / "legacy.mp4").write_bytes(b"legacy-mp4")
    (legacy_shorts / "legacy.json").write_text(json.dumps({"viral_metadata": {"ui_title": "Legacy"}}), encoding="utf-8")

    clips.invalidate_clips_cache("test_setup")
    response = _list_clips(_static_subject("token-a"))

    assert response["total"] == 1
    assert [clip["project"] for clip in response["clips"]] == [strict_project]
    assert [clip["name"] for clip in response["clips"]] == ["strict.mp4"]


def test_clips_page_cache_is_partitioned_by_subject(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "clips-cache-test-secret")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    project_a = _owned_project_id("token-a", "a")
    project_b = _owned_project_id("token-b", "b")
    _create_clip(tmp_path, project_a, "a.mp4", owner_token="token-a", title="A")
    _create_clip(tmp_path, project_b, "b.mp4", owner_token="token-b", title="B")
    clips.invalidate_clips_cache("test_setup")

    response_a = _list_clips(_static_subject("token-a"))
    response_b = _list_clips(_static_subject("token-b"))

    assert [clip["project"] for clip in response_a["clips"]] == [project_a]
    assert [clip["project"] for clip in response_b["clips"]] == [project_b]
    assert len(clips._clips_cache_state.page_cache) == 2
