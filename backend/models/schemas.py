"""
backend/models/schemas.py
===========================
Pydantic data validation schemas for GodTier Shorts.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, model_validator, field_validator


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any | None = None
    trace_id: str


VALID_STYLES = {
    "HORMOZI", "MRBEAST", "MINIMALIST", "TIKTOK", "YOUTUBE_SHORT",
    "PODCAST", "CORPORATE", "HIGHCARE", "CYBER_PUNK", "STORY_TELLER",
    "GLOW_KARAOKE", "VIRAL", "POP", "CLEAN", "BOLD", "MINIMAL",
}
VALID_LAYOUTS = {"auto", "single", "split"}
VALID_ANIMATIONS = {"default", "pop", "shake", "slide_up", "fade", "typewriter", "none"}


class JobRequest(BaseModel):
    youtube_url: str | None = None
    num_clips: int | None = Field(default=None, ge=1, le=20)
    auto_mode: bool = False
    duration_min: float | int | None = Field(default=None, ge=30, le=300)
    duration_max: float | int | None = Field(default=None, ge=30, le=300)
    force_reanalyze: bool = False
    force_rerender: bool = False
    style: str | None = None
    style_name: str | None = None
    ai_engine: str | None = None
    skip_subtitles: bool = False
    resolution: str | None = None
    subtitle_style: str | None = None
    layout: str | None = None
    requested_layout: str | None = None
    target_ratio: str | None = None
    font_name: str | None = None
    font_size: int | None = None
    primary_color: str | None = None
    outline_color: str | None = None
    outline_width: int | None = None
    animation_type: str | None = None
    position: str | None = None
    max_words_per_line: int | None = None

    @field_validator("style_name")

    @classmethod
    def validate_style_name(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in VALID_STYLES:
            raise ValueError(f"unknown style_name: {v}")
        return v

    @field_validator("layout", "requested_layout")

    @classmethod
    def validate_layout(cls, v: str | None) -> str | None:
        if v is not None and v.lower() not in VALID_LAYOUTS:
            raise ValueError(f"unknown requested layout: {v}")
        return v

    @field_validator("animation_type")

    @classmethod
    def validate_animation_type(cls, v: str | None) -> str | None:
        if v is not None and v.lower() not in VALID_ANIMATIONS:
            raise ValueError(f"unknown animation_type: {v}")
        return v

    @model_validator(mode="after")
    def validate_duration_range(self) -> JobRequest:
        if not self.auto_mode:
            if self.duration_min is not None and self.duration_max is not None:
                if self.duration_min >= self.duration_max:
                    raise ValueError("duration_min, duration_max araligi gecersiz olamaz")
        return self


class CancelJobRequest(BaseModel):
    confirmed: bool = True
    source: str | None = None
    reason: str | None = None


class AccountDeletionRequest(BaseModel):
    confirm: str


class BatchJobRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    style: str | None = None
    style_name: str | None = None
    animation_type: str | None = None
    skip_subtitles: bool = False
    num_clips: int | None = None
    auto_mode: bool = False
    project_id: str | None = None
    duration_min: float | int | None = None
    duration_max: float | int | None = None
    start_time: float | None = None
    end_time: float | None = None
    layout: str | None = None
    requested_layout: str | None = None


class ClipTranscriptRecoveryRequest(BaseModel):
    clip_name: str
    project_id: str | None = None
    strategy: str | None = None


class ManualAutoCutRequest(BaseModel):
    project_id: str | None = None
    start_time: float
    end_time: float
    style: str | None = None
    style_name: str | None = None
    animation_type: str | None = None
    requested_layout: str | None = None
    cut_as_short: bool = True
    duration_min: float | int | None = None
    duration_max: float | int | None = None


class ManualJobRequest(BaseModel):
    project_id: str | None = None
    clip_name: str | None = None
    cut_points: list[Any] = Field(default_factory=list)
    style: str | None = None
    style_name: str | None = None
    animation_type: str | None = None
    requested_layout: str | None = None
    duration_min: float | int | None = None
    duration_max: float | int | None = None


class ProjectTranscriptRecoveryRequest(BaseModel):
    project_id: str
    force_retranscribe: bool = False


class ReburnRequest(BaseModel):
    project_id: str | None = None
    clip_name: str | None = None
    style: str | None = None
    font_name: str | None = None
    font_size: int | None = None
    primary_color: str | None = None
    outline_color: str | None = None
    outline_width: int | None = None
    animation_type: str | None = None
    position: str | None = None
    max_words_per_line: int | None = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None
    words: list[dict[str, Any]] | None = None
