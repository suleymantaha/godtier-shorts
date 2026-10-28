"""Regression coverage for manual render request data and cut point validation."""

import pytest
from pydantic import ValidationError

from backend.core.cut_points import parse_cut_points
from backend.core.exceptions import InvalidInputError
from backend.models.schemas import ManualAutoCutRequest, ManualJobRequest


def test_manual_render_request_preserves_render_fields() -> None:
    transcript = [{"start": 1.0, "end": 2.0, "text": "hello"}]
    request = ManualJobRequest(
        start_time=1,
        end_time=2,
        transcript=transcript,
        center_x=0.3,
        layout="split",
    )

    assert request.start_time == 1
    assert request.end_time == 2
    assert request.transcript == transcript
    assert request.center_x == 0.3
    assert request.layout == "split"


@pytest.mark.parametrize(
    "payload",
    [
        {"start_time": 2, "end_time": 2},
        {"start_time": -1, "end_time": 2},
        {"start_time": float("nan"), "end_time": 2},
        {"start_time": 0, "end_time": float("inf")},
    ],
)
@pytest.mark.parametrize("request_type", [ManualAutoCutRequest, ManualJobRequest])
def test_manual_requests_reject_invalid_time_ranges(request_type, payload: dict) -> None:
    with pytest.raises(ValidationError):
        request_type(**payload)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[1]",
        "[1, 2, 2]",
        "[2, 1]",
        "[1, true, 2]",
        '[1, "bad", 2]',
        "[1, 11]",
        "[-1, 2]",
        "[1, 1e999]",
    ],
)
def test_cut_points_reject_invalid_input_instead_of_falling_back(raw: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_cut_points(raw, start_time=0, end_time=10)


def test_cut_points_preserve_requested_segments() -> None:
    assert parse_cut_points("[1, 2.5, 4]", start_time=0, end_time=10) == [1, 2.5, 4]
    assert parse_cut_points(None, start_time=0, end_time=10) is None


def test_cut_points_reject_oversized_integer() -> None:
    for digits in (400, 5000):
        with pytest.raises(InvalidInputError):
            parse_cut_points(f"[1, {str(9) * digits}]", start_time=0, end_time=10)

def test_reburn_request_preserves_frontend_render_fields():
    from backend.models.schemas import ReburnRequest
    transcript = [{'start': 0, 'end': 1, 'text': 'updated'}]
    request = ReburnRequest(clip_name='clip.mp4', transcript=transcript, style_name='MINIMALIST')
    assert request.transcript == transcript
    assert request.style_name == 'MINIMALIST'

@pytest.mark.parametrize('payload', [
    {'start_time': -1, 'end_time': 60, 'num_clips': 2},
    {'start_time': float('nan'), 'end_time': 60, 'num_clips': 2},
    {'start_time': 0, 'end_time': float('inf'), 'num_clips': 2},
    {'start_time': 60, 'end_time': 30, 'num_clips': 2},
    {'start_time': 0, 'end_time': 60, 'num_clips': 0},
    {'start_time': 0, 'end_time': 60, 'num_clips': 21},
    {'start_time': 0, 'end_time': 60, 'num_clips': 2, 'duration_min': float('nan')},
    {'start_time': 0, 'end_time': 60, 'num_clips': 2, 'duration_max': -1},
])
def test_batch_request_rejects_invalid_render_bounds(payload):
    from backend.models.schemas import BatchJobRequest
    with pytest.raises(ValidationError):
        BatchJobRequest(**payload)
