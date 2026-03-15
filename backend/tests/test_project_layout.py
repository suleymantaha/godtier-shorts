from __future__ import annotations

from pathlib import Path

import pytest

import backend.config as config
from backend.config import (
    ProjectPaths,
    extract_subject_hash_from_project_id,
    get_project_path,
)


def test_extract_subject_hash_from_owner_scoped_project_id() -> None:
    project_id = "yt_1234567890abcdef1234567890abcdef_videoid"

    assert extract_subject_hash_from_project_id(project_id) == "1234567890abcdef1234567890abcdef"


def test_project_paths_use_nested_subject_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    project_id = "up_1234567890abcdef1234567890abcdef_cliphash"

    project = ProjectPaths(project_id)

    assert project.root == tmp_path / "projects" / "1234567890abcdef1234567890abcdef" / project_id
    assert get_project_path(project_id, "shorts", "clip.mp4") == project.root / "shorts" / "clip.mp4"


def test_flat_project_ids_are_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")

    with pytest.raises(ValueError, match="owner subject hash"):
        ProjectPaths("proj_legacy")
