from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.core.workflows_pipeline import PipelineWorkflow


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
