"""
backend/core/orchestrator.py
==============================
Tüm sistemi tek bir arayüz altında toplayan ana orkestratör.
(eski: src/main.py → GodTierShortsCreator)
"""
import asyncio
import json
import os
import re
import shutil
import threading
import time
from typing import Callable, Optional

from loguru import logger

from backend.config import (
    LOGS_DIR, DOWNLOADS_DIR, TEMP_DIR, OUTPUTS_DIR, METADATA_DIR,
    MASTER_VIDEO, MASTER_AUDIO, VIDEO_METADATA, YOLO_MODEL_PATH,
    ProjectPaths,
)
from backend.services.transcription    import run_transcription, release_whisper_models
from backend.services.viral_analyzer   import ViralAnalyzer
from backend.services.video_processor  import VideoProcessor
from backend.services.subtitle_styles  import StyleManager
from backend.services.subtitle_renderer import SubtitleRenderer

logger.add(
    str(LOGS_DIR / "orchestrator_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)

StatusCallback = Callable[[dict], None]


class GodTierShortsCreator:
    def __init__(self, ui_callback: Optional[StatusCallback] = None, cancel_event: Optional[threading.Event] = None):
        """
        ui_callback: {'message': str, 'progress': int} dict'i alan çağrı.
        """
        logger.info("👑 GOD-TIER SHORTS ORKESTRATÖRÜ BAŞLATILDI 👑")
        self.ui_callback = ui_callback
        self.cancel_event = cancel_event or threading.Event()
        self.project: Optional[ProjectPaths] = None

        self.analyzer       = ViralAnalyzer(engine="local")
        self.video_processor = VideoProcessor(
            model_version=str(YOLO_MODEL_PATH),
            device="cuda",
        )

    def cleanup_gpu(self) -> None:
        try:
            release_whisper_models()
        except Exception:
            pass
        try:
            self.video_processor.cleanup_gpu()
        except Exception:
            pass

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise RuntimeError("Job cancelled by user")

    def _validate_youtube_url(self, url: str) -> None:
        """YouTube URL'sinin (veya 11 haneli video ID'sinin) güvenliğini ve doğruluğunu kontrol eder."""
        # Check for bare 11-character video ID first
        if re.match(r'^[0-9A-Za-z_-]{11}$', url):
            return

        # Check for full URL strictly
        youtube_regex = re.compile(
            r'^(https?://)?(www\.)?'
            r'(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)'
            r'([0-9A-Za-z_-]{11})(&.*)?$'
        )
        if not youtube_regex.match(url):
            raise ValueError(f"Geçersiz veya güvensiz YouTube URL formatı: {url}")

    async def _run_command_with_cancel_async(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ) -> tuple[int, str, str]:
        """Runs a command asynchronously with cancellation support without blocking the event loop."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _check_cancel():
            while proc.returncode is None:
                if self.cancel_event.is_set():
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    raise RuntimeError("Job cancelled by user")
                await asyncio.sleep(0.5)

        cancel_task = asyncio.create_task(_check_cancel())

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            cancel_task.cancel()
            return proc.returncode or 0, stdout_bytes.decode(errors='replace'), stderr_bytes.decode(errors='replace')
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            cancel_task.cancel()
            raise RuntimeError(error_message)

    # Note: Keeping synchronous signature temporarily backward-compat if anything calls it sync,
    # but actual implementation blocks the current thread until the async work is done.
    # We will update pipeline calls immediately after this.
    def _run_command_with_cancel(
        self,
        cmd: list[str],
        *,
        timeout: float,
        error_message: str,
    ) -> asyncio.subprocess.Process:
        """DEPRECATED: Use _run_command_with_cancel_async for new code."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rc, out, err = loop.run_until_complete(
            self._run_command_with_cancel_async(cmd, timeout=timeout, error_message=error_message)
        )
        loop.close()
        
        # Mock CompletedProcess for backward compatibility in the short term
        class MockCompletedProcess:
            def __init__(self, c, r, o, e):
                self.args = c
                self.returncode = r
                self.stdout = o
                self.stderr = e
        return MockCompletedProcess(cmd, rc, out, err)


    @staticmethod
    def _normalize_transcript_payload(transcript_data: list) -> list[dict]:
        normalized: list[dict] = []
        for segment in transcript_data:
            if hasattr(segment, "model_dump"):
                normalized.append(segment.model_dump())
            elif isinstance(segment, dict):
                normalized.append(segment)
            else:
                normalized.append(dict(segment))
        return normalized

    @staticmethod
    def _build_clip_metadata(
        transcript_data: list[dict],
        *,
        viral_metadata: Optional[dict] = None,
        render_metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "transcript": transcript_data,
            "viral_metadata": viral_metadata,
            "render_metadata": render_metadata,
        }

    def _load_project_transcript(self) -> list[dict]:
        if self.project is None:
            raise RuntimeError("Proje bağlamı bulunamadı.")
        if not self.project.transcript.exists():
            raise FileNotFoundError(f"Transkript bulunamadı: {self.project.transcript}")

        with open(self.project.transcript, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Durum bildirimi
    # ------------------------------------------------------------------

    def _update_status(self, message: str, progress: int) -> None:
        logger.info(f"[{progress}%] ⏳ {message}")
        if self.ui_callback:
            self.ui_callback({"message": message, "progress": progress})

    # ------------------------------------------------------------------
    # Video indirme
    # ------------------------------------------------------------------

    async def download_full_video_async(self, url: str, project_paths: Optional[ProjectPaths] = None, resolution: str = "best") -> tuple[str, str]:
        """En yüksek kalitede veya seçilmiş kalitede .mp4 indirir. Async versiyon."""
        self._validate_youtube_url(url)
        self._update_status("YouTube'dan orijinal video indiriliyor...", 10)

        video_file = str(project_paths.master_video if project_paths else MASTER_VIDEO)
        audio_file = str(project_paths.master_audio if project_paths else MASTER_AUDIO)

        if resolution != "best":
            height = ''.join(filter(str.isdigit, resolution))
            format_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/mp4"
        else:
            format_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

        try:
            rc, stdout, stderr = await self._run_command_with_cancel_async(
                ["yt-dlp", "-f", format_str, "-o", video_file, url],
                timeout=1800,
                error_message="Video indirme işlemi timeout oldu (30 dakika)",
            )
        except RuntimeError:
            raise
        if rc != 0 or not os.path.exists(video_file):
            raise RuntimeError(f"Video indirilemedi: {url}\n{stderr}")

        self._update_status("Video içinden ses ayrıştırılıyor...", 20)
        try:
            arc, astout, astderr = await self._run_command_with_cancel_async(
                ["ffmpeg", "-y", "-i", video_file, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_file],
                timeout=900,
                error_message="Ses ayrıştırma işlemi timeout oldu (15 dakika)",
            )
        except RuntimeError:
            raise
        if arc != 0:
            stderr_tail = (astderr or "")[-300:]
            logger.error("Ses ayrıştırma hatası (stderr son 300 karakter): %s", stderr_tail)
            raise RuntimeError(f"Ses ayrıştırılamadı. ffmpeg stderr özeti: {stderr_tail}")

        return video_file, audio_file

    def download_full_video(self, url: str, project_paths: Optional[ProjectPaths] = None, resolution: str = "best") -> tuple[str, str]:
        """Geriye dönük uyumluluk için senkron sarmalayıcı."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.download_full_video_async(url, project_paths, resolution))
        loop.close()
        return result

    # ------------------------------------------------------------------
    # Timestamp kaydırma
    # ------------------------------------------------------------------

    def _shift_timestamps(
        self,
        original_json: str,
        start_time: float,
        end_time: float,
        output_json: str,
    ) -> str:
        """Kırpılan klibin altyazı zamanlamalarını 0. saniyeye hizalar."""
        with open(original_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        shifted = []
        duration = end_time - start_time
        for seg in data:
            if seg["end"] > start_time and seg["start"] < end_time:
                new_start = max(0, seg["start"] - start_time)
                new_end   = min(seg["end"] - start_time, duration)

                shifted_words = []
                for w in seg.get("words", []):
                    if "start" in w and "end" in w:
                        ws = w["start"] - start_time
                        we = min(w["end"] - start_time, duration)
                        if we > 0 and ws < duration:
                            shifted_words.append({
                                "word":  w["word"],
                                "start": max(0, ws),
                                "end":   we,
                                "score": w.get("score", 1.0),
                            })

                if shifted_words:
                    shifted.append({
                        "text":    seg["text"],
                        "start":   new_start,
                        "end":     new_end,
                        "speaker": seg.get("speaker", "Bilinmeyen"),
                        "words":   shifted_words,
                    })

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(shifted, f, ensure_ascii=False, indent=4)

        return output_json

    def _cut_and_burn_clip(
        self,
        master_video: str,
        start_t: float,
        end_t: float,
        temp_cropped: str,
        final_output: str,
        ass_file: str,
        subtitle_engine: Optional[SubtitleRenderer],
        layout: str = "single",
        center_x: Optional[float] = None,
        cut_as_short: bool = True,
    ) -> None:
        """Video keser, tracking yapar, sonra gerekiyorsa altyazıyı yakar."""
        if cut_as_short:
            try:
                self.video_processor.create_viral_short(
                    input_video=master_video,
                    start_time=start_t,
                    end_time=end_t,
                    output_filename=temp_cropped,
                    smoothness=0.1,
                    manual_center_x=center_x,
                    layout=layout,
                    cancel_event=self.cancel_event,
                )
            finally:
                self.video_processor.cleanup_gpu()
        else:
            self.video_processor.cut_segment_only(
                input_video=master_video,
                start_time=start_t,
                end_time=end_t,
                output_filename=temp_cropped,
                cancel_event=self.cancel_event,
            )

        if subtitle_engine is not None and os.path.exists(ass_file):
            raw_path = final_output.replace(".mp4", "_raw.mp4")
            shutil.copy2(temp_cropped, raw_path)
            subtitle_engine.burn_subtitles_to_video(
                temp_cropped,
                ass_file,
                final_output,
                cancel_event=self.cancel_event,
            )
        else:
            shutil.move(temp_cropped, final_output)

    # ------------------------------------------------------------------
    # Pipeline (tam otomatik)
    # ------------------------------------------------------------------

    async def run_pipeline_async(
        self,
        youtube_url: str,
        style_name: str = "HORMOZI",
        layout: str = "single",
        skip_subtitles: bool = False,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        resolution: str = "best",
    ) -> None:
        """Tek butondan tüm sistemi çalıştıran ana fonksiyon. Async versiyon."""
        self._validate_youtube_url(youtube_url)
        global_start = time.time()
        self._check_cancelled()

        # 1. Proje Hazırlığı (Video ID al ve klasör oluştur)
        self._update_status("Video ID alınıyor...", 5)
        try:
            rc, stdout, stderr = await self._run_command_with_cancel_async(
                ["yt-dlp", "--get-id", youtube_url],
                timeout=120,
                error_message="Video ID alma işlemi timeout oldu",
            )
            if rc != 0:
                raise RuntimeError(stderr or "Video ID alınamadı")
            video_id = stdout.strip()
            project_id = f"yt_{video_id}"
            self.project = ProjectPaths(project_id)
            logger.info(f"📁 Proje klasörü: {self.project.root}")
        except Exception as e:
            logger.error(f"Video ID alınamadı: {e}")
            self.project = ProjectPaths(f"fallback_{int(time.time())}")

        # 2. İndir (Eğer master yoksa)
        master_video = str(self.project.master_video)
        master_audio = str(self.project.master_audio)
        
        if not os.path.exists(master_video):
            self._check_cancelled()
            self._update_status("Orijinal video indiriliyor...", 10)
            try:
                master_video, master_audio = await self.download_full_video_async(youtube_url, self.project, resolution)
            except RuntimeError as e:
                logger.error(f"Pipeline durduruldu: {e}")
                self._update_status(f"HATA: {e}", -1)
                raise
        else:
            self._update_status("✅ Video kütüphanede bulundu, indirme atlanıyor.", 25)
            logger.info(f"♻️ Video zaten mevcut: {master_video}")

        # 3. WhisperX (Eğer transkript yoksa)
        metadata_file = str(self.project.transcript)
        if not os.path.exists(metadata_file):
            self._check_cancelled()
            self._update_status("WhisperX ses haritası çıkarıyor...", 30)
            try:
                metadata_file = await asyncio.to_thread(
                    run_transcription,
                    master_audio,
                    str(self.project.transcript),
                    lambda msg, pct: self._update_status(msg, pct),
                    self.cancel_event
                )
                await asyncio.to_thread(release_whisper_models)
            except Exception as e:
                logger.error(f"❌ WhisperX hatası: {e}")
                self._update_status(f"WhisperX hatası: {e}", -1)
                raise RuntimeError(f"WhisperX hatası: {e}") from e
        else:
            self._update_status("✅ Transkript kütüphanede bulundu, analiz atlanıyor.", 45)
            logger.info(f"♻️ Transkript zaten mevcut: {metadata_file}")

        # 4. LLM analizi
        self._update_status("LLM viral klipleri seçiyor...", 50)
        self._check_cancelled()
        viral_results = await asyncio.to_thread(
            self.analyzer.analyze_metadata,
            metadata_file,
            num_clips=num_clips,
            duration_min=duration_min,
            duration_max=duration_max,
            ui_callback=self.ui_callback,
            cancel_event=self.cancel_event,
        )
        if not viral_results or "segments" not in viral_results:
            logger.error("❌ LLM viral kısım bulamadı!")
            self._update_status("HATA: Viral klip secimi basarisiz.", -1)
            raise RuntimeError("Viral klip seçimi başarısız oldu.")
        
        # Analiz sonucunu proje klasörüne de kopyalayalım/kaydedelim
        with open(self.project.viral_meta, "w", encoding="utf-8") as f:
            json.dump(viral_results, f, ensure_ascii=False, indent=4)

        # 5. Klip üretimi döngüsü
        segments = viral_results["segments"][:num_clips]
        if not segments:
            logger.error("❌ Hiç viral segment üretilmedi.")
            self._update_status("HATA: Üretilecek viral segment bulunamadı.", -1)
            raise RuntimeError("Üretilecek viral segment bulunamadı.")

        total = len(segments)
        self._update_status(f"{total} adet viral short üretimine başlandı!", 60)

        subtitle_engine: Optional[SubtitleRenderer] = None
        if not skip_subtitles:
            chosen_style = StyleManager.get_preset(style_name)
            subtitle_engine = SubtitleRenderer(style=chosen_style)

        for idx, seg in enumerate(segments):
            self._check_cancelled()
            clip_num = idx + 1
            start_t  = seg["start_time"]
            end_t    = seg["end_time"]
            hook     = seg.get("hook_text", "")
            
            hook_slug = re.sub(r'[^\w\s-]', '', hook).strip().lower().replace(' ', '_')[:30]
            clip_name = f"short_{clip_num}_{hook_slug}"
            
            logger.info(f"🎬 Klip {clip_num}/{total} kurgulanıyor: {clip_name}")
            
            render_pct = 60 + int((idx / total) * 35)
            self._update_status(f"Klip {clip_num}/{total} hazırlanıyor: {seg.get('ui_title', 'Viral Klip')}...", render_pct)

            shifted_json     = str(TEMP_DIR / f"shifted_{clip_num}.json")
            ass_file         = str(TEMP_DIR / f"subs_{clip_num}.ass")
            temp_cropped     = str(TEMP_DIR / f"cropped_{clip_num}.mp4")
            final_output     = str(self.project.outputs / f"{clip_name}.mp4")

            transcript_data: list[dict] = []
            if not skip_subtitles and subtitle_engine is not None:
                self._update_status(f"Klip {clip_num}/{total} - Altyazılar oluşturuluyor...", render_pct + 1)
                self._shift_timestamps(metadata_file, start_t, end_t, shifted_json)
                subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

                with open(shifted_json, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)
            
            clip_full_metadata = self._build_clip_metadata(
                transcript_data,
                viral_metadata={
                    "hook_text": seg.get("hook_text", ""),
                    "ui_title": seg.get("ui_title", ""),
                    "social_caption": seg.get("social_caption", ""),
                    "viral_score": seg.get("viral_score", 0),
                },
                render_metadata={
                    "mode": "pipeline_auto",
                    "project_id": self.project.root.name if self.project else None,
                    "clip_name": f"{clip_name}.mp4",
                    "start_time": start_t,
                    "end_time": end_t,
                    "crop_mode": "auto",
                    "center_x": None,
                    "layout": layout,
                    "style_name": style_name,
                    "skip_subtitles": skip_subtitles,
                },
            )
            with open(final_output.replace(".mp4", ".json"), "w", encoding="utf-8") as f:
                json.dump(clip_full_metadata, f, ensure_ascii=False, indent=4)

            self._update_status(f"Klip {clip_num}/{total} - Video kesiliyor (YOLO + NVENC)...", render_pct + 2)
            if not skip_subtitles and subtitle_engine is not None:
                self._update_status(f"Klip {clip_num}/{total} - Altyazılar videoya gömülüyor...", render_pct + 3)
            cleanup_files = [shifted_json, ass_file]
            if temp_cropped != final_output:
                cleanup_files.append(temp_cropped)
            try:
                await asyncio.to_thread(
                    self._cut_and_burn_clip,
                    master_video, start_t, end_t, temp_cropped, final_output, ass_file,
                    subtitle_engine, layout=layout, center_x=None, cut_as_short=True,
                )
            finally:
                for f in cleanup_files:
                    try:
                        os.remove(f)
                    except FileNotFoundError:
                        pass

        elapsed = round(time.time() - global_start, 2)
        self._update_status("TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!", 100)
        logger.success(f"🎉 {elapsed}s içinde {total} video üretildi!")

    def run_pipeline(
        self,
        youtube_url: str,
        style_name: str = "HORMOZI",
        layout: str = "single",
        skip_subtitles: bool = False,
        num_clips: int = 8,
        duration_min: float = 120.0,
        duration_max: float = 180.0,
        resolution: str = "best",
    ) -> None:
        """Tek butondan tüm sistemi çalıştıran ana fonksiyon senkron sarmalayıcı."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            self.run_pipeline_async(
                youtube_url, style_name, layout, skip_subtitles,
                num_clips, duration_min, duration_max, resolution
            )
        )
        loop.close()

    # ------------------------------------------------------------------
    # Manuel klip
    # ------------------------------------------------------------------

    async def run_manual_clip_async(
        self,
        start_t: float,
        end_t: float,
        transcript_data: Optional[list],
        style_name: str = "HORMOZI",
        project_id: Optional[str] = None,
        center_x: Optional[float] = None,
        layout: str = "single",
        output_name: Optional[str] = None,
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> str:
        """Kullanıcının elle seçtiği aralık için tek klip üretir."""
        if project_id:
            self.project = ProjectPaths(project_id)
            master_video = str(self.project.master_video)
        else:
            # Fallback (Eski yapıda proje yoksa)
            master_video = str(MASTER_VIDEO)
            # Ama yine de yeni bir çıktı yolu lazım
            self.project = ProjectPaths(f"manual_{int(time.time())}")

        if not os.path.exists(master_video):
            raise FileNotFoundError(f"Orijinal video bulunamadı: {master_video}")

        self._update_status(f"Manuel klip: {start_t} - {end_t} sn", 10)
        normalized_transcript = (
            self._normalize_transcript_payload(transcript_data)
            if transcript_data
            else self._load_project_transcript()
        )

        job_id = f"manual_{int(time.time())}"
        temp_json    = str(TEMP_DIR / f"manual_{job_id}.json")
        shifted_json = str(TEMP_DIR / f"shifted_{job_id}.json")
        ass_file     = str(TEMP_DIR / f"subs_{job_id}.ass")
        temp_cropped = str(TEMP_DIR / f"cropped_{job_id}.mp4")
        
        # Proje içi shorts klasörüne
        clip_filename = output_name or f"manual_{job_id}.mp4"
        if not clip_filename.endswith(".mp4"):
            clip_filename = f"{clip_filename}.mp4"
        final_output = str(self.project.outputs / clip_filename)

        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(normalized_transcript, f, ensure_ascii=False, indent=4)

        self._shift_timestamps(temp_json, start_t, end_t, shifted_json)

        subtitle_engine = None
        if not skip_subtitles:
            chosen_style = StyleManager.get_preset(style_name)
            subtitle_engine = SubtitleRenderer(style=chosen_style)
            subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)

        cleanup_files = [temp_json, shifted_json, temp_cropped]
        if not skip_subtitles:
            cleanup_files.append(ass_file)
        try:
            await asyncio.to_thread(
                self._cut_and_burn_clip,
                master_video, start_t, end_t, temp_cropped, final_output, ass_file,
                subtitle_engine, layout, center_x, cut_as_short
            )
            meta_path = final_output.replace(".mp4", ".json")
            with open(shifted_json, "r", encoding="utf-8") as f:
                shifted_transcript = json.load(f)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    self._build_clip_metadata(
                        shifted_transcript,
                        viral_metadata=None,
                        render_metadata={
                            "mode": "manual_auto" if center_x is None else "manual_custom_crop",
                            "project_id": self.project.root.name if self.project else None,
                            "clip_name": clip_filename,
                            "start_time": start_t,
                            "end_time": end_t,
                            "crop_mode": "auto" if center_x is None else "manual",
                            "center_x": center_x,
                            "layout": layout,
                            "style_name": style_name,
                            "cut_as_short": cut_as_short,
                        },
                    ),
                    f,
                    ensure_ascii=False,
                    indent=4,
                )
        finally:
            for f in cleanup_files:
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass

        self._update_status(f"Manuel klip hazır: {final_output}", 100)
        return final_output

    def run_manual_clip(self, *args, **kwargs) -> str:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(self.run_manual_clip_async(*args, **kwargs))
        loop.close()
        return res

    async def run_manual_clips_from_cut_points_async(
        self,
        cut_points: list[float],
        transcript_data: list,
        style_name: str = "HORMOZI",
        project_id: Optional[str] = None,
        layout: str = "single",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        """Kesim noktalarına göre birden fazla klip üretir. cut_points=[t0,t1,...,tn] -> n aralık."""
        if len(cut_points) < 2:
            return []
        results = []
        total = len(cut_points) - 1
        for i in range(total):
            self._check_cancelled()
            start_t = cut_points[i]
            end_t = cut_points[i + 1]
            if end_t <= start_t:
                continue
            clip_num = i + 1
            pct = 10 + int((i / total) * 85)
            self._update_status(f"Klip {clip_num}/{total}: {start_t:.1f}-{end_t:.1f} sn...", pct)
            output_name = f"cut_{clip_num}_{int(start_t)}_{int(end_t)}.mp4"
            path = await self.run_manual_clip_async(
                start_t, end_t, transcript_data,
                style_name, project_id, None, layout, output_name, skip_subtitles, cut_as_short,
            )
            results.append(path)
        self._update_status("Tüm kesim noktaları işlendi!", 100)
        return results

    def run_manual_clips_from_cut_points(self, *args, **kwargs) -> list[str]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(self.run_manual_clips_from_cut_points_async(*args, **kwargs))
        loop.close()
        return res

    # ------------------------------------------------------------------
    # AI Toplu Klip (Batch)
    # ------------------------------------------------------------------

    async def run_batch_manual_clips_async(
        self,
        start_t: float,
        end_t: float,
        num_clips: int,
        transcript_data: list,
        style_name: str = "HORMOZI",
        project_id: Optional[str] = None,
        layout: str = "single",
        skip_subtitles: bool = False,
        cut_as_short: bool = True,
    ) -> list[str]:
        """Seçilen aralıkta AI kullanarak N adet viral klip üretir."""
        if project_id:
            self.project = ProjectPaths(project_id)
            master_video = str(self.project.master_video)
        else:
            master_video = str(MASTER_VIDEO)
            self.project = ProjectPaths(f"batch_{int(time.time())}")

        if not os.path.exists(master_video):
            raise FileNotFoundError(f"Orijinal video bulunamadı: {master_video}")

        self._update_status(f"AI Toplu Analiz başlıyor ({num_clips} klip)...", 10)
        
        # 1. Bu aralıktaki transkripti çek
        sub_transcript = [s for s in transcript_data if s["start"] >= start_t and s["end"] <= end_t]
        
        # 2. Viral Analiz (Segment bazlı)
        viral_results = await asyncio.to_thread(
            self.analyzer.analyze_transcript_segment,
            transcript_data=sub_transcript,
            limit=num_clips,
            window_start=start_t,
            window_end=end_t,
            cancel_event=self.cancel_event,
        )
        
        if not viral_results or "segments" not in viral_results:
            logger.error("❌ AI bu aralıkta viral segment bulamadı!")
            self._update_status("HATA: AI viral segment bulamadı.", -1)
            return []
            
        segments = viral_results["segments"]
        total = len(segments)
        self._update_status(f"AI {total} adet viral an buldu, kurgu başlıyor...", 30)
        
        results = []
        subtitle_engine = None
        if not skip_subtitles:
            chosen_style = StyleManager.get_preset(style_name)
            subtitle_engine = SubtitleRenderer(style=chosen_style)

        for idx, seg in enumerate(segments):
            self._check_cancelled()
            clip_num = idx + 1
            s_t = seg["start_time"]
            e_t = seg["end_time"]
            hook = seg.get("hook_text", "")
            
            hook_slug = re.sub(r'[^\w\s-]', '', hook).strip().lower().replace(' ', '_')[:25]
            clip_name = f"batch_{clip_num}_{hook_slug}"
            
            # İlerlemeyi 30-95 arası dağıt
            render_pct = 30 + int((idx / total) * 65)
            self._update_status(f"Klip {clip_num}/{total} hazırlanıyor: {seg.get('ui_title', 'Viral Klip')}...", render_pct)
            
            shifted_json = str(TEMP_DIR / f"batch_s_{clip_num}.json")
            ass_file     = str(TEMP_DIR / f"batch_a_{clip_num}.ass")
            temp_cropped = str(TEMP_DIR / f"batch_c_{clip_num}.mp4")
            final_output = str(self.project.outputs / f"{clip_name}.mp4")
            
            # Altyazı kaydırma (Dosya yoluna ihtiyacı var, geçici bir tane yapalım)
            temp_orig = str(TEMP_DIR / f"orig_{clip_num}.json")
            with open(temp_orig, "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, ensure_ascii=False)
            
            self._shift_timestamps(temp_orig, s_t, e_t, shifted_json)
            if subtitle_engine is not None:
                subtitle_engine.generate_ass_file(shifted_json, ass_file, max_words_per_screen=3)
            
            # Metadata kaydet
            with open(shifted_json, "r", encoding="utf-8") as f:
                t_data = json.load(f)
            
            clip_meta = self._build_clip_metadata(
                t_data,
                viral_metadata={
                    "hook_text": seg.get("hook_text", ""),
                    "ui_title": seg.get("ui_title", ""),
                    "social_caption": seg.get("social_caption", ""),
                    "viral_score": seg.get("viral_score", 0),
                },
                render_metadata={
                    "mode": "batch_auto",
                    "project_id": self.project.root.name if self.project else None,
                    "clip_name": f"{clip_name}.mp4",
                    "start_time": s_t,
                    "end_time": e_t,
                    "crop_mode": "auto",
                    "center_x": None,
                    "layout": layout,
                    "style_name": style_name,
                    "skip_subtitles": skip_subtitles,
                },
            )
            with open(final_output.replace(".mp4", ".json"), "w", encoding="utf-8") as f:
                json.dump(clip_meta, f, ensure_ascii=False, indent=4)
                
            self._update_status(f"Klip {clip_num}/{total} - Video kesiliyor...", render_pct + 1)
            if subtitle_engine is not None:
                self._update_status(f"Klip {clip_num}/{total} - Altyazılar basılıyor...", render_pct + 2)
            cleanup_files = [temp_orig, shifted_json]
            if subtitle_engine is not None:
                cleanup_files.extend([ass_file, temp_cropped])
            try:
                await asyncio.to_thread(
                    self._cut_and_burn_clip,
                    master_video, s_t, e_t, temp_cropped, final_output, ass_file,
                    subtitle_engine, layout, None, cut_as_short
                )
                results.append(final_output)
            finally:
                for f in cleanup_files:
                    try:
                        os.remove(f)
                    except FileNotFoundError:
                        pass
                    except OSError as e:
                        logger.warning(f"Dosya silinemedi: {f} - {e}")
                
        self._update_status("TÜM TOPLU ÜRETİM TAMAMLANDI!", 100)
        logger.success(f"🎉 Toplu üretim bitti: {len(results)} klip.")
        return results

    def run_batch_manual_clips(self, *args, **kwargs) -> list[str]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(self.run_batch_manual_clips_async(*args, **kwargs))
        loop.close()
        return res

    # ------------------------------------------------------------------
    # Altyazı yeniden yazma
    # ------------------------------------------------------------------

    async def reburn_subtitles_async(self, clip_name: str, transcript: list, project_id: Optional[str] = None, style_name: str = "HORMOZI") -> str:
        """Mevcut bir klibin altyazılarını yeniden işler. _raw.mp4 varsa onu kullanır (çift altyazı önlenir). Async versiyon."""
        if project_id:
            project = ProjectPaths(project_id)
            input_video = str(project.outputs / clip_name)
        else:
            input_video = str(OUTPUTS_DIR / clip_name)

        if not os.path.exists(input_video):
            raise FileNotFoundError(f"Video bulunamadı: {input_video}")

        raw_video = input_video.replace(".mp4", "_raw.mp4")
        source_video = raw_video if os.path.exists(raw_video) else input_video
        if source_video == raw_video:
            logger.info(f"♻️ Ham video kullanılıyor (çift altyazı önlenir): {raw_video}")

        temp_output = input_video.replace(".mp4", "_temp_reburn.mp4")
        ass_file    = str(TEMP_DIR / f"{clip_name.replace('.mp4', '')}.ass")

        self._update_status("Altyazı haritası güncelleniyor...", 30)
        subtitle_engine = SubtitleRenderer(style=StyleManager.get_preset(style_name))
        normalized_transcript = self._normalize_transcript_payload(transcript)

        temp_json = str(TEMP_DIR / f"reburn_{int(time.time())}.json")
        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(normalized_transcript, f, ensure_ascii=False, indent=4)

        # Runs sync primarily string ops
        subtitle_engine.generate_ass_file(temp_json, ass_file, max_words_per_screen=3)

        self._update_status("Videonun makyajı tazeleniyor...", 60)
        # Calling the potentially blocking ffmpeg shell script wrapper in another thread via to_thread.
        await asyncio.to_thread(
            subtitle_engine.burn_subtitles_to_video,
            source_video, ass_file, temp_output, cancel_event=self.cancel_event
        )

        os.replace(temp_output, input_video)

        meta_path = input_video.replace(".mp4", ".json")
        existing_metadata: dict | None = None
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing_metadata = loaded

        with open(meta_path, "w", encoding="utf-8") as f:
            merged_metadata = self._build_clip_metadata(
                normalized_transcript,
                viral_metadata=(existing_metadata or {}).get("viral_metadata"),
                render_metadata=(existing_metadata or {}).get("render_metadata"),
            )
            if isinstance(merged_metadata.get("render_metadata"), dict):
                merged_metadata["render_metadata"]["style_name"] = style_name
            json.dump(merged_metadata, f, ensure_ascii=False, indent=4)

        for f in (temp_json, ass_file):
            try:
                os.remove(f)
            except FileNotFoundError:
                pass

        self._update_status("Klip başarıyla güncellendi!", 100)
        return input_video

    def reburn_subtitles(self, *args, **kwargs) -> str:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(self.reburn_subtitles_async(*args, **kwargs))
        loop.close()
        return res

    # ------------------------------------------------------------------
    # Yerel video transkripsiyon
    # ------------------------------------------------------------------

    def transcribe_local_video(self, video_path: str) -> list | None:
        """Yüklenen yerel videoyu transkribe eder ve metadata üretir."""
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

        self._update_status("Ses haritası çıkarılıyor (WhisperX)...", 20)

        try:
            run_transcription(
                audio_file=video_path,
                output_json=str(VIDEO_METADATA),
                status_callback=lambda msg, pct: self._update_status(f"Transkripsiyon: {msg}", 20 + int(pct * 0.4)),
                cancel_event=self.cancel_event,
            )
        except Exception as e:
            self._update_status(f"HATA: {e}", -1)
            return None

        with open(str(VIDEO_METADATA), "r", encoding="utf-8") as f:
            transcript = json.load(f)

        self._update_status("Video ve ses haritası hazır!", 100)
        logger.success("✅ Yerel video başarıyla işlendi.")
        return transcript
