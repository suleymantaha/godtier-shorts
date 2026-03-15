from __future__ import annotations

from backend.services.video_processor import VideoProcessor


def test_is_split_layout_stable_requires_majority_of_sampled_frames() -> None:
    stable = VideoProcessor._is_split_layout_stable(
        [
            (1920, [300.0, 900.0]),
            (1920, [320.0, 930.0]),
            (1920, [340.0]),
            (1920, [350.0, 980.0]),
            (1920, []),
        ]
    )
    assert stable is True


def test_is_split_layout_stable_rejects_close_centers() -> None:
    stable = VideoProcessor._is_split_layout_stable(
        [
            (1920, [500.0, 700.0]),
            (1920, [510.0, 690.0]),
            (1920, [520.0, 710.0]),
        ]
    )
    assert stable is False


def test_is_split_layout_stable_requires_distribution_across_clip_regions() -> None:
    frame_results = []
    for sample_index in range(16):
        centers = [320.0, 1220.0] if sample_index < 10 else [640.0]
        frame_results.append((1920, centers, sample_index, 16))

    assert VideoProcessor._is_split_layout_stable(frame_results) is False


def test_is_split_layout_stable_accepts_uniformly_distributed_two_person_frames() -> None:
    frame_results = [
        (1920, [300.0, 1300.0], sample_index, 16)
        for sample_index in range(16)
    ]

    assert VideoProcessor._is_split_layout_stable(frame_results) is True
