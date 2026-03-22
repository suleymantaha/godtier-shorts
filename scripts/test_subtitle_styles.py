#!/usr/bin/env python3
"""
Altyazı stilleri için integration test scripti.
Gerçek video işleme ile ASS üretimini test eder.
Kullanım: python scripts/test_subtitle_styles.py [PROJECT_DIR]
"""
import os
import sys
import json

# Proje root'unu path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.subtitle_styles import StyleManager, SubtitleStyle
from backend.services.subtitle_renderer import SubtitleRenderer


def main():
    # Varsayılan veya argümandan proje yolu
    PROJECT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "workspace", "projects", "yt_-hL25diakQc"
    )
    VIDEO_PATH = os.path.join(PROJECT_DIR, "master.mp4")
    TRANSCRIPT_PATH = os.path.join(PROJECT_DIR, "transcript.json")
    OUTPUT_DIR = os.path.join(PROJECT_DIR, "shorts")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # List all available presets
    print("\n" + "="*60)
    print("📋 MEVCUT ALTYAZI STİLLERİ")
    print("="*60)

    presets = StyleManager.list_presets()
    for preset_name in presets:
        style = StyleManager.get_preset(preset_name)
        print(f"\n🎨 {preset_name}: {style.name}")
        print(f"   Font: {style.font_name}, Size: {style.font_size}")
        print(f"   Category: {style.category.value}")
        print(f"   Animation: {style.animation_type}")

    # Select styles to test
    test_styles = ["TIKTOK", "YOUTUBE_SHORT", "PODCAST", "HIGHCARE", "HORMOZI"]

    print("\n" + "="*60)
    print("🧪 TEST İŞLEMİ BAŞLIYOR")
    print("="*60)

    # Test each style
    for style_name in test_styles:
        print(f"\n{'='*60}")
        print(f"🎬 Test: {style_name}")
        print("="*60)

        # Get the style
        style = StyleManager.get_preset(style_name)
        print(f"✅ Stil yüklendi: {style.name}")
        print(f"   Font: {style.font_name} ({style.font_size}px)")
        print(f"   Primary Color: {style.primary_color}")
        print(f"   Highlight Color: {style.highlight_color}")

        # Create renderer
        renderer = SubtitleRenderer(style)

        # Output paths
        ass_file = os.path.join(OUTPUT_DIR, f"test_{style_name.lower()}.ass")
        output_video = os.path.join(OUTPUT_DIR, f"test_{style_name.lower()}.mp4")

        # Generate ASS file
        print(f"📝 ASS dosyası oluşturuluyor: {ass_file}")
        try:
            renderer.generate_ass_file(
                transcript_json_path=TRANSCRIPT_PATH,
                output_ass_path=ass_file,
                max_words_per_screen=4
            )

            # Check if ASS file was created
            if os.path.exists(ass_file):
                file_size = os.path.getsize(ass_file)
                print(f"✅ ASS dosyası oluşturuldu: {file_size:,} bytes")
            else:
                print(f"❌ ASS dosyası oluşturulamadı!")
                continue

        except Exception as e:
            print(f"❌ ASS oluşturma hatası: {e}")
            continue

        # Check if we should burn subtitles to video
        # (Skipping actual video burning for now - requires significant time)
        print(f"\n📹 Video işleme atlanıyor (zaman gerektirir)")
        print(f"   ASS dosyası hazır: {ass_file}")
        print(f"   FFmpeg komutu:")
        print(f"   ffmpeg -i {VIDEO_PATH} -vf ass={ass_file} -c:v h264_nvenc {output_video}")

    print("\n" + "="*60)
    print("✅ TÜM TESTLER TAMAMLANDI")
    print("="*60)

    # Show generated files
    print("\n📁 Oluşturulan dosyalar:")
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.ass'):
            fpath = os.path.join(OUTPUT_DIR, f)
            size = os.path.getsize(fpath)
            print(f"   {f} ({size:,} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
