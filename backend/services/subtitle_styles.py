"""
backend/services/subtitle_styles.py
=====================================
Subtitle stil tanimlari, preset yonetimi ve render spec cozumleyicisi.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field, field_validator

LOGICAL_CANVAS_WIDTH = 1080
LOGICAL_CANVAS_HEIGHT = 1920
SPLIT_PANEL_HEIGHT = 864
SPLIT_GUTTER_HEIGHT = 192
VALID_LAYOUTS = {"single", "split"}
GLOW_STYLE_KEYS = {"GLOW_KARAOKE", "GLASS_MORPH", "RETRO_WAVE", "CYBER_PUNK"}
EXPLICIT_ANIMATION_TYPES = {"pop", "shake", "slide_up", "fade", "typewriter", "none"}
VALID_ANIMATION_TYPES = {"default", *EXPLICIT_ANIMATION_TYPES}


class SubtitleCategory(str, Enum):
    """Altyazi kategorileri."""

    DYNAMIC = "dynamic"
    MINIMAL = "minimal"
    CREATIVE = "creative"
    ACCESSIBLE = "accessible"
    CORPORATE = "corporate"


class SubtitleStyle(BaseModel):
    """Kullanici veya sistem tarafindan secilen altyazi stili."""

    preset_key: str | None = Field(default=None, exclude=True)
    name: str = Field(default="Custom")
    font_name: str = Field(default="Arial")
    font_size: int = Field(default=24)
    primary_color: str = Field(default="&H00FFFFFF")
    highlight_color: str = Field(default="&H0000FFFF")
    outline_color: str = Field(default="&H00000000")
    outline_width: float = Field(default=2.0)
    shadow_color: str = Field(default="&H80000000")
    shadow_depth: float = Field(default=1.5)
    alignment: int = Field(default=2)
    margin_v: int = Field(default=220)
    animation_type: str = Field(default="pop")
    category: SubtitleCategory = Field(default=SubtitleCategory.DYNAMIC)
    font_weight: int = Field(default=700)
    italic: bool = Field(default=False)
    underline: bool = Field(default=False)
    gradient_colors: list[str] = Field(default_factory=lambda: ["&H00FFFFFF"])
    gradient_direction: str = Field(default="none")
    position_x: float = Field(default=0.5, ge=0.0, le=1.0)
    position_y: float = Field(default=0.9, ge=0.0, le=1.0)
    blur: float = Field(default=0.0, ge=0.0, le=10.0)
    border_radius: float = Field(default=0.0, ge=0.0, le=50.0)
    background_color: str = Field(default="&H00000000")
    animation_duration: float = Field(default=0.15, ge=0.0, le=2.0)
    animation_easing: str = Field(default="ease-out")
    high_contrast: bool = Field(default=False)
    large_text: bool = Field(default=False)

    @field_validator(
        "primary_color",
        "highlight_color",
        "outline_color",
        "shadow_color",
        "background_color",
    )
    @classmethod
    def validate_ass_color_format(cls, value: str) -> str:
        if not re.match(r"^&H[0-9A-Fa-f]{8}$", value):
            logger.warning(f"Renk formatı uygun değil: {value}, varsayılan beyaz kullanılıyor")
            return "&H00FFFFFF"
        return value.upper()

    @field_validator("font_size")
    @classmethod
    def validate_font_size(cls, value: int) -> int:
        if value < 8:
            logger.warning(f"Font boyutu çok küçük: {value}, minimum 8 kullanılıyor")
            return 8
        if value > 200:
            logger.warning(f"Font boyutu çok büyük: {value}, maksimum 200 kullanılıyor")
            return 200
        return value


class SubtitleCanvasSpec(BaseModel):
    width: int
    height: int
    layout: Literal["single", "split"] = "single"
    logical_width: int = LOGICAL_CANVAS_WIDTH
    logical_height: int = LOGICAL_CANVAS_HEIGHT


class SubtitleSafeAreaSpec(BaseModel):
    left: int
    top: int
    width: int
    height: int
    margin_l: int
    margin_r: int
    margin_v: int
    anchor_x: int
    anchor_y: int
    alignment: int
    padding_x: int
    padding_y: int
    max_text_width: int


class SubtitleAnimationSpec(BaseModel):
    entry_ms: int
    exit_ms: int
    emphasis_ms: int
    emphasis_scale_pct: int
    base_scale_pct: int
    slide_offset_px: int
    chunk_fade: bool


class ResolvedSubtitleRenderSpec(BaseModel):
    canvas: SubtitleCanvasSpec
    safe_area: SubtitleSafeAreaSpec
    animation: SubtitleAnimationSpec
    font_size: int
    outline_width: float
    shadow_depth: float
    blur: float
    line_height: float
    style: SubtitleStyle


class SubtitleMotionPreset(BaseModel):
    label: str
    animation_type: Literal["pop", "shake", "slide_up", "fade", "typewriter", "none"]
    animation_duration: float
    animation_easing: str
    emphasis_scale_pct: int
    base_scale_pct: int
    slide_offset_px: int
    chunk_fade: bool = True


class StyleManager:
    """Altyazi stillerini yöneten sinif."""

    _MOTION_PRESETS: dict[str, SubtitleMotionPreset] = {
        "pop": SubtitleMotionPreset(
            label="Pop",
            animation_type="pop",
            animation_duration=0.15,
            animation_easing="ease-out",
            emphasis_scale_pct=132,
            base_scale_pct=92,
            slide_offset_px=0,
        ),
        "shake": SubtitleMotionPreset(
            label="Shake",
            animation_type="shake",
            animation_duration=0.12,
            animation_easing="ease-in-out",
            emphasis_scale_pct=112,
            base_scale_pct=100,
            slide_offset_px=0,
        ),
        "slide_up": SubtitleMotionPreset(
            label="Slide Up",
            animation_type="slide_up",
            animation_duration=0.14,
            animation_easing="ease-out",
            emphasis_scale_pct=108,
            base_scale_pct=100,
            slide_offset_px=18,
        ),
        "fade": SubtitleMotionPreset(
            label="Fade",
            animation_type="fade",
            animation_duration=0.2,
            animation_easing="ease-out",
            emphasis_scale_pct=100,
            base_scale_pct=100,
            slide_offset_px=0,
        ),
        "typewriter": SubtitleMotionPreset(
            label="Typewriter",
            animation_type="typewriter",
            animation_duration=0.08,
            animation_easing="linear",
            emphasis_scale_pct=100,
            base_scale_pct=100,
            slide_offset_px=0,
        ),
        "none": SubtitleMotionPreset(
            label="None",
            animation_type="none",
            animation_duration=0.0,
            animation_easing="linear",
            emphasis_scale_pct=100,
            base_scale_pct=100,
            slide_offset_px=0,
            chunk_fade=False,
        ),
    }

    _PRESETS: dict[str, SubtitleStyle] = {
        "HORMOZI": SubtitleStyle(
            name="Hormozi Style",
            category=SubtitleCategory.DYNAMIC,
            font_name="Montserrat Black",
            font_size=120,
            primary_color="&H00FFFFFF",
            highlight_color="&H0000FFFF",
            outline_width=10.0,
            shadow_depth=5.0,
            alignment=2,
            margin_v=260,
            animation_type="pop",
        ),
        "MRBEAST": SubtitleStyle(
            name="MrBeast Gaming",
            category=SubtitleCategory.DYNAMIC,
            font_name="Komika Axis",
            font_size=100,
            primary_color="&H00FFFFFF",
            highlight_color="&H0000FF00",
            outline_width=12.0,
            shadow_depth=0.0,
            alignment=2,
            margin_v=300,
            animation_type="pop",
        ),
        "MINIMALIST": SubtitleStyle(
            name="Minimalist Podcast",
            category=SubtitleCategory.MINIMAL,
            font_name="Helvetica Neue",
            font_size=18,
            primary_color="&H00E0E0E0",
            highlight_color="&H00FFFFFF",
            outline_width=0.0,
            shadow_depth=1.0,
            alignment=2,
            margin_v=220,
            animation_type="fade",
        ),
        "TIKTOK": SubtitleStyle(
            name="TikTok Vertical",
            category=SubtitleCategory.DYNAMIC,
            font_name="Montserrat Black",
            font_size=100,
            primary_color="&H00FFFFFF",
            highlight_color="&H00FF00FF",
            gradient_colors=["&H00FFFFFF", "&H00FF00FF"],
            gradient_direction="horizontal",
            outline_width=8.0,
            shadow_depth=3.0,
            alignment=2,
            margin_v=250,
            position_y=0.85,
            animation_type="pop",
            animation_duration=0.12,
        ),
        "YOUTUBE_SHORT": SubtitleStyle(
            name="YouTube Shorts",
            category=SubtitleCategory.DYNAMIC,
            font_name="Poppins Bold",
            font_size=100,
            primary_color="&H00FFFFFF",
            highlight_color="&H0000FFFF",
            outline_width=10.0,
            shadow_depth=4.0,
            alignment=2,
            margin_v=280,
            animation_type="pop",
            background_color="&H80000000",
            border_radius=8.0,
        ),
        "PODCAST": SubtitleStyle(
            name="Podcast Style",
            category=SubtitleCategory.MINIMAL,
            font_name="Inter",
            font_size=60,
            primary_color="&H00F0F0F0",
            highlight_color="&H00FFFFFF",
            outline_width=0.0,
            shadow_depth=2.0,
            shadow_color="&H80000000",
            alignment=2,
            margin_v=220,
            animation_type="fade",
            animation_duration=0.3,
            background_color="&H40000000",
            border_radius=4.0,
        ),
        "CORPORATE": SubtitleStyle(
            name="Kurumsal",
            category=SubtitleCategory.CORPORATE,
            font_name="Roboto",
            font_size=60,
            font_weight=500,
            primary_color="&H00FFFFFF",
            outline_width=2.0,
            outline_color="&H00000000",
            shadow_depth=1.0,
            alignment=2,
            margin_v=220,
            animation_type="fade",
            animation_duration=0.5,
        ),
        "HIGHCARE": SubtitleStyle(
            name="Yüksek Kontrast",
            category=SubtitleCategory.ACCESSIBLE,
            font_name="Arial Black",
            font_size=60,
            font_weight=900,
            primary_color="&H00FFFF00",
            highlight_color="&H00FFFFFF",
            outline_width=4.0,
            outline_color="&H00000000",
            shadow_depth=0.0,
            high_contrast=True,
            alignment=2,
            margin_v=220,
            animation_type="none",
        ),
        "CYBER_PUNK": SubtitleStyle(
            name="Cyber Glitch",
            category=SubtitleCategory.CREATIVE,
            font_name="Orbitron Bold",
            font_size=100,
            primary_color="&H00FFFFFF",
            outline_color="&H00FF00FF",
            outline_width=4.0,
            shadow_color="&H00FFFF00",
            shadow_depth=6.0,
            gradient_colors=["&H00FFFFFF", "&H0000FFFF"],
            gradient_direction="vertical",
            animation_type="shake",
        ),
        "STORY_TELLER": SubtitleStyle(
            name="Storyteller",
            category=SubtitleCategory.CREATIVE,
            font_name="Courier New",
            font_size=60,
            font_weight=400,
            primary_color="&H00E0E0E0",
            alignment=1,
            margin_v=150,
            position_x=0.1,
            animation_type="typewriter",
            animation_duration=0.05,
        ),
        "GLOW_KARAOKE": SubtitleStyle(
            name="Neon Karaoke",
            category=SubtitleCategory.CREATIVE,
            font_name="Montserrat ExtraBold",
            font_size=110,
            primary_color="&H80FFFFFF",
            highlight_color="&H0000FFFF",
            outline_width=2.0,
            blur=4.0,
            animation_type="pop",
            animation_duration=0.1,
            margin_v=280,
        ),
        "GLASS_MORPH": SubtitleStyle(
            name="Glassmorphism",
            category=SubtitleCategory.CREATIVE,
            font_name="Inter SemiBold",
            font_size=60,
            primary_color="&H20FFFFFF",
            background_color="&H80FFFFFF",
            outline_width=1.0,
            outline_color="&H40000000",
            blur=10.0,
            border_radius=15.0,
            alignment=2,
            margin_v=100,
        ),
        "ALI_ABDAAL": SubtitleStyle(
            name="Productivity Vlog",
            category=SubtitleCategory.MINIMAL,
            font_name="Outfit Bold",
            font_size=60,
            primary_color="&H00FFFFFF",
            highlight_color="&H0032CD32",
            outline_width=0.0,
            shadow_depth=3.0,
            shadow_color="&H60000000",
            margin_v=240,
            animation_type="pop",
            animation_duration=0.1,
        ),
        "RETRO_WAVE": SubtitleStyle(
            name="80s Synthwave",
            category=SubtitleCategory.CREATIVE,
            font_name="Vampire",
            font_size=100,
            primary_color="&H00FF00FF",
            highlight_color="&H0000FFFF",
            outline_width=6.0,
            outline_color="&H00000000",
            blur=6.0,
            gradient_colors=["&H00FF00FF", "&H0000FFFF"],
            gradient_direction="horizontal",
            margin_v=260,
            animation_type="slide_up",
            animation_duration=0.2,
        ),
        "HACKER_TERMINAL": SubtitleStyle(
            name="Terminal Code",
            category=SubtitleCategory.CREATIVE,
            font_name="Consolas",
            font_size=60,
            primary_color="&H0000FF00",
            highlight_color="&H00FFFFFF",
            background_color="&HB0000000",
            outline_width=0.0,
            shadow_depth=0.0,
            border_radius=0.0,
            alignment=7,
            margin_v=140,
            position_x=0.05,
            position_y=0.15,
            animation_type="typewriter",
            animation_duration=0.03,
        ),
        "CINEMATIC_FILM": SubtitleStyle(
            name="Documentary Film",
            category=SubtitleCategory.MINIMAL,
            font_name="Times New Roman",
            font_size=60,
            italic=True,
            primary_color="&H00E6E6E6",
            highlight_color="&H00D4AF37",
            outline_width=1.0,
            outline_color="&H40000000",
            shadow_depth=2.0,
            shadow_color="&H90000000",
            alignment=2,
            margin_v=80,
            animation_type="fade",
            animation_duration=0.4,
        ),
    }

    @classmethod
    def normalize_preset_name(cls, preset_name: str) -> str:
        return preset_name.strip().upper()

    @classmethod
    def is_valid_layout(cls, layout: str) -> bool:
        return layout in VALID_LAYOUTS

    @classmethod
    def ensure_valid_layout(cls, layout: str) -> str:
        normalized = (layout or "single").strip().lower()
        if normalized not in VALID_LAYOUTS:
            raise ValueError(f"unknown layout: {layout}")
        return normalized

    @classmethod
    def has_preset(cls, preset_name: str) -> bool:
        return cls.normalize_preset_name(preset_name) in cls._PRESETS

    @classmethod
    def ensure_valid_preset_name(cls, preset_name: str) -> str:
        key = cls.normalize_preset_name(preset_name)
        if key not in cls._PRESETS:
            raise ValueError(f"unknown style_name: {preset_name}")
        return key

    @classmethod
    def get_preset(cls, preset_name: str) -> SubtitleStyle:
        key = cls.ensure_valid_preset_name(preset_name)
        logger.info(f"Stil yüklendi: {key}")
        return cls._PRESETS[key].model_copy(deep=True, update={"preset_key": key})

    @classmethod
    def ensure_valid_animation_type(cls, animation_type: str | None) -> str:
        normalized = (animation_type or "default").strip().lower()
        if normalized not in VALID_ANIMATION_TYPES:
            raise ValueError(f"unknown animation_type: {animation_type}")
        return normalized

    @classmethod
    def get_motion_preset(cls, animation_type: str) -> SubtitleMotionPreset:
        normalized = cls.ensure_valid_animation_type(animation_type)
        if normalized == "default":
            raise ValueError("default animation_type cannot be resolved directly")
        return cls._MOTION_PRESETS[normalized]

    @classmethod
    def list_animation_options(cls) -> list[dict[str, str]]:
        return [
            {"value": "default", "label": "Preset Default"},
            *[
                {"value": key, "label": preset.label}
                for key, preset in cls._MOTION_PRESETS.items()
            ],
        ]

    @classmethod
    def resolve_style(
        cls,
        preset_name: str,
        animation_type: str = "default",
    ) -> SubtitleStyle:
        style = cls.get_preset(preset_name)
        requested_animation_type = cls.ensure_valid_animation_type(animation_type)
        if requested_animation_type == "default":
            return style

        motion_preset = cls.get_motion_preset(requested_animation_type)
        return style.model_copy(
            deep=True,
            update={
                "animation_type": motion_preset.animation_type,
                "animation_duration": motion_preset.animation_duration,
                "animation_easing": motion_preset.animation_easing,
            },
        )

    @classmethod
    def list_presets(cls) -> list[str]:
        return list(cls._PRESETS.keys())

    @classmethod
    def list_presets_by_category(cls, category: SubtitleCategory) -> list[str]:
        return [key for key, style in cls._PRESETS.items() if style.category == category]

    @classmethod
    def create_custom_style(
        cls,
        name: str,
        font_name: str = "Arial",
        font_size: int = 36,
        primary_color: str = "&H00FFFFFF",
        category: SubtitleCategory = SubtitleCategory.CREATIVE,
        **kwargs: object,
    ) -> SubtitleStyle:
        return SubtitleStyle(
            name=name,
            font_name=font_name,
            font_size=font_size,
            primary_color=primary_color,
            category=category,
            **kwargs,
        )

    @classmethod
    def resolve_render_spec(
        cls,
        style: SubtitleStyle,
        *,
        canvas_width: int = LOGICAL_CANVAS_WIDTH,
        canvas_height: int = LOGICAL_CANVAS_HEIGHT,
        layout: str = "single",
    ) -> ResolvedSubtitleRenderSpec:
        resolved_layout = cls.ensure_valid_layout(layout)
        canvas = SubtitleCanvasSpec(width=canvas_width, height=canvas_height, layout=resolved_layout)
        scale = min(canvas_width / LOGICAL_CANVAS_WIDTH, canvas_height / LOGICAL_CANVAS_HEIGHT)
        safe_area = cls._resolve_safe_area(canvas)
        animation = cls._resolve_animation(style, scale)
        font_size = cls._resolve_font_size(style, scale)
        outline_width = cls._resolve_outline_width(style, scale)
        shadow_depth = cls._resolve_shadow_depth(style, scale)
        blur = cls._resolve_blur(style, scale)
        line_height = 1.12 if resolved_layout == "split" else 1.18

        return ResolvedSubtitleRenderSpec(
            canvas=canvas,
            safe_area=safe_area,
            animation=animation,
            font_size=font_size,
            outline_width=outline_width,
            shadow_depth=shadow_depth,
            blur=blur,
            line_height=line_height,
            style=style,
        )

    @staticmethod
    def _resolve_safe_area(canvas: SubtitleCanvasSpec) -> SubtitleSafeAreaSpec:
        side_padding = _snap(canvas.width * 0.08)
        padding_x = _snap(canvas.width * 0.03)
        padding_y = _snap(canvas.height * 0.0125)
        area_width = max(240, canvas.width - (side_padding * 2))

        if canvas.layout == "split":
            top = _snap(canvas.height * (SPLIT_PANEL_HEIGHT / LOGICAL_CANVAS_HEIGHT))
            height = _snap(canvas.height * (SPLIT_GUTTER_HEIGHT / LOGICAL_CANVAS_HEIGHT))
            anchor_y = top + padding_y
            alignment = 8
            margin_v = anchor_y
        else:
            height = _snap(canvas.height * 0.18)
            margin_v = _snap(canvas.height * 0.14)
            top = max(0, canvas.height - margin_v - height)
            anchor_y = canvas.height - margin_v
            alignment = 2

        return SubtitleSafeAreaSpec(
            left=side_padding,
            top=top,
            width=area_width,
            height=height,
            margin_l=side_padding,
            margin_r=side_padding,
            margin_v=margin_v,
            anchor_x=canvas.width // 2,
            anchor_y=anchor_y,
            alignment=alignment,
            padding_x=padding_x,
            padding_y=padding_y,
            max_text_width=max(240, area_width - (padding_x * 2)),
        )

    @staticmethod
    def _resolve_animation(style: SubtitleStyle, scale: float) -> SubtitleAnimationSpec:
        base_ms = int(round(style.animation_duration * 1000))
        emphasis_ms = max(40, min(base_ms or 90, 160))
        entry_ms = max(70, min(base_ms or 120, 260))
        exit_ms = max(60, min(entry_ms, 220))
        try:
            motion_preset = StyleManager.get_motion_preset(style.animation_type)
        except ValueError:
            motion_preset = StyleManager.get_motion_preset("pop")
        emphasis_scale_pct = motion_preset.emphasis_scale_pct
        base_scale_pct = motion_preset.base_scale_pct
        slide_offset_px = _snap(motion_preset.slide_offset_px * max(scale, 0.75)) if motion_preset.slide_offset_px else 0
        return SubtitleAnimationSpec(
            entry_ms=entry_ms,
            exit_ms=exit_ms,
            emphasis_ms=emphasis_ms,
            emphasis_scale_pct=emphasis_scale_pct,
            base_scale_pct=base_scale_pct,
            slide_offset_px=slide_offset_px,
            chunk_fade=motion_preset.chunk_fade,
        )

    @staticmethod
    def _resolve_font_size(style: SubtitleStyle, scale: float) -> int:
        logical_font_size = max(32, min(int(round(style.font_size * 1.08)), 126))
        if style.high_contrast or style.large_text:
            logical_font_size = min(136, logical_font_size + 10)
        return _snap(logical_font_size * scale)

    @staticmethod
    def _resolve_blur(style: SubtitleStyle, scale: float) -> float:
        if style.preset_key in GLOW_STYLE_KEYS:
            return round(max(0.0, min(style.blur * scale * 0.55, 2.2)), 2)
        return round(max(0.0, min(style.blur * scale * 0.25, 0.35)), 2)

    @staticmethod
    def _resolve_outline_width(style: SubtitleStyle, scale: float) -> float:
        multiplier = 0.85 if style.preset_key in GLOW_STYLE_KEYS else 0.72
        cap = 5.0 if style.preset_key in GLOW_STYLE_KEYS else 7.0
        return round(max(0.0, min(style.outline_width * scale * multiplier, cap)), 2)

    @staticmethod
    def _resolve_shadow_depth(style: SubtitleStyle, scale: float) -> float:
        return round(max(0.0, min(style.shadow_depth * scale * 0.6, 4.0)), 2)


def _snap(value: float) -> int:
    return int(round(value))
