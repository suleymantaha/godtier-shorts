from __future__ import annotations

import os
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable, Literal


Stage = Literal["transcript", "tracking", "render"]
_MICRO_USD = Decimal("0.000001")


def gpu_hourly_cost_from_env() -> Decimal:
    raw = os.getenv("GPU_HOURLY_COST_USD", "0").strip() or "0"
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise RuntimeError("GPU_HOURLY_COST_USD must be a decimal") from exc
    if not value.is_finite() or value < 0:
        raise RuntimeError("GPU_HOURLY_COST_USD must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    source_seconds: int
    transcript_seconds: int
    tracking_seconds: int
    render_seconds: int
    total_wall_seconds: int
    gpu_model: str
    gpu_seconds: int
    output_count: int
    retry_count: int
    estimated_internal_cost_usd: Decimal
    peak_vram_mb: int | None = None


class UsageMeter:
    def __init__(
        self,
        *,
        source_seconds: int,
        retry_count: int = 0,
        gpu_hourly_cost_usd: Decimal | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._started = clock()
        self._stage_started = self._started
        self._stage: Stage | None = None
        self._durations: dict[Stage, float] = {
            "transcript": 0.0,
            "tracking": 0.0,
            "render": 0.0,
        }
        self._source_seconds = max(0, int(source_seconds))
        self._retry_count = max(0, int(retry_count))
        self._hourly_cost = gpu_hourly_cost_usd if gpu_hourly_cost_usd is not None else gpu_hourly_cost_from_env()
        if not self._hourly_cost.is_finite() or self._hourly_cost < 0:
            raise ValueError("gpu_hourly_cost_usd must be non-negative")

    def start_stage(self, stage: Stage) -> None:
        now = self._clock()
        if self._stage is not None:
            self._durations[self._stage] += now - self._stage_started
        self._stage = stage
        self._stage_started = now

    def observe(self, progress: int, message: str) -> None:
        normalized = message.casefold()
        if any(word in normalized for word in ("render", "encode", "ffmpeg", "subtitle")) or progress >= 70:
            stage: Stage = "render"
        elif any(word in normalized for word in ("track", "yolo", "analy", "speaker")) or progress >= 45:
            stage = "tracking"
        else:
            stage = "transcript"
        if stage != self._stage:
            self.start_stage(stage)

    def finish(
        self,
        *,
        gpu_model: str,
        output_count: int,
        peak_vram_mb: int | None = None,
    ) -> UsageSnapshot:
        finished = self._clock()
        if self._stage is not None:
            self._durations[self._stage] += finished - self._stage_started
        total = max(0, round(finished - self._started))
        cost = (Decimal(total) * self._hourly_cost / Decimal(3600)).quantize(_MICRO_USD, rounding=ROUND_HALF_UP)
        return UsageSnapshot(
            source_seconds=self._source_seconds,
            transcript_seconds=max(0, round(self._durations["transcript"])),
            tracking_seconds=max(0, round(self._durations["tracking"])),
            render_seconds=max(0, round(self._durations["render"])),
            total_wall_seconds=total,
            gpu_model=gpu_model,
            gpu_seconds=total,
            output_count=max(0, int(output_count)),
            retry_count=self._retry_count,
            estimated_internal_cost_usd=cost,
            peak_vram_mb=peak_vram_mb,
        )
