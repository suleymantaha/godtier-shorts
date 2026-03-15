from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.core.workflows_batch import BatchClipWorkflow


def test_batch_workflow_includes_partially_overlapping_segments_for_analysis(monkeypatch, tmp_path) -> None:
    observed: dict[str, object] = {}
    master_video = tmp_path / "master.mp4"
    master_video.write_bytes(b"video")

    class FakeAnalyzer:
        def analyze_transcript_segment(self, *, transcript_data, **kwargs):
            observed["transcript_data"] = transcript_data
            observed["kwargs"] = kwargs
            return {"segments": []}

    fake_project = SimpleNamespace(root=tmp_path)
    monkeypatch.setattr(
        "backend.core.workflows_batch.resolve_project_master_video",
        lambda *args, **kwargs: (fake_project, str(master_video)),
    )

    ctx = SimpleNamespace(
        project=None,
        analyzer=FakeAnalyzer(),
        cancel_event=None,
        subject=None,
        _check_cancelled=lambda: None,
        _update_status=lambda *_args, **_kwargs: None,
    )

    transcript = [
        {"text": "left overlap", "start": 8.0, "end": 12.0, "words": []},
        {"text": "inside", "start": 12.0, "end": 15.0, "words": []},
        {"text": "right overlap", "start": 15.0, "end": 21.0, "words": []},
        {"text": "outside", "start": 21.0, "end": 24.0, "words": []},
    ]

    result = asyncio.run(
        BatchClipWorkflow(ctx).run(
            start_t=10.0,
            end_t=20.0,
            num_clips=2,
            transcript_data=transcript,
            project_id="proj_1",
        )
    )

    assert result == []
    assert [segment["text"] for segment in observed["transcript_data"]] == [
        "left overlap",
        "inside",
        "right overlap",
    ]
    assert observed["kwargs"]["window_start"] == 10.0
    assert observed["kwargs"]["window_end"] == 20.0
