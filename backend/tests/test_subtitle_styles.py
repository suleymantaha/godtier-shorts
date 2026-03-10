"""
backend/tests/test_subtitle_styles.py
=====================================
Subtitle stilleri için unit testler.

Test kapsamı:
- SubtitleStyle modeli validasyonları
- StyleManager preset yönetimi
- Geriye dönük uyumluluk
- Yeni alanlar için varsayılan değerler
"""
import pytest
from backend.services.subtitle_styles import (
    SubtitleStyle, 
    StyleManager, 
    SubtitleCategory
)


class TestSubtitleStyle:
    """SubtitleStyle modeli için unit testler."""
    
    def test_default_style_has_all_fields(self):
        """Varsayılan stil tüm alanları içermeli."""
        style = SubtitleStyle()
        
        # Temel alanlar
        assert style.name == "Custom"
        assert style.font_name == "Arial"
        assert style.font_size == 24
        assert style.primary_color == "&H00FFFFFF"
        assert style.alignment == 2
        assert style.margin_v == 220
        
        # Yeni alanlar (varsayılan değerlerle)
        assert style.category == SubtitleCategory.DYNAMIC
        assert style.font_weight == 700
        assert style.gradient_colors == ["&H00FFFFFF"]
        assert style.gradient_direction == "none"
        assert style.background_color == "&H00000000"
    
    def test_new_fields_have_defaults(self):
        """Yeni alanlar varsayılan değere sahip olmalı."""
        style = SubtitleStyle()
        
        assert style.font_weight == 700  # Varsayılan kalınlık
        assert style.background_color == "&H00000000"  # Şeffaf
        assert style.gradient_colors == ["&H00FFFFFF"]
        assert style.animation_duration == 0.15
        assert style.high_contrast == False
    
    def test_existing_presets_unchanged(self):
        """Mevcut presetler değişmemeli."""
        style = StyleManager.get_preset("HORMOZI")
        assert style.name == "Hormozi Style"
        assert style.font_size == 120
        assert style.animation_type == "pop"
        
        style = StyleManager.get_preset("MRBEAST")
        assert style.name == "MrBeast Gaming"
        assert style.font_size == 130
        assert style.animation_type == "pop"
        
        style = StyleManager.get_preset("MINIMALIST")
        assert style.name == "Minimalist Podcast"
        assert style.font_size == 18
        assert style.animation_type == "fade"
    
    def test_unknown_preset_returns_default(self):
        """Bilinmeyen preset varsayılan dönmeli."""
        style = StyleManager.get_preset("BILINMEYEN")
        assert isinstance(style, SubtitleStyle)
        assert style.name == "Custom"
        assert style.alignment == 2
        assert style.margin_v == 220
    
    def test_case_insensitive_preset_lookup(self):
        """Preset araması büyük-küçük harf duyarsız olmalı."""
        assert StyleManager.get_preset("hormozi") == StyleManager.get_preset("HORMOZI")
        assert StyleManager.get_preset("Hormozi") == StyleManager.get_preset("HORMOZI")
        assert StyleManager.get_preset("mrbeast") == StyleManager.get_preset("MRBEAST")


class TestSubtitleCategory:
    """SubtitleCategory enum için testler."""
    
    def test_all_categories_exist(self):
        """Tüm kategoriler tanımlı olmalı."""
        assert SubtitleCategory.DYNAMIC.value == "dynamic"
        assert SubtitleCategory.MINIMAL.value == "minimal"
        assert SubtitleCategory.CREATIVE.value == "creative"
        assert SubtitleCategory.ACCESSIBLE.value == "accessible"
        assert SubtitleCategory.CORPORATE.value == "corporate"


class TestStyleManager:
    """StyleManager için unit testler."""
    
    def test_list_presets_returns_all(self):
        """Tüm presetler listelenmeli."""
        presets = StyleManager.list_presets()
        
        # Mevcut presetler
        assert "HORMOZI" in presets
        assert "MRBEAST" in presets
        assert "MINIMALIST" in presets
        
        # Yeni presetler
        assert "TIKTOK" in presets
        assert "YOUTUBE_SHORT" in presets
        assert "PODCAST" in presets
        assert "CORPORATE" in presets
        assert "HIGHCARE" in presets
        
        # En yeni presetler
        assert "CYBER_PUNK" in presets
        assert "STORY_TELLER" in presets
        assert "GLOW_KARAOKE" in presets
        assert "GLASS_MORPH" in presets
    
        # En son presetler
        assert "ALI_ABDAAL" in presets
        assert "RETRO_WAVE" in presets
        assert "HACKER_TERMINAL" in presets
        assert "CINEMATIC_FILM" in presets
    
    def test_preset_count(self):
        """Toplam preset sayısı doğru olmalı."""
        presets = StyleManager.list_presets()
        assert len(presets) == 16  # 3 mevcut + 5 yeni + 4 en yeni + 4 en en yeni
    
    def test_new_presets_have_categories(self):
        """Yeni presetler doğru kategoride olmalı."""
        tiktok = StyleManager.get_preset("TIKTOK")
        assert tiktok.category == SubtitleCategory.DYNAMIC
        
        podcast = StyleManager.get_preset("PODCAST")
        assert podcast.category == SubtitleCategory.MINIMAL
        
        corporate = StyleManager.get_preset("CORPORATE")
        assert corporate.category == SubtitleCategory.CORPORATE
        
        highcare = StyleManager.get_preset("HIGHCARE")
        assert highcare.category == SubtitleCategory.ACCESSIBLE
        
        cyber_punk = StyleManager.get_preset("CYBER_PUNK")
        assert cyber_punk.category == SubtitleCategory.CREATIVE

    def test_presets_use_bottom_safe_alignment(self):
        """Tüm presetler alt güvenli bölgeyi kullanmalı."""
        expected_margins = {
            "HORMOZI": 260,
            "MRBEAST": 300,
            "MINIMALIST": 220,
            "TIKTOK": 250,
            "YOUTUBE_SHORT": 280,
            "PODCAST": 220,
            "CORPORATE": 220,
            "HIGHCARE": 220,
        }

        for preset_name, margin_v in expected_margins.items():
            style = StyleManager.get_preset(preset_name)
            assert style.alignment == 2
            assert style.margin_v == margin_v
    
    def test_list_presets_by_category(self):
        """Kategoriye göre preset listeleme çalışmalı."""
        dynamic = StyleManager.list_presets_by_category(SubtitleCategory.DYNAMIC)
        assert "HORMOZI" in dynamic
        assert "MRBEAST" in dynamic
        assert "TIKTOK" in dynamic
        assert "YOUTUBE_SHORT" in dynamic
        
        minimal = StyleManager.list_presets_by_category(SubtitleCategory.MINIMAL)
        assert "MINIMALIST" in minimal
        assert "PODCAST" in minimal
        
        corporate = StyleManager.list_presets_by_category(SubtitleCategory.CORPORATE)
        assert "CORPORATE" in corporate
        
        accessible = StyleManager.list_presets_by_category(SubtitleCategory.ACCESSIBLE)
        assert "HIGHCARE" in accessible
    
    def test_create_custom_style(self):
        """Özel stil oluşturma çalışmalı."""
        style = StyleManager.create_custom_style(
            name="Test Style",
            font_name="Test Font",
            font_size=42,
            category=SubtitleCategory.CREATIVE
        )
        
        assert style.name == "Test Style"
        assert style.font_name == "Test Font"
        assert style.font_size == 42
        assert style.category == SubtitleCategory.CREATIVE
        assert style.alignment == 2
        assert style.margin_v == 220


class TestColorValidation:
    """Renk formatı validasyonu için testler."""
    
    def test_valid_color_format(self):
        """Geçerli renk formatları kabul edilmeli."""
        valid_colors = [
            "&H00FFFFFF",  # Beyaz
            "&H00000000",  # Siyah
            "&H00FFFF00",  # Sarı
            "&H0000FF00",  # Yeşil
            "&H00FF0000",  # Kırmızı
            "&H000000FF",  # Mavi
            "&H80FFFFFF",  # Yarı saydam beyaz
        ]
        
        for color in valid_colors:
            style = SubtitleStyle(primary_color=color)
            assert style.primary_color == color
    
    def test_invalid_color_format_returns_default(self):
        """Geçersiz renk formatı varsayılan beyaza dönmeli."""
        invalid_colors = [
            "FFFFFF",       # &H eksik
            "&HFF",         # Eksik karakter
            "white",        # Hex değil
            "#FFFFFF",      # # formatı değil
        ]
        
        for color in invalid_colors:
            style = SubtitleStyle(primary_color=color)
            # Geçersiz format varsayılan beyaza döner
            assert style.primary_color == "&H00FFFFFF"


class TestFontSizeValidation:
    """Font boyutu validasyonu için testler."""
    
    def test_valid_font_sizes(self):
        """Geçerli font boyutları kabul edilmeli."""
        style = SubtitleStyle(font_size=36)
        assert style.font_size == 36
        
        style = SubtitleStyle(font_size=100)
        assert style.font_size == 100
    
    def test_font_size_minimum(self):
        """Minimum font boyutu uygulanmalı."""
        style = SubtitleStyle(font_size=1)
        assert style.font_size == 8  # Minimum 8
    
    def test_font_size_maximum(self):
        """Maksimum font boyutu uygulanmalı."""
        style = SubtitleStyle(font_size=500)
        assert style.font_size == 200  # Maksimum 200


class TestBackwardCompatibility:
    """Geriye dönük uyumluluk testleri."""
    
    def test_existing_api_compatible(self):
        """Mevcut API çağrıları çalışmalı."""
        # JobRequest'ten gelebilecek çağrılar
        style = StyleManager.get_preset("HORMOZI")
        assert style.font_name == "Montserrat Black"
        assert style.font_size == 120
        
        style = StyleManager.get_preset("MINIMALIST")
        assert style.font_name == "Helvetica Neue"
        assert style.font_size == 18
    
    def test_new_fields_optional(self):
        """Yeni alanlar opsiyonel olmalı (geriye dönük uyumluluk)."""
        # Sadece temel alanlarla stil oluşturabilmeli
        style = SubtitleStyle(
            name="Test",
            font_name="Arial",
            font_size=24
        )
        
        # Yeni alanlar varsayılan değerlerle dolmalı
        assert style.category == SubtitleCategory.DYNAMIC
        assert style.font_weight == 700
        assert style.background_color == "&H00000000"
    
    def test_style_model_dump(self):
        """Model dump işlemi çalışmalı."""
        style = StyleManager.get_preset("HORMOZI")
        data = style.model_dump()
        
        assert "name" in data
        assert "font_name" in data
        assert "font_size" in data
        # Yeni alanlar da dahil
        assert "category" in data
        assert "font_weight" in data
        assert "gradient_colors" in data
