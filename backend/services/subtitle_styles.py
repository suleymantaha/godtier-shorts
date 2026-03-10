"""
backend/services/subtitle_styles.py
=====================================
Subtitle stil tanımları ve StyleManager.
(eski: src/subtitle_styles.py)

Genişletme (2026-03-07):
- SubtitleCategory enum eklendi
- Yeni stil alanları eklendi (geriye dönük uyumlu)
- Yeni preset stiller eklendi
"""
import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from loguru import logger


class SubtitleCategory(str, Enum):
    """Altyazı kategorileri - stillerin gruplandırılması için."""
    DYNAMIC = "dynamic"      # Dinamik/enerjik (HORMOZI, MRBEAST)
    MINIMAL = "minimal"      # Minimal/sade (MINIMALIST)
    CREATIVE = "creative"   # Yaratıcı/özelleştirilmiş
    ACCESSIBLE = "accessible" # Erişilebilirlik odaklı
    CORPORATE = "corporate"  # Kurumsal/profesyonel


class SubtitleStyle(BaseModel):
    """Kullanıcının veya sistemin belirleyeceği altyazı şablonu.
    
    Genişletilmiş versiyon (2026-03-07):
    - Tüm yeni alanlar varsayılan değere sahiptir
    - Geriye dönük uyumluluk korunmaktadır
    """
    # --- Temel Alanlar (MEVCUT - DEĞİŞTİRİLMEDİ) ---
    name: str            = Field(default="Custom")
    font_name: str       = Field(default="Arial")
    font_size: int       = Field(default=24)
    primary_color: str   = Field(default="&H00FFFFFF")   # Beyaz
    highlight_color: str = Field(default="&H0000FFFF")   # Sarı
    outline_color: str   = Field(default="&H00000000")   # Siyah
    outline_width: float = Field(default=2.0)
    shadow_color: str    = Field(default="&H80000000")
    shadow_depth: float  = Field(default=1.5)
    alignment: int       = Field(default=2)              # 2 = Alt orta (ASS numpad anchor)
    margin_v: int        = Field(default=220)
    animation_type: str  = Field(default="pop")          # pop | slide_up | fade | none
    
    # --- YENİ ALANLAR (geriye dönük uyumlu - varsayılan değerlerle) ---
    
    # Kategori
    category: SubtitleCategory = Field(default=SubtitleCategory.DYNAMIC)
    
    # Font geliştirmeleri
    font_weight: int = Field(default=700)        # 100-900 arası kalınlık, varsayılan bold
    italic: bool = Field(default=False)
    underline: bool = Field(default=False)
    
    # Renk paleti (gradient desteği için)
    gradient_colors: list[str] = Field(default_factory=lambda: ["&H00FFFFFF"])
    gradient_direction: str = Field(default="none")  # none|horizontal|vertical
    
    # Konum hassasiyeti
    position_x: float = Field(default=0.5, ge=0.0, le=1.0)  # %0-100
    position_y: float = Field(default=0.9, ge=0.0, le=1.0)
    
    # Efektler
    blur: float = Field(default=0.0, ge=0.0, le=10.0)
    border_radius: float = Field(default=0.0, ge=0.0, le=50.0)
    background_color: str = Field(default="&H00000000")  # Şeffaf
    
    # Animasyon detayları
    animation_duration: float = Field(default=0.15, ge=0.0, le=2.0)  # Saniye
    animation_easing: str = Field(default="ease-out")  # ease-out|ease-in|linear
    
    # Erişilebilirlik
    high_contrast: bool = Field(default=False)
    large_text: bool = Field(default=False)
    
    @field_validator("primary_color", "highlight_color", "outline_color", "shadow_color", "background_color")
    @classmethod
    def validate_ass_color_format(cls, v: str) -> str:
        """ASS renk formatını doğrular: &H00RRGGBB veya &H80RRGGBB"""
        if not re.match(r'^&H[0-9A-Fa-f]{8}$', v):
            logger.warning(f"⚠️ Renk formatı uygun değil: {v}, varsayılan beyaz kullanılıyor")
            return "&H00FFFFFF"
        return v
    
    @field_validator("font_size")
    @classmethod
    def validate_font_size(cls, v: int) -> int:
        """Font boyutunu sınırlandırır."""
        if v < 8:
            logger.warning(f"⚠️ Font boyutu çok küçük: {v}, minimum 8 kullanılıyor")
            return 8
        if v > 200:
            logger.warning(f"⚠️ Font boyutu çok büyük: {v}, maksimum 200 kullanılıyor")
            return 200
        return v


class StyleManager:
    """Altyazı stillerini yöneten sınıf."""
    
    _PRESETS: dict[str, SubtitleStyle] = {
        # --- MEVCUT PRESETLER (DEĞİŞTİRİLMEDİ) ---
        "HORMOZI": SubtitleStyle(
            name="Hormozi Style",
            category=SubtitleCategory.DYNAMIC,
            font_name="Montserrat Black",
            font_size=120, # 85 -> 120 (Full HD Shorts için!)
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
            font_size=130, # Dev font
            primary_color="&H00FFFFFF",
            highlight_color="&H0000FF00",
            outline_width=12.0,
            shadow_depth=0.0,
            alignment=2,
            margin_v=300, # Biraz daha yukarıda
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
        
        # --- YENİ PRESETLER (2026-03-07) ---
        "TIKTOK": SubtitleStyle(
            name="TikTok Vertical",
            category=SubtitleCategory.DYNAMIC,
            font_name="Montserrat Black",
            font_size=140,
            primary_color="&H00FFFFFF",
            highlight_color="&H00FF00FF",  # TikTok cyan/magenta
            gradient_colors=["&H00FFFFFF", "&H00FF00FF"],
            gradient_direction="horizontal",
            outline_width=8.0,
            shadow_depth=3.0,
            alignment=2,  # Alt orta
            margin_v=250,
            position_y=0.85,
            animation_type="pop",
            animation_duration=0.12,
        ),
        "YOUTUBE_SHORT": SubtitleStyle(
            name="YouTube Shorts",
            category=SubtitleCategory.DYNAMIC,
            font_name="Poppins Bold",
            font_size=110,
            primary_color="&H00FFFFFF",
            highlight_color="&H0000FFFF",
            outline_width=10.0,
            shadow_depth=4.0,
            alignment=2,
            margin_v=280,
            animation_type="pop",
            background_color="&H80000000",  # Yarı siyah arka plan
            border_radius=8.0,
        ),
        "PODCAST": SubtitleStyle(
            name="Podcast Style",
            category=SubtitleCategory.MINIMAL,
            font_name="Inter",
            font_size=32,
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
            font_size=36,
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
            font_size=48,
            font_weight=900,
            primary_color="&H00FFFF00",  # Sarı
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
            font_size=120,
            primary_color="&H00FFFFFF",
            outline_color="&H00FF00FF",   # Macenta çerçeve
            outline_width=4.0,
            shadow_color="&H00FFFF00",    # Cyan (Turkuaz) gölge - Glitch efekti için
            shadow_depth=6.0,
            gradient_colors=["&H00FFFFFF", "&H0000FFFF"],
            gradient_direction="vertical",
            animation_type="shake",       # Titreme animasyonu
        ),
        "STORY_TELLER": SubtitleStyle(
            name="Storyteller",
            category=SubtitleCategory.CREATIVE,
            font_name="Courier New",      # Daktilo fontu
            font_size=40,
            font_weight=400,
            primary_color="&H00E0E0E0",
            alignment=1,                  # 1 = Sol alt köşe
            margin_v=150,
            position_x=0.1,               # Ekranın solundan başlasın
            animation_type="typewriter",  # Yeni animasyon tipi
            animation_duration=0.05,
        ),
        "GLOW_KARAOKE": SubtitleStyle(
            name="Neon Karaoke",
            category=SubtitleCategory.CREATIVE,
            font_name="Montserrat ExtraBold",
            font_size=110,
            primary_color="&H80FFFFFF",   # %50 Transparan beyaz (arka plan kelimeler için)
            highlight_color="&H0000FFFF", # Parlak Sarı (vurgu rengi)
            outline_width=2.0,
            blur=4.0,                     # Hafif bir ışık hüzmesi efekti
            animation_type="pop",
            animation_duration=0.1,
            margin_v=280
        ),
        "GLASS_MORPH": SubtitleStyle(
            name="Glassmorphism",
            category=SubtitleCategory.CREATIVE,
            font_name="Inter SemiBold",
            font_size=45,
            primary_color="&H20FFFFFF",    # Çok şeffaf beyaz
            background_color="&H80FFFFFF", # Arkadaki videoyu bulanıklaştıran beyaz buzlu cam
            outline_width=1.0,
            outline_color="&H40000000",
            blur=10.0,                     # Arkayı bulanık gösteren temel efekt
            border_radius=15.0,            # Köşeleri yuvarlatılmış şık bir kutu
            alignment=2,
            margin_v=100
        ),
        "ALI_ABDAAL": SubtitleStyle(
            name="Productivity Vlog",
            category=SubtitleCategory.MINIMAL,
            font_name="Outfit Bold",
            font_size=55,
            primary_color="&H00FFFFFF",
            highlight_color="&H0032CD32",  # Hoş bir pastel/lime yeşili
            outline_width=0.0,
            shadow_depth=3.0,
            shadow_color="&H60000000",     # Çok yumuşak %40 siyah gölge
            margin_v=240,
            animation_type="pop",
            animation_duration=0.1,        # Çok hızlı pop
        ),
        "RETRO_WAVE": SubtitleStyle(
            name="80s Synthwave",
            category=SubtitleCategory.CREATIVE,
            font_name="Vampire",           # Retro/Sci-Fi font (veya Impact)
            font_size=100,
            primary_color="&H00FF00FF",    # Neon Pembe
            highlight_color="&H0000FFFF",  # Cyan (Camgöbeği)
            outline_width=6.0,
            outline_color="&H00000000",
            blur=6.0,                      # Güçlü neon parlaklık
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
            font_size=38,
            primary_color="&H0000FF00",    # Matrix Yesili
            highlight_color="&H00FFFFFF",  # Beyaz (vurgular)
            background_color="&HB0000000", # Neredeyse mat siyah arka plan
            outline_width=0.0,
            shadow_depth=0.0,
            border_radius=0.0,             # Keskin terminal köşesi
            alignment=7,                   # 7 = Sol Üst köşeye yakın (ancak margin ile)
            margin_v=140,
            position_x=0.05,
            position_y=0.15,
            animation_type="typewriter",
            animation_duration=0.03,       # Çok hızlı terminal yazısı
        ),
        "CINEMATIC_FILM": SubtitleStyle(
            name="Documentary Film",
            category=SubtitleCategory.MINIMAL,
            font_name="Times New Roman",
            font_size=42,
            italic=True,
            primary_color="&H00E6E6E6",    # Hafif kırık sinematik beyaz
            highlight_color="&H00D4AF37",  # Soluk altın sarısı
            outline_width=1.0,
            outline_color="&H40000000",
            shadow_depth=2.0,
            shadow_color="&H90000000",
            alignment=2,
            margin_v=80,                   # Ekranda en aşağı noktalardan birine iner
            animation_type="fade",
            animation_duration=0.4,        # Ağır ve dramatik geçiş
        ),
    }

    @classmethod
    @logger.catch
    def get_preset(cls, preset_name: str) -> SubtitleStyle:
        """İsme göre hazır stil döner; bulunamazsa varsayılan Custom döner."""
        key = preset_name.upper()
        if key in cls._PRESETS:
            logger.info(f"🎨 Stil yüklendi: {preset_name}")
            return cls._PRESETS[key]
        logger.warning(f"⚠️ '{preset_name}' bulunamadı, Custom yükleniyor.")
        return SubtitleStyle()

    @classmethod
    def list_presets(cls) -> list[str]:
        """Tüm mevcut preset adlarını döner."""
        return list(cls._PRESETS.keys())
    
    @classmethod
    def list_presets_by_category(cls, category: SubtitleCategory) -> list[str]:
        """Belirli bir kategorideki preset adlarını döner."""
        return [
            key for key, style in cls._PRESETS.items() 
            if style.category == category
        ]
    
    @classmethod
    def create_custom_style(
        cls,
        name: str,
        font_name: str = "Arial",
        font_size: int = 36,
        primary_color: str = "&H00FFFFFF",
        category: SubtitleCategory = SubtitleCategory.CREATIVE,
        **kwargs
    ) -> SubtitleStyle:
        """Özel stil oluşturucu fabrika metodu."""
        return SubtitleStyle(
            name=name,
            font_name=font_name,
            font_size=font_size,
            primary_color=primary_color,
            category=category,
            **kwargs
        )
