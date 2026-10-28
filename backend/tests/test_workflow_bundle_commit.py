from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core import workflow_artifacts


@pytest.mark.parametrize("existing", [False, True])
def test_metadata_failure_never_publishes_partial_render_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, existing: bool
) -> None:
    outputs = tmp_path / "shorts"
    outputs.mkdir()
    quarantine = tmp_path / ".quarantine" / "clip.mp4"
    quarantine.parent.mkdir()
    quarantine.write_bytes(b"new-video")
    public = outputs / "clip.mp4"
    if existing:
        public.write_bytes(b"old-video")
        public.with_suffix(".json").write_text('{"old": true}', encoding="utf-8")

    def fail_metadata(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(workflow_artifacts, "write_json_atomic", fail_metadata)
    with pytest.raises(OSError, match="disk full"):
        workflow_artifacts.commit_render_bundle(
            project=SimpleNamespace(root=tmp_path, outputs=outputs),
            quarantine_output=quarantine,
            clip_filename="clip.mp4",
            clip_metadata={"new": True},
            subject=None,
            project_id="project",
            ui_title=None,
            message="ready",
            progress=99,
        )

    assert quarantine.read_bytes() == b"new-video"
    assert public.exists() is existing
    if existing:
        assert public.read_bytes() == b"old-video"
        assert public.with_suffix(".json").read_text(encoding="utf-8") == '{"old": true}'


@pytest.mark.parametrize("existing", [False, True])
def test_video_promotion_failure_rolls_back_sidecars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, existing: bool
) -> None:
    outputs = tmp_path / "shorts"
    outputs.mkdir()
    quarantine = tmp_path / ".quarantine" / "clip.mp4"
    quarantine.parent.mkdir()
    quarantine.write_bytes(b"new-video")
    quarantine.with_name("clip_raw.mp4").write_bytes(b"new-raw")
    public = outputs / "clip.mp4"
    if existing:
        public.write_bytes(b"old-video")
        public.with_name("clip_raw.mp4").write_bytes(b"old-raw")
        public.with_suffix(".json").write_text('{"old": true}', encoding="utf-8")

    original_move = workflow_artifacts.move_file_atomic

    def fail_video(source: str | Path, destination: Path) -> None:
        if Path(source) == quarantine:
            raise OSError("video promotion failed")
        original_move(source, destination)

    monkeypatch.setattr(workflow_artifacts, "move_file_atomic", fail_video)
    with pytest.raises(OSError, match="video promotion failed"):
        workflow_artifacts.commit_render_bundle(
            project=SimpleNamespace(root=tmp_path, outputs=outputs),
            quarantine_output=quarantine,
            clip_filename="clip.mp4",
            clip_metadata={"new": True},
            subject=None,
            project_id="project",
            ui_title=None,
            message="ready",
            progress=99,
        )

    assert quarantine.read_bytes() == b"new-video"
    assert quarantine.with_name("clip_raw.mp4").read_bytes() == b"new-raw"
    assert quarantine.with_suffix(".json").read_text(encoding="utf-8").find('"new"') > 0
    assert public.exists() is existing
    if existing:
        assert public.read_bytes() == b"old-video"
        assert public.with_name("clip_raw.mp4").read_bytes() == b"old-raw"
        assert public.with_suffix(".json").read_text(encoding="utf-8") == '{"old": true}'
    else:
        assert not public.with_name("clip_raw.mp4").exists()
        assert not public.with_suffix(".json").exists()
