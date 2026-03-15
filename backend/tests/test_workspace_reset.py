from __future__ import annotations

from pathlib import Path

import pytest

import backend.config as config
from scripts.reset_workspace_for_subject_layout import main as reset_workspace_main


def _write_tree(root: Path, *relative_paths: str) -> None:
    for relative_path in relative_paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("data", encoding="utf-8")


def test_reset_workspace_for_subject_layout_clears_legacy_roots_and_recreates_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "projects"
    downloads_dir = tmp_path / "downloads"
    metadata_dir = tmp_path / "metadata"
    outputs_dir = tmp_path / "outputs"

    _write_tree(projects_dir, "legacy_proj/master.mp4", "legacy_proj/shorts/clip.mp4")
    _write_tree(downloads_dir, "master_video.mp4")
    _write_tree(metadata_dir, "video_metadata.json")
    _write_tree(outputs_dir, "clip.mp4")

    monkeypatch.setattr(config, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(config, "DOWNLOADS_DIR", downloads_dir)
    monkeypatch.setattr(config, "METADATA_DIR", metadata_dir)
    monkeypatch.setattr(config, "OUTPUTS_DIR", outputs_dir)

    summary = reset_workspace_main(["--yes"])

    assert summary == {
        "deleted_projects": 1,
        "deleted_downloads": 1,
        "deleted_metadata": 1,
        "deleted_outputs": 1,
    }
    assert projects_dir.exists() and list(projects_dir.iterdir()) == []
    assert downloads_dir.exists() and list(downloads_dir.iterdir()) == []
    assert metadata_dir.exists() and list(metadata_dir.iterdir()) == []
    assert outputs_dir.exists() and list(outputs_dir.iterdir()) == []


def test_reset_workspace_requires_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "projects"
    _write_tree(projects_dir, "legacy_proj/master.mp4")
    monkeypatch.setattr(config, "PROJECTS_DIR", projects_dir)

    with pytest.raises(SystemExit):
        reset_workspace_main([])

    assert (projects_dir / "legacy_proj" / "master.mp4").exists()
