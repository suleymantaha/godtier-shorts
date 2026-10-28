"""Split panels must not borrow pixels from the other half of a talk show."""
from __future__ import annotations

import numpy as np

from backend.services.video_processor import VideoProcessor


def test_landscape_two_panel_crop_does_not_include_neighbor() -> None:
    frame_width, frame_height = 1920, 1080
    crop_width, crop_height = VideoProcessor._split_crop_dimensions(frame_width, frame_height)
    assert crop_width <= frame_width // 2
    assert abs(crop_width / crop_height - 1080 / 864) < 0.01

    # A broadcast with one solid-color speaker panel on each side exposes bleed.
    frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
    frame[:, : frame_width // 2, 0] = 255
    frame[:, frame_width // 2 :, 2] = 255
    left_x1, left_x2 = VideoProcessor._compute_crop_bounds(480, crop_width, frame_width)
    right_x1, right_x2 = VideoProcessor._compute_crop_bounds(1440, crop_width, frame_width)
    y1 = (frame_height - crop_height) // 2
    left = frame[y1 : y1 + crop_height, left_x1:left_x2]
    right = frame[y1 : y1 + crop_height, right_x1:right_x2]
    assert left.shape == right.shape == (crop_height, crop_width, 3)
    assert np.all(left[:, :, 2] == 0)
    assert np.all(right[:, :, 0] == 0)


def test_split_crop_uses_subject_separation_without_fixing_source_halves() -> None:
    crop_width, _ = VideoProcessor._split_crop_dimensions(1920, 1080, center_distance=400)
    assert crop_width < 400
    left = VideoProcessor._compute_crop_bounds(250, crop_width, 1920)
    right = VideoProcessor._compute_crop_bounds(650, crop_width, 1920)
    assert left[1] < right[0]
    assert VideoProcessor._compute_crop_bounds(300, crop_width, 1920) != left


def test_split_vertical_crop_retains_high_subject_head() -> None:
    _, crop_height = VideoProcessor._split_crop_dimensions(1920, 1080, center_distance=900)
    top, bottom = VideoProcessor._split_crop_vertical_bounds(
        1080, crop_height, person_box=(200.0, 50.0, 600.0, 750.0)
    )
    assert top <= 50
    assert bottom <= 1080
    assert bottom - top == crop_height
