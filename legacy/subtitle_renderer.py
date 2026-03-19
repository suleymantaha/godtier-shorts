import os
import json
import subprocess
from loguru import logger
from subtitle_styles import StyleManager, SubtitleStyle

# --- LOGLAMA ---
os.makedirs("logs", exist_ok=True)
logger.add("logs/renderer_{time:YYYY-MM-DD}.log", rotation="50 MB", retention="10 days", level="DEBUG")

class SubtitleRenderer:
    def __init__(self, style: SubtitleStyle):
        logger.info(f"🎬 Kinetik Altyazı Motoru Başlatıldı. Aktif Stil: {style.name}")
        self.style = style

    @staticmethod
    def _is_nvenc_error(stderr_text: str) -> bool:
        lowered = stderr_text.lower()
        patterns = (
            "nvenc",
            "cuda",
            "hwaccel",
            "cannot load libnvidia-encode",
            "no nvenc capable devices found",
            "frame dimension less than the minimum supported value",
        )
        return any(pattern in lowered for pattern in patterns)

    def _format_time_ass(self, seconds: float) -> str:
        """Saniyeyi ASS dosyasının istediği H:MM:SS.cs formatına çevirir (Örn: 1:23:45.67)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _generate_ass_header(self, video_width: int = 1080, video_height: int = 1920) -> str:
        """ASS dosyasının bel kemiği (Çözünürlük ve Stil Tanımları)"""
        s = self.style
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 1[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{s.font_name},{s.font_size},{s.primary_color},&H000000FF,{s.outline_color},{s.shadow_color},-1,0,0,0,100,100,0,0,1,{s.outline_width},{s.shadow_depth},{s.alignment},10,10,{s.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        return header

    def _apply_animation_tag(self) -> str:
        """Seçilen animasyona göre ASS Override Tag'i üretir."""
        if self.style.animation_type == "pop":
            # Kelime okunduğu an %130 büyür ve 150ms içinde %100'e geri döner
            return r"{\fscx130\fscy130\t(0,150,\fscx100\fscy100)}"
        elif self.style.animation_type == "slide_up":
            # Aşağıdan yukarı hafif kayarak gelir
            return r"{\move(540,1000,540,960,0,200)}"
        elif self.style.animation_type == "fade":
            return r"{\fad(100,100)}"
        return ""

    @logger.catch
    def generate_ass_file(self, whisperx_json_path: str, output_ass_path: str = "dynamic_subs.ass", max_words_per_screen: int = 3):
        """WhisperX kelimelerini 3'erli gruplar (chunk) halinde ekrana dizer, okunan kelimeyi parlatır."""
        logger.info(f"📝 WhisperX verisi işleniyor: {whisperx_json_path}")
        
        try:
            with open(whisperx_json_path, "r", encoding="utf-8") as f:
                segments = json.load(f)
        except Exception as e:
            logger.error(f"❌ JSON okunamadı: {str(e)}")
            raise

        ass_content = self._generate_ass_header()

        # WhisperX segmentleri içindeki kelimeleri gruplama (Chunking) mantığı
        for segment in segments:
            words = segment.get("words",[])
            if not words:
                continue

            # Kelimeleri max_words_per_screen sayısına göre böl (Örn: Ekranda en fazla 3 kelime kalsın)
            for i in range(0, len(words), max_words_per_screen):
                chunk = words[i:i + max_words_per_screen]
                if not chunk: continue
                
                chunk_start = chunk[0]["start"]
                chunk_end = chunk[-1]["end"]
                
                start_time_str = self._format_time_ass(chunk_start)
                end_time_str = self._format_time_ass(chunk_end)

                # Kinetik Vurgu Mantığı (Karaoke Style)
                # Bu chunk ekrandayken, her bir kelimenin okunma süresi boyunca farklı bir satır (Event) üretiriz.
                for current_word_idx, active_word in enumerate(chunk):
                    if "start" not in active_word or "end" not in active_word:
                        continue # Zaman damgası olmayan kelimeleri atla
                        
                    active_start = self._format_time_ass(active_word["start"])
                    active_end = self._format_time_ass(active_word["end"])
                    
                    dialogue_text = ""
                    for w_idx, w in enumerate(chunk):
                        word_text = w["word"]
                        if w_idx == current_word_idx:
                            # AKTİF KELİME: Rengini değiştir ve animasyon (Pop/Zıplama) ekle
                            anim_tag = self._apply_animation_tag()
                            dialogue_text += f"{anim_tag}{{\\c{self.style.highlight_color}}}{word_text}{{\\c{self.style.primary_color}}} "
                        else:
                            # PASİF KELİME: Normal renkte kalsın
                            dialogue_text += f"{word_text} "
                    
                    # Her kelimenin okunduğu o kısacık süre (active_start -> active_end) için ekrana basıyoruz.
                    ass_line = f"Dialogue: 0,{active_start},{active_end},Main,,0,0,0,,{dialogue_text.strip()}\n"
                    ass_content += ass_line

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
            
        logger.success(f"✅ Dinamik ASS Altyazı dosyası oluşturuldu: {output_ass_path}")
        return output_ass_path

    @logger.catch
    def burn_subtitles_to_video(self, input_video: str, ass_file: str, output_video: str):
        """Oluşturulan altyazı dosyasını GPU/NVENC kullanarak videonun içine kazır (Hardcode)"""
        logger.info(f"🔥 Altyazılar videoya işleniyor (Donanım Hızlandırması Aktif)... Hedef: {output_video}")
        
        # FFmpeg'in ass filtresi yolları okurken Windows/Linux uyuşmazlığı yapabilir, mutlak yol alalım.
        ass_file_abs = os.path.abspath(ass_file).replace("\\", "/")
        
        # NVENC encode deneriz; sorun olursa CPU fallback kullanırız.
        cmd_nvenc = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"ass='{ass_file_abs}'", # Altyazı filtresi
            "-c:v", "h264_nvenc", # NVENC ile encode (Işık hızı)
            "-preset", "p6",
            "-b:v", "8M",
            "-c:a", "copy", # Sesi elleme aynen aktar
            output_video
        ]
        cmd_cpu = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"ass='{ass_file_abs}'",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            output_video
        ]
        
        try:
            subprocess.run(cmd_nvenc, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            logger.success("🎉 İŞLEM BİTTİ! Viral videon sosyal medyaya yüklenmeye hazır.")
        except subprocess.CalledProcessError as e:
            stderr_text = e.stderr.decode("utf-8", errors="replace")
            if not self._is_nvenc_error(stderr_text):
                logger.error(f"❌ FFmpeg Render Hatası: {stderr_text}")
                raise

            logger.warning("⚠️ NVENC kullanılamadı, CPU fallback (libx264) deneniyor...")
            try:
                subprocess.run(cmd_cpu, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                logger.success("🎉 İŞLEM BİTTİ! Video CPU fallback ile hazırlandı.")
            except subprocess.CalledProcessError as cpu_error:
                cpu_stderr = cpu_error.stderr.decode("utf-8", errors="replace")
                logger.error(f"❌ CPU fallback de başarısız oldu: {cpu_stderr}")
                raise

# --- SİSTEMİ TEST ETME ---
if __name__ == "__main__":
    # 1. Kullanıcı UI'dan bir stil seçer
    chosen_style = StyleManager.get_preset("HORMOZI")
    
    # Not: UI'dan özel (Custom) stil gelseydi şöyle olurdu:
    # chosen_style = SubtitleStyle(name="MyStyle", primary_color="&H00FF0000", animation_type="slide_up")
    
    # 2. Motoru başlat
    renderer = SubtitleRenderer(style=chosen_style)
    
    # 3. WhisperX verisinden (.json) -> Kinetik Altyazı Dosyası (.ass) Üret
    # (Önceki aşamada elde ettiğimiz video_metadata.json'u kullanıyoruz)
    try:
        ass_path = renderer.generate_ass_file(
            whisperx_json_path="video_metadata.json", 
            max_words_per_screen=3 # Ekranda 3 kelime kalsın (Tam Shorts kıvamı)
        )
        
        # 4. Görüntü işleme aşamasında oluşturduğumuz dikey (kırpılmış) videoya bu yazıyı göm
        renderer.burn_subtitles_to_video(
            input_video="viral_short_01.mp4", 
            ass_file=ass_path, 
            output_video="FINAL_VIRAL_SHORT.mp4"
        )
    except Exception as e:
        logger.error(f"Sistem Çöktü: {str(e)}")
