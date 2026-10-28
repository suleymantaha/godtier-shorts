"""Validation for manually supplied video cut points."""

from __future__ import annotations

import json
import math

from backend.core.exceptions import InvalidInputError


def parse_cut_points(raw: str | None, *, start_time: float, end_time: float) -> list[float] | None:
    """Keep the caller's intended order and reject invalid segments."""
    if not raw or not raw.strip():
        return None
    try:
        pts = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidInputError("Kesim noktaları geçerli bir JSON dizisi olmalı") from exc
    if not isinstance(pts, list) or not 2 <= len(pts) <= 21:
        raise InvalidInputError("Kesim noktaları 2 ile 21 sayı içermeli")
    if any(isinstance(point, bool) or not isinstance(point, (int, float)) for point in pts):
        raise InvalidInputError("Kesim noktaları yalnızca sayı içermeli")
    try:
        nums = [float(point) for point in pts]
    except OverflowError as exc:
        raise InvalidInputError("Kesim noktaları sonlu sayı olmalı") from exc
    if any(not math.isfinite(point) for point in nums):
        raise InvalidInputError("Kesim noktaları sonlu sayı olmalı")
    if nums[0] < start_time or nums[-1] > end_time:
        raise InvalidInputError("Kesim noktaları seçilen zaman aralığında olmalı")
    if any(right <= left for left, right in zip(nums, nums[1:])):
        raise InvalidInputError("Kesim noktaları artan sırada ve benzersiz olmalı")
    return nums
