"""
Subtitle style ve render spec davranislari icin unit testler.
"""

from __future__ import annotations

import pytest

from backend.services.subtitle_styles import (
    LOGICAL_CANVAS_HEIGHT,
    LOGICAL_CANVAS_WIDTH,
    SPLIT_GUTTER_HEIGHT,
    SPLIT_PANEL_HEIGHT,
    StyleManager,
    SubtitleCategory,
    SubtitleStyle,
)


class TestSubtitleStyle:
    def test_default_style_has_all_fields(self) -> None:
        style = SubtitleStyle()
        assert style.name == "Custom"
        assert style.font_name == "Arial"
        assert style.font_size == 24
        assert style.primary_color == "&H00FFFFFF"
        assert style.alignment == 2
        assert style.margin_v == 220
        assert style.category == SubtitleCategory.DYNAMIC
        assert style.font_weight == 700
        assert style.gradient_colors == ["&H00FFFFFF"]
        assert style.background_color == "&H00000000"

    def test_new_fields_have_defaults(self) -> None:
        style = SubtitleStyle()
        assert style.animation_duration == 0.15
        assert style.gradient_direction == "none"
        assert style.high_contrast is False
        assert style.large_text is False

    def test_invalid_color_format_returns_default(self) -> None:
        for color in ["FFFFFF", "&HFF", "white", "#FFFFFF"]:
            style = SubtitleStyle(primary_color=color)
            assert style.primary_color == "&H00FFFFFF"

    def test_font_size_is_clamped(self) -> None:
        assert SubtitleStyle(font_size=1).font_size == 8
        assert SubtitleStyle(font_size=500).font_size == 200


class TestStyleManager:
    def test_list_presets_returns_all_public_presets(self) -> None:
        presets = StyleManager.list_presets()
        assert "HORMOZI" in presets
        assert "MRBEAST" in presets
        assert "MINIMALIST" in presets
        assert "CINEMATIC_FILM" in presets
        assert len(presets) == 16

    def test_case_insensitive_lookup_returns_deep_copy(self) -> None:
        lower = StyleManager.get_preset("hormozi")
        upper = StyleManager.get_preset("HORMOZI")
        assert lower == upper
        assert lower is not upper

        lower.font_size = 77
        fresh = StyleManager.get_preset("HORMOZI")
        assert fresh.font_size == 120
        assert fresh.preset_key == "HORMOZI"

    def test_unknown_preset_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown style_name"):
            StyleManager.get_preset("BILINMEYEN")

    def test_list_presets_by_category(self) -> None:
        dynamic = StyleManager.list_presets_by_category(SubtitleCategory.DYNAMIC)
        assert {"HORMOZI", "MRBEAST", "TIKTOK", "YOUTUBE_SHORT"}.issubset(set(dynamic))

        minimal = StyleManager.list_presets_by_category(SubtitleCategory.MINIMAL)
        assert {"MINIMALIST", "PODCAST"}.issubset(set(minimal))

        corporate = StyleManager.list_presets_by_category(SubtitleCategory.CORPORATE)
        assert corporate == ["CORPORATE"]

    def test_create_custom_style(self) -> None:
        style = StyleManager.create_custom_style(
            name="Test Style",
            font_name="Test Font",
            font_size=42,
            category=SubtitleCategory.CREATIVE,
        )
        assert style.name == "Test Style"
        assert style.font_name == "Test Font"
        assert style.font_size == 42
        assert style.category == SubtitleCategory.CREATIVE
        assert style.margin_v == 220

    def test_layout_validation_is_strict(self) -> None:
        assert StyleManager.ensure_valid_layout("single") == "single"
        assert StyleManager.ensure_valid_layout("split") == "split"
        with pytest.raises(ValueError, match="unknown layout"):
            StyleManager.ensure_valid_layout("grid")

    def test_animation_validation_and_listing(self) -> None:
        assert StyleManager.ensure_valid_animation_type("default") == "default"
        assert StyleManager.ensure_valid_animation_type("POP") == "pop"
        with pytest.raises(ValueError, match="unknown animation_type"):
            StyleManager.ensure_valid_animation_type("warp")

        options = StyleManager.list_animation_options()
        assert options[0] == {"value": "default", "label": "Preset Default"}
        assert {"value": "pop", "label": "Pop"} in options

    def test_resolve_style_preserves_preset_motion_by_default(self) -> None:
        style = StyleManager.resolve_style("HORMOZI", "default")
        assert style.animation_type == "pop"
        assert style.animation_duration == pytest.approx(0.15, abs=1e-6)

    def test_resolve_style_overrides_only_motion_fields(self) -> None:
        style = StyleManager.resolve_style("HORMOZI", "fade")
        assert style.preset_key == "HORMOZI"
        assert style.font_name == "Montserrat Black"
        assert style.animation_type == "fade"
        assert style.animation_duration == pytest.approx(0.2, abs=1e-6)
        assert style.animation_easing == "ease-out"


class TestResolvedRenderSpec:
    def test_public_presets_resolve_for_single_and_split_layouts(self) -> None:
        for preset_name in StyleManager.list_presets():
            style = StyleManager.get_preset(preset_name)
            single = StyleManager.resolve_render_spec(style, layout="single")
            split = StyleManager.resolve_render_spec(style, layout="split")
            lower_third = StyleManager.resolve_render_spec(style, layout="single", safe_area_profile="lower_third_safe")

            assert single.safe_area.profile == "default"
            assert split.safe_area.profile == "default"
            assert lower_third.safe_area.profile == "lower_third_safe"
            assert split.font_size <= single.font_size
            assert split.safe_area.max_text_width < single.safe_area.max_text_width

    def test_single_layout_uses_fixed_safe_area(self) -> None:
        style = StyleManager.get_preset("HORMOZI")
        spec = StyleManager.resolve_render_spec(style, canvas_width=1080, canvas_height=1920, layout="single")

        assert spec.canvas.width == LOGICAL_CANVAS_WIDTH
        assert spec.canvas.height == LOGICAL_CANVAS_HEIGHT
        assert spec.safe_area.alignment == 2
        assert spec.safe_area.margin_l == 86
        assert spec.safe_area.margin_r == 86
        assert spec.safe_area.margin_v == 269
        assert spec.safe_area.anchor_y == LOGICAL_CANVAS_HEIGHT - 269
        assert spec.font_size >= 100
        assert spec.safe_area.profile == "default"

    def test_lower_third_profile_moves_single_layout_up(self) -> None:
        style = StyleManager.get_preset("HORMOZI")
        spec = StyleManager.resolve_render_spec(
            style,
            canvas_width=1080,
            canvas_height=1920,
            layout="single",
            safe_area_profile="lower_third_safe",
        )

        assert spec.safe_area.profile == "lower_third_safe"
        assert spec.safe_area.margin_v == 422
        assert spec.safe_area.anchor_y == LOGICAL_CANVAS_HEIGHT - 422

    def test_split_layout_uses_middle_gutter_safe_area(self) -> None:
        style = StyleManager.get_preset("TIKTOK")
        single = StyleManager.resolve_render_spec(style, canvas_width=1080, canvas_height=1920, layout="single")
        spec = StyleManager.resolve_render_spec(style, canvas_width=1080, canvas_height=1920, layout="split")

        assert spec.safe_area.top == SPLIT_PANEL_HEIGHT
        assert spec.safe_area.height == SPLIT_GUTTER_HEIGHT
        assert spec.safe_area.alignment == 8
        assert spec.safe_area.padding_x == 54
        assert spec.safe_area.padding_y == 36
        assert spec.safe_area.margin_v == 900
        assert spec.safe_area.anchor_y == 900
        assert spec.safe_area.max_text_width == 800
        assert spec.font_size < single.font_size
        assert spec.line_height == 1.08
        assert spec.safe_area.profile == "default"

    def test_non_glow_styles_limit_blur(self) -> None:
        style = StyleManager.get_preset("HORMOZI")
        style.blur = 9.0
        spec = StyleManager.resolve_render_spec(style)
        assert spec.blur <= 1.2

    def test_glow_styles_keep_bounded_blur(self) -> None:
        spec = StyleManager.resolve_render_spec(StyleManager.get_preset("RETRO_WAVE"))
        assert 0 < spec.blur <= 4.0

    def test_model_dump_excludes_internal_preset_key(self) -> None:
        dumped = StyleManager.get_preset("HORMOZI").model_dump()
        assert "preset_key" not in dumped


class TestBackwardCompatibility:
    def test_existing_api_compatible(self) -> None:
        style = StyleManager.get_preset("HORMOZI")
        assert style.font_name == "Montserrat Black"
        assert style.font_size == 120

        style = StyleManager.get_preset("MINIMALIST")
        assert style.font_name == "Helvetica Neue"
        assert style.font_size == 18

    def test_new_fields_optional(self) -> None:
        style = SubtitleStyle(name="Test", font_name="Arial", font_size=24)
        assert style.category == SubtitleCategory.DYNAMIC
        assert style.font_weight == 700
        assert style.background_color == "&H00000000"
