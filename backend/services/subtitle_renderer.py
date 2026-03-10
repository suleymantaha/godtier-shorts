"""
backend/services/subtitle_renderer.py
=======================================
Kinetik altyazı oluşturma ve video'ya yazma servisi.
(eski: src/subtitle_renderer.py)
"""
import os
import json
import subprocess
import threading
import time
from loguru import logger

from backend.config import LOGS_DIR
from backend.services.subtitle_styles import StyleManager, SubtitleStyle

logger.add(
    str(LOGS_DIR / "renderer_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)


class SubtitleRenderer:
    @staticmethod
    def _run_command_with_cancel(
        cmd: list[str],
        *,
        timeout: float,
        cancel_event: threading.Event | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        start = time.time()
        while True:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.communicate()
                raise RuntimeError("Job cancelled by user")
            rc = proc.poll()
            if rc is not None:
                stdout, stderr = proc.communicate()
                return subprocess.CompletedProcess(cmd, rc, stdout, stderr)
            if time.time() - start > timeout:
                proc.kill()
                proc.communicate()
                raise RuntimeError("Altyazı burn işlemi timeout oldu (10 dakika)")
            time.sleep(0.5)

    def __init__(self, style: SubtitleStyle):
        logger.info(f"🎬 Kinetik Altyazı Motoru Başlatıldı. Stil: {style.name}")
        self.style = style

    # ------------------------------------------------------------------
    # Yardımcı metodlar
    # ------------------------------------------------------------------

    def _format_time_ass(self, seconds: float) -> str:
        """Saniyeyi ASS formatına çevirir: H:MM:SS.cs"""
        hours        = int(seconds // 3600)
        minutes      = int((seconds % 3600) // 60)
        secs         = int(seconds % 60)
        centiseconds = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _generate_ass_header(self) -> str:
        s = self.style
        
        is_opaque_box = s.background_color and s.background_color.upper() != "&H00000000"
        border_style = 3 if is_opaque_box else 1
        back_color = s.background_color if is_opaque_box else s.shadow_color
        
        bold_val = "-1" if s.font_weight >= 600 else "0"
        italic_val = "-1" if s.italic else "0"
        underline_val = "-1" if s.underline else "0"
        
        margin_l = int(s.position_x * 1080) if s.position_x != 0.5 else 10
        margin_r = int((1.0 - s.position_x) * 1080) if s.position_x != 0.5 else 10
        
        # Shorts için her zaman 1080x1920 referans alalım (Burn-in sırasında ölçeklenir)
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{s.font_name},{s.font_size},{s.primary_color},&H000000FF,{s.outline_color},{back_color},{bold_val},{italic_val},{underline_val},0,100,100,0,0,{border_style},{s.outline_width},{s.shadow_depth},{s.alignment},{margin_l},{margin_r},{s.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _calculate_animation_tags(self, word_start: float, word_end: float, chunk_start: float, chunk_end: float) -> str:
        """
        Kelimelerin chunk başlangıcına göre ne zaman 'pop' yapacağını hesaplar.
        Yeni God-Tier Dinamik Odak Sistemi:
        - Okunmadan önce: %75 küçülmüş ve şeffaf
        - Okunurken: %140 patlar ve parlak renk olur
        - Okunduktan sonra: %90'a iner ve beyaz olur
        """
        if self.style.animation_type == "none":
            return ""

        relative_start_ms = max(0, int((word_start - chunk_start) * 1000))
        relative_end_ms = max(0, int((word_end - chunk_start) * 1000))
        
        # Eğer word start ile chunk start mantıksız şekilde ters düştüyse (0'landıysa) minimal süre ver
        if relative_end_ms <= relative_start_ms:
            relative_end_ms = relative_start_ms + 100
            
        pop_duration = min(150, relative_end_ms - relative_start_ms)
        if pop_duration < 100: 
            pop_duration = 150
        pop_end_ms = relative_start_ms + pop_duration

        if self.style.animation_type == "pop":
            c_hi = self.style.highlight_color
            c_pri = self.style.primary_color
            
            # Başlangıç durumu: Küçültülmüş
            init = r"{\fscx80\fscy80}"
            
            # Okunma anı: Kesin olarak en az pop_duration (150ms) boyunca ekranda tam parlak kalmasını garantile
            # 10ms animasyon veriyoruz ki renderer bu frameleri skip etmesin
            active = fr"{{\t({relative_start_ms},{relative_start_ms+10},\c{c_hi}\fscx140\fscy140)}}"
            
            # Okunma sonrası: Ana renk + %100 
            post = fr"{{\t({pop_end_ms},{pop_end_ms+100},\c{c_pri}\fscx100\fscy100)}}"
            
            return init + active + post
                   
        elif self.style.animation_type == "fade":
            return fr"{{\fad(100,100)}}"
            
        elif self.style.animation_type == "shake":
            c_hi = self.style.highlight_color
            c_pri = self.style.primary_color
            
            init = r"{\fscx100\fscy100}"
            active = fr"{{\t({relative_start_ms},{relative_start_ms+25},\c{c_hi}\frz5\frx10)\t({relative_start_ms+25},{relative_start_ms+50},\frz-5\frx-10)\t({relative_start_ms+50},{relative_start_ms+75},\frz0\frx0)}}"
            post = fr"{{\t({pop_end_ms},{pop_end_ms+100},\c{c_pri})}}"
            return init + active + post
            
        elif self.style.animation_type == "typewriter":
            c_pri = self.style.primary_color
            init = r"{\alpha&HFF&}"
            active = fr"{{\t({relative_start_ms},{relative_start_ms+1},\alpha&H00&)}}"
            post = fr"{{\c{c_pri}}}"
            return init + active + post
            
        elif self.style.animation_type == "slide_up":
            c_pri = self.style.primary_color
            init = r"{\fscy0\alpha&HFF&}"
            active = fr"{{\t({relative_start_ms},{relative_start_ms+100},\fscy100\alpha&H00&)}}"
            post = fr"{{\c{c_pri}}}"
            return init + active + post
            
        return ""

    def _smart_chunking(self, words: list[dict], max_words: int = 4) -> list[list[dict]]:
        """Noktalama işaretlerine ve boşluklara duyarlı kelime gruplama sistemi."""
        chunks = []
        current_chunk = []
        
        for i, word in enumerate(words):
            if "start" not in word or "end" not in word:
                continue
                
            current_chunk.append(word)
            
            # 1. Uzun duraksamalar (>0.4 saniye) chunk'ı böler
            next_word = words[i+1] if i + 1 < len(words) else None
            time_gap = (next_word["start"] - word["end"]) if next_word and "start" in next_word else 0
            
            # 2. Noktalama işaretleri
            text = word.get("word", "").strip()
            has_strong_punct = any(p in text for p in [".", "!", "?", "—"])
            has_weak_punct = "," in text
            
            should_break = False
            
            if len(current_chunk) >= max_words:
                should_break = True
            elif time_gap > 0.4:
                should_break = True
            elif has_strong_punct:
                should_break = True
            elif has_weak_punct and len(current_chunk) >= 2:
                should_break = True
                
            if should_break:
                chunks.append(current_chunk)
                current_chunk = []
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def _resolve_overlaps(self, words: list[dict]) -> list[dict]:
        """Kelimeler arası zaman çakışmalarını sıfırlar."""
        resolved = []
        for w in words:
            if not resolved:
                resolved.append(w)
                continue
                
            prev = resolved[-1]
            if w["start"] < prev["end"]:
                # Çakışma var: Önceki kelimeyi mevcut kelimenin başlangıcında bitir
                prev["end"] = w["start"]
                # Eğer önceki kelimenin süresi 0'dan küçük olduysa (çok hızlı söylenmişse), arayı minimal aç
                if prev["end"] <= prev["start"]:
                    prev["end"] = prev["start"] + 0.01 
                    w["start"] = prev["end"]
            
            resolved.append(w)
        return resolved

    @staticmethod
    def _canonicalize_text(text: str) -> str:
        normalized = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower())
        return " ".join(normalized.split())

    def _build_words_from_segment_text(self, segment: dict) -> list[dict]:
        text = str(segment.get("text", "")).strip()
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))

        if not text or end <= start:
            return []

        tokens = [token for token in text.split() if token]
        if not tokens:
            return []

        total_duration = max(end - start, 0.01)
        word_duration = total_duration / len(tokens)
        words: list[dict] = []

        for idx, token in enumerate(tokens):
            word_start = start + (idx * word_duration)
            word_end = end if idx == len(tokens) - 1 else start + ((idx + 1) * word_duration)
            words.append({
                "word": token,
                "start": word_start,
                "end": word_end,
                "score": 1.0,
            })

        return words

    def _flatten_render_words(self, segments: list[dict]) -> list[dict]:
        all_words: list[dict] = []

        for segment in segments:
            segment_words = [
                word
                for word in segment.get("words", []) or []
                if word.get("word") and "start" in word and "end" in word
            ]

            segment_text = self._canonicalize_text(str(segment.get("text", "")))
            words_text = self._canonicalize_text(
                " ".join(str(word.get("word", "")).strip() for word in segment_words)
            )

            if not segment_words or (segment_text and segment_text != words_text):
                all_words.extend(self._build_words_from_segment_text(segment))
            else:
                all_words.extend(segment_words)

        return all_words

    @logger.catch
    def generate_ass_file(
        self,
        whisperx_json_path: str,
        output_ass_path: str = "dynamic_subs.ass",
        max_words_per_screen: int = 4,
    ) -> str:
        """Smart Chunker ve Karaoke kelime animasyonları içeren ASS üreticisi."""
        logger.info(f"📝 WhisperX NLP verisi işleniyor: {whisperx_json_path}")

        with open(whisperx_json_path, "r", encoding="utf-8") as f:
            segments = json.load(f)

        ass_lines: list[str] = []
        all_words = self._flatten_render_words(segments)

        # Zaman çakışmalarını temizle
        all_words = self._resolve_overlaps([w for w in all_words if "start" in w and "end" in w])

        chunks = self._smart_chunking(all_words, max_words=max_words_per_screen)

        for i, chunk in enumerate(chunks):
            if not chunk: continue
            
            chunk_start_sec = chunk[0]["start"]
            chunk_end_sec = chunk[-1]["end"]
            
            # Flicker prevention: Bridge the gap between consecutive chunks
            # If the gap is less than 0.4s, extend the current chunk to the next chunk's start.
            if i + 1 < len(chunks) and chunks[i+1]:
                next_chunk_start = chunks[i+1][0]["start"]
                gap = next_chunk_start - chunk_end_sec
                if 0 <= gap < 0.4:
                    chunk_end_sec = next_chunk_start
            
            chunk_start_ass = self._format_time_ass(chunk_start_sec)
            chunk_end_ass   = self._format_time_ass(chunk_end_sec)

            dialogue_text = ""
            for i, w in enumerate(chunk):
                word_text = w["word"].strip()
                w_start = w["start"]
                w_end = w["end"]
                
                anim_tags = self._calculate_animation_tags(w_start, w_end, chunk_start_sec, chunk_end_sec)
                
                c_pri = self.style.primary_color
                
                # Her kelimenin başına reset tag koyalım
                if self.style.blur > 0:
                    reset_tag = fr"{{\r\blur{self.style.blur}\c{c_pri}}}"
                else:
                    reset_tag = fr"{{\r\c{c_pri}}}"
                
                dialogue_text += f"{reset_tag}{anim_tags}{word_text} "

            ass_lines.append(
                f"Dialogue: 0,{chunk_start_ass},{chunk_end_ass},Main,,0,0,0,,{dialogue_text.strip()}\n"
            )

        ass_content = self._generate_ass_header() + "".join(ass_lines)

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        logger.success(f"✅ NLP Akıllı ASS dosyası oluşturuldu: {output_ass_path}")
        return output_ass_path

    @logger.catch
    def burn_subtitles_to_video(
        self,
        input_video: str,
        ass_file: str,
        output_video: str,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Altyazıyı videoya kalıcı olarak işler. NVENC dener, başarısızsa CPU (libx264) fallback."""
        logger.info(f"🔥 Akıllı Altyazılar işleniyor → {output_video}")

        ass_abs = os.path.abspath(ass_file).replace("\\", "/")
        cmd_nvenc = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-i", input_video,
            "-vf", f"ass='{ass_abs}'",
            "-c:v", "h264_nvenc",
            "-preset", "p6",
            "-b:v", "8M",
            "-c:a", "copy",
            output_video,
        ]
        cmd_cpu = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", f"ass='{ass_abs}'",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            output_video,
        ]
        try:
            result = self._run_command_with_cancel(
                cmd_nvenc,
                timeout=600,
                cancel_event=cancel_event,
            )
            if result.returncode == 0:
                logger.success("🎉 Altyazı işlendi (NVENC), video hazır.")
                return
            stderr = result.stderr.decode("utf-8", errors="replace")
            if "cuda" in stderr.lower() or "nvenc" in stderr.lower() or "hwaccel" in stderr.lower():
                logger.warning("⚠️ CUDA/NVENC kullanılamadı, CPU fallback deneniyor...")
                cpu_result = self._run_command_with_cancel(cmd_cpu, timeout=600, cancel_event=cancel_event)
                if cpu_result.returncode != 0:
                    raise RuntimeError("CPU fallback ile altyazı burn başarısız")
                logger.success("🎉 Altyazı işlendi (CPU), video hazır.")
            else:
                logger.error(f"FFmpeg Error: {stderr[-1000:]}")
                raise subprocess.CalledProcessError(result.returncode, cmd_nvenc, result.stdout, result.stderr)
        except RuntimeError:
            raise