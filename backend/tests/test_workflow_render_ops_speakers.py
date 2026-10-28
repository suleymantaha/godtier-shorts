import json
from types import SimpleNamespace

import pytest

from backend.core import workflow_render_ops as ops
from backend.services.diarization import build_diarization_index, speaker_at


def test_word_speaker_switch_drives_index_and_dominance(tmp_path):
    transcript = [{"start": 0, "end": 8, "speaker": "SPEAKER_00", "words": [
        {"start": 0, "end": 4, "speaker": "SPEAKER_00"},
        {"start": 4, "end": 8, "speaker": "SPEAKER_01"},
    ]}]
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(transcript), encoding="utf-8")
    assert speaker_at(build_diarization_index(str(path)), 6) == "SPEAKER_01"
    assert speaker_at(build_diarization_index(str(path)), 4) == "SPEAKER_01"
    assert ops._analyze_speaker_dominance(transcript, 0, 8) == (0.5, 2, 0.5)


@pytest.mark.parametrize("transcript, expected", [
    ([{"start": 0, "end": 8, "speaker": speaker}], "auto")
    for speaker in (None, "Unknown", "", "unknown")
] + [
    ([{"start": 0, "end": 1, "speaker": "SPEAKER_00"},
      {"start": 1, "end": 8, "speaker": "Unknown"}], "auto"),
    ([{"start": 0, "end": 8, "speaker": "SPEAKER_00"}], "single"),
])
def test_speaker_evidence_controls_visual_auto_layout(monkeypatch, transcript, expected):
    monkeypatch.setattr(ops, "apply_opening_validation", lambda **kwargs: (0, {}))
    requested = []

    def resolve(**kwargs):
        requested.append(kwargs["requested_layout"])
        return SimpleNamespace(resolved_layout="split")

    ops._resolve_segment_window(
        video_processor=object(), transcript_source=transcript,
        source_video="source.mp4", start_t=0, end_t=8, requested_layout="auto", cut_as_short=True,
        manual_center_x=None, snap_segment_boundaries=lambda *args: (0, 8, {}),
        resolve_subtitle_render_plan=resolve,
    )
    assert requested == [expected]


def test_index_uses_segment_fallback_only_outside_labeled_words(tmp_path):
    transcript = [{"start": 0, "end": 8, "speaker": "SPEAKER_00", "words": [
        {"start": 3, "end": 5, "speaker": "SPEAKER_01"},
    ]}]
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(transcript), encoding="utf-8")
    index = build_diarization_index(str(path))
    assert [speaker_at(index, t) for t in (1, 4, 6)] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
    assert ops._analyze_speaker_dominance(transcript, 0, 8) == (0.75, 2, 0.25)


def test_sparse_reliable_labels_do_not_claim_monologue():
    transcript = [{"start": 0, "end": 1, "speaker": "SPEAKER_00"},
                  {"start": 1, "end": 8, "speaker": "Unknown"}]
    assert ops._analyze_speaker_dominance(transcript, 0, 8) == (0.125, 1, 0)


def test_explicit_unknown_word_blocks_segment_speaker_fallback(tmp_path):
    transcript = [{"start": 0, "end": 8, "speaker": "SPEAKER_00", "words": [
        {"start": 1, "end": 8, "speaker": "Unknown"},
    ]}]
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(transcript), encoding="utf-8")
    assert speaker_at(build_diarization_index(str(path)), 6) is None
    assert ops._analyze_speaker_dominance(transcript, 0, 8) == (0.125, 1, 0)


def test_short_overlapping_segment_does_not_hide_still_active_long_segment(tmp_path):
    transcript = [{"start": 0, "end": 8, "speaker": "SPEAKER_00"},
                  {"start": 2, "end": 3, "speaker": "SPEAKER_01"}]
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(transcript), encoding="utf-8")
    index = build_diarization_index(str(path))
    assert speaker_at(index, 2.5) == "SPEAKER_01"
    assert speaker_at(index, 6) == "SPEAKER_00"


def test_opening_adjustment_cannot_snap_back_before_visible_subject(monkeypatch):
    checked_starts = []

    def validate(**kwargs):
        checked_starts.append(kwargs["start_t"])
        return 1.1, {"layout_validation_status": "ok", "suggested_start_time": 1.1}

    monkeypatch.setattr(ops, "apply_opening_validation", validate)
    start, _, _, _, _ = ops._resolve_segment_window(
        video_processor=object(), transcript_source=[], source_video="source.mp4",
        start_t=1, end_t=4, requested_layout="single", cut_as_short=True,
        manual_center_x=None, snap_segment_boundaries=lambda *args: (1, 4, {}),
        resolve_subtitle_render_plan=lambda **kwargs: SimpleNamespace(resolved_layout="single"),
    )
    assert start >= 1.1
    assert checked_starts[-1] >= 1.1


def test_revalidated_opening_missing_subject_is_rejected(monkeypatch):
    reports = iter([(1.1, {"layout_validation_status": "ok"}),
                    (1.1, {"layout_validation_status": "opening_subject_missing"})])
    monkeypatch.setattr(ops, "apply_opening_validation", lambda **kwargs: next(reports))
    with pytest.raises(RuntimeError, match="subject"):
        ops._resolve_segment_window(
            video_processor=object(), transcript_source=[], source_video="source.mp4",
            start_t=1, end_t=4, requested_layout="single", cut_as_short=True,
            manual_center_x=None, snap_segment_boundaries=lambda *args: (args[1], args[2], {}),
            resolve_subtitle_render_plan=lambda **kwargs: SimpleNamespace(resolved_layout="single"),
        )
