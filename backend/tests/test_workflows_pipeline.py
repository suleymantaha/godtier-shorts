from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from backend.config import ProjectPaths
from backend.core.workflows_pipeline import PipelineWorkflow
from backend.core.workflow_helpers import ensure_pipeline_master_assets
from backend.services.ownership import build_owner_scoped_project_id


def test_pipeline_ensure_transcript_passes_cancel_event_as_keyword(monkeypatch, tmp_path) -> None:
    observed: dict[str, object] = {}
    transcript_path = tmp_path / "transcript.json"
    cancel_event = object()

    def fake_run_transcription(*args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        transcript_path.write_text("[]", encoding="utf-8")
        return str(transcript_path)

    monkeypatch.setattr("backend.core.workflows_pipeline.run_transcription", fake_run_transcription)
    monkeypatch.setattr("backend.core.workflows_pipeline.release_whisper_models", lambda: None)

    ctx = SimpleNamespace(
        project=SimpleNamespace(transcript=transcript_path),
        cancel_event=cancel_event,
        _check_cancelled=lambda: None,
        _update_status=lambda *_args, **_kwargs: None,
    )

    result = asyncio.run(PipelineWorkflow(ctx)._ensure_transcript(str(tmp_path / "master.wav")))

    assert result == str(transcript_path)
    assert observed["args"] == ()
    assert observed["kwargs"]["audio_file"] == str(tmp_path / "master.wav")
    assert observed["kwargs"]["output_json"] == str(transcript_path)
    assert observed["kwargs"]["cancel_event"] is cancel_event
    assert callable(observed["kwargs"]["status_callback"])


def test_ensure_pipeline_master_assets_recovers_missing_audio_even_when_transcript_exists(monkeypatch, tmp_path) -> None:
    import backend.config as config

    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setenv("SUBJECT_NAMESPACE_SECRET", "pipeline-master-assets-secret")

    project = ProjectPaths(build_owner_scoped_project_id("yt", "subject-a", "video123"))
    project.master_video.write_bytes(b"video")
    project.transcript.write_text("[]", encoding="utf-8")

    observed: dict[str, object] = {}

    async def fake_extract_audio_async(*, video_file: str, audio_file: str, update_status, command_runner) -> str:
        observed["video_file"] = video_file
        observed["audio_file"] = audio_file
        observed["command_runner"] = command_runner
        Path(audio_file).write_bytes(b"audio")
        return audio_file

    monkeypatch.setattr("backend.core.media_ops.extract_audio_async", fake_extract_audio_async)

    ctx = SimpleNamespace(
        project=project,
        command_runner=object(),
        _update_status=lambda *_args, **_kwargs: None,
    )

    master_video, master_audio = asyncio.run(
        ensure_pipeline_master_assets(ctx, "https://youtube.com/watch?v=test123", "best")
    )

    assert master_video == str(project.master_video)
    assert master_audio == str(project.master_audio)
    assert observed["video_file"] == str(project.master_video)
    assert observed["audio_file"] == str(project.master_audio)
    assert project.master_audio.read_bytes() == b"audio"
