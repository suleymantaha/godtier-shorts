import asyncio
import json
from pathlib import Path

from backend.api.routes import clips


def _create_clip(base_dir: Path, project_id: str, clip_name: str, *, title: str = "") -> None:
    shorts_dir = base_dir / project_id / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    (shorts_dir / clip_name).write_bytes(b"fake-mp4")
    if title:
        metadata = {"viral_metadata": {"ui_title": title}}
        (shorts_dir / clip_name.replace(".mp4", ".json")).write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )


def _list_clips(page: int = 1, page_size: int = 50) -> dict:
    return asyncio.run(clips.list_clips(page=page, page_size=page_size, _=None))


def test_clips_index_cache_reuses_scan(monkeypatch, tmp_path: Path):
    _create_clip(tmp_path, "proj-a", "a.mp4", title="A")
    _create_clip(tmp_path, "proj-b", "b.mp4", title="B")

    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    clips.invalidate_clips_cache("test_setup")

    original_scan = clips._scan_clips_index
    scan_calls = 0

    def _wrapped_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(clips, "_scan_clips_index", _wrapped_scan)

    first = _list_clips()
    second = _list_clips()

    assert scan_calls == 1
    assert first == second
    assert first["total"] == 2


def test_clips_cache_invalidation_after_success(monkeypatch, tmp_path: Path):
    _create_clip(tmp_path, "proj-a", "a.mp4", title="A")
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "thread_safe_broadcast", lambda *_args, **_kwargs: None)
    clips.invalidate_clips_cache("test_setup")

    original_scan = clips._scan_clips_index
    scan_calls = 0

    def _wrapped_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(clips, "_scan_clips_index", _wrapped_scan)

    _list_clips()
    assert scan_calls == 1

    job_id = "job-cache-refresh"
    clips.manager.jobs[job_id] = {}
    clips.finalize_job_success(job_id, "ok")
    clips.manager.jobs.pop(job_id, None)
    _list_clips()

    assert scan_calls == 2


def test_clips_cache_ttl_refresh(monkeypatch, tmp_path: Path):
    _create_clip(tmp_path, "proj-a", "a.mp4", title="A")
    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(clips, "CLIPS_CACHE_TTL_SECONDS", 0)
    clips.invalidate_clips_cache("test_setup")

    original_scan = clips._scan_clips_index
    scan_calls = 0

    def _wrapped_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(clips, "_scan_clips_index", _wrapped_scan)

    _list_clips()
    _list_clips()
    assert scan_calls == 2


def test_clips_pagination_contract_unchanged(monkeypatch, tmp_path: Path):
    _create_clip(tmp_path, "proj-a", "a.mp4", title="A")
    _create_clip(tmp_path, "proj-a", "b.mp4", title="B")
    _create_clip(tmp_path, "proj-a", "c.mp4", title="C")

    monkeypatch.setattr(clips, "PROJECTS_DIR", tmp_path)
    clips.invalidate_clips_cache("test_setup")

    page_1 = _list_clips(page=1, page_size=2)
    page_2 = _list_clips(page=2, page_size=2)

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
