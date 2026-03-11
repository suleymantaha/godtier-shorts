"""
backend/services/video_processor.py
=====================================
YOLO + ffmpeg NVENC tabanlı video kırpma ve dikey dönüştürme servisi.
(eski: src/video_processor.py)
"""
import os
import io
import gc
import uuid
import subprocess
import threading
import time

import cv2
import torch
import numpy as np
from loguru import logger
from ultralytics import YOLO

from backend.config import LOGS_DIR, YOLO_MODEL_PATH, TEMP_DIR


def _is_nvenc_error(stderr: str) -> bool:
    """FFmpeg stderr içinde NVENC/CUDA kaynaklı hata desenlerini yakalar."""
    patterns = (
        "nvenc",
        "cuda",
        "cannot load libnvidia-encode",
        "no nvenc capable devices found",
        "error initializing output stream",
    )
    lowered = stderr.lower()
    return any(pattern in lowered for pattern in patterns)


logger.add(
    str(LOGS_DIR / "video_processor_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
)


class VideoProcessor:
    @staticmethod
    def _run_command_with_cancel(
        cmd: list[str],
        *,
        timeout: float,
        cancel_event: threading.Event | None = None,
        text: bool = True,
    ) -> subprocess.CompletedProcess:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
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
                raise RuntimeError("FFmpeg işlemi timeout oldu")
            time.sleep(0.5)

    def __init__(self, model_version: str | None = None, device: str = "cuda"):
        """
        model_version: YOLO model dosyası (varsayılan: config.YOLO_MODEL_PATH)
        device:        'cuda' veya 'cpu'
        
        YOLO modeli lazy-load edilir — ilk `create_viral_short()` çağrısında
        GPU'ya yüklenir. Bu sayede WhisperX transkripsiyon sırasında VRAM
        kullanılmaz (eş zamanlı CUDA OOM riski ortadan kalkar).
        """
        self._model_path = model_version or str(YOLO_MODEL_PATH)
        self._device     = device
        self.model: YOLO | None = None  # Henüz yüklenmedi
        logger.info(f"🎥 Video Processor hazırlandı (YOLO lazy-load, cihaz: {device.upper()}).")

    def _ensure_model_loaded(self) -> None:
        """YOLO modelini ilk kullanımda GPU'ya yükler."""
        if self.model is not None:
            return  # Zaten yüklü

        logger.info(f"🔄 YOLO modeli yükleniyor: {self._model_path}")
        try:
            self.model = YOLO(self._model_path)

            if self._device == "cuda" and not torch.cuda.is_available():
                logger.warning("⚠️ CUDA istendi ama GPU yok. CPU'ya geçiliyor.")
                self._device = "cpu"

            self.model.to(self._device)
            logger.success(f"✅ YOLO modeli {self._device.upper()} üzerine yüklendi.")
        except Exception as e:
            logger.error(f"❌ YOLO yüklenemedi: {e}")
            raise

    def unload_model(self) -> None:
        """YOLO modelini VRAM'den boşalt (WhisperX ile birlikte çalışmak için)."""
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if self._device == "cuda":
                torch.cuda.empty_cache()
            logger.info("♻️ YOLO modeli VRAM'den boşaltıldı.")

    def cleanup_gpu(self) -> None:
        """YOLO modelini ve GPU belleğini temizler."""
        self.unload_model()
        gc.collect()
        if self._device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("🧹 VideoProcessor GPU cleanup tamamlandı.")

    # ------------------------------------------------------------------
    # Yardımcı
    # ------------------------------------------------------------------

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        """Linear interpolation — sinematik yumuşak kamera kayması."""
        return a + (b - a) * t

    @staticmethod
    def _compute_crop_bounds(center_x: float, crop_width: int, frame_width: int) -> tuple[int, int]:
        """Crop sınırlarını frame genişliğine güvenli şekilde sıkıştırır."""
        x1 = int(center_x - crop_width / 2)
        max_x1 = max(0, frame_width - crop_width)
        x1 = min(max(0, x1), max_x1)
        x2 = x1 + crop_width
        return x1, x2

    # ------------------------------------------------------------------
    # Ana metod
    # ------------------------------------------------------------------

    @logger.catch
    def create_viral_short(
        self,
        input_video: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        smoothness: float = 0.1,
        manual_center_x: float | None = None,
        layout: str = "single",  # "single" veya "split"
        cancel_event: threading.Event | None = None,
    ) -> None:
        """
        Geniş videoyu keser, insanı takip eder, 1080x1920 dikey video üretir.
        layout="split": Eğer 2 kişi varsa ekranı ikiye böler.
        """
        logger.info(f"✂️ Klip: {start_time} - {end_time} sn (Layout: {layout}) → {output_filename}")

        if manual_center_x is None:
            self._ensure_model_loaded()

        job_uuid = uuid.uuid4().hex[:8]
        temp_cut        = str(TEMP_DIR / f"cut_{job_uuid}.mp4")
        temp_video_only = str(TEMP_DIR / f"vonly_{job_uuid}.mp4")

        # --- Adım 1: Segment hassas kesimi (Senkron ve frame doğruluğu için re-encode) ---
        duration = end_time - start_time
        try:
            result = self._run_command_with_cancel(
                ["ffmpeg", "-y", "-i", input_video,
                 "-ss", str(start_time), "-t", str(duration),
                 "-c:v", "h264_nvenc", "-preset", "p6", "-b:v", "8M",
                 "-c:a", "aac", "-b:a", "192k", temp_cut],
                timeout=300,
                cancel_event=cancel_event,
            )
            if result.returncode != 0:
                stderr = result.stderr or ""
                logger.error(f"FFmpeg kesim hatası: {stderr[-500:]}")
                raise RuntimeError(f"Video kesilemedi: {stderr[-300:]}")
        except RuntimeError as e:
            if "timeout" in str(e).lower():
                raise RuntimeError("Video kesme işlemi timeout oldu (5 dakika)") from e
            raise

        # --- Adım 2: OpenCV + YOLO ---
        cap    = cv2.VideoCapture(temp_cut)
        orig_fps = cap.get(cv2.CAP_PROP_FPS)
        orig_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Shorts standard: 1080x1920
        target_w, target_h = 1080, 1920

        ffmpeg_proc: subprocess.Popen[bytes] | None = None
        frame_count = 0
        try:
            ffmpeg_proc = subprocess.Popen(
                ["ffmpeg", "-y",
                 "-loglevel", "error",
                 "-f", "rawvideo", "-vcodec", "rawvideo",
                 "-s", f"{target_w}x{target_h}",
                 "-pix_fmt", "bgr24", "-r", str(orig_fps),
                 "-i", "-",
                 "-c:v", "h264_nvenc", "-preset", "p6", "-b:v", "8M",
                 "-pix_fmt", "yuv420p", temp_video_only],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if ffmpeg_proc.stdin is None:
                raise RuntimeError("FFmpeg stdin açılamadı!")
            stdin: io.RawIOBase = ffmpeg_proc.stdin  # type: ignore[assignment]

            # Takip değişkenleri
            current_cx1 = orig_w / 2
            current_cx2 = orig_w / 2
            deadzone_px = 30

            # Hesaplanan dikey crop boyutu (Kaynak üzerindeki pencere)
            # tek parça (1080x1920) için 9/16, split (1080x960 yarı ekran) için 1080/960 = 9/8
            if layout == "split":
                src_crop_w = int(orig_h * (1080 / 960))
            else:
                src_crop_w = int(orig_h * (9 / 16))
            src_crop_h = orig_h

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    ffmpeg_proc.kill()
                    cap.release()
                    raise RuntimeError("Job cancelled by user")
                ret, frame = cap.read()
                if not ret: break
                frame_count += 1
                target_cx1, target_cx2 = current_cx1, current_cx2

                if manual_center_x is not None:
                    current_cx1 = manual_center_x * orig_w
                elif self.model is not None:
                    results = self.model.predict(frame, classes=[0], verbose=False, conf=0.55)
                    det_boxes = results[0].boxes
                    if det_boxes is not None and len(det_boxes) > 0:
                        boxes = det_boxes.xyxy.cpu().numpy()  # type: ignore[reportAttributeAccessIssue]
                        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
                        indices = np.argsort(areas)[::-1] # Büyükten küçüğe
                        
                        if layout == "split":
                            if len(indices) >= 2:
                                # 2 kişi bulundu, ekran atlamaması için her zaman soldaki Üst, sağdaki Alt ekranda kalsın
                                b1 = boxes[indices[0]]
                                b2 = boxes[indices[1]]
                                c1 = (b1[0] + b1[2]) / 2
                                c2 = (b2[0] + b2[2]) / 2
                                
                                if c1 > c2:
                                    c1, c2 = c2, c1
                                
                                target_cx1, target_cx2 = c1, c2
                            else:
                                # Sadece bir kişi bulunduysa, hangisine odaklıysa (daha yakın olan) onu güncelle
                                b1 = boxes[indices[0]]
                                cx = (b1[0] + b1[2]) / 2
                                if abs(cx - current_cx1) < abs(cx - current_cx2):
                                    target_cx1 = cx
                                else:
                                    target_cx2 = cx
                        else:
                            best1 = boxes[indices[0]]
                            target_cx1 = (best1[0] + best1[2]) / 2
                            target_cx2 = target_cx1

                    # Yumuşatma
                    if abs(target_cx1 - current_cx1) > deadzone_px:
                        current_cx1 = self.lerp(current_cx1, target_cx1, smoothness)
                    if abs(target_cx2 - current_cx2) > deadzone_px:
                        current_cx2 = self.lerp(current_cx2, target_cx2, smoothness)

                # --- Layout Oluşturma ---
                if layout == "split" and manual_center_x is None:
                    # İki parça: Üst ve Alt
                    # Üst (1080x960)
                    def get_crop(cx, cw):
                        x1, x2 = self._compute_crop_bounds(cx, cw, orig_w)
                        return frame[0:orig_h, x1:x2]

                    crop1 = get_crop(current_cx1, src_crop_w)
                    crop2 = get_crop(current_cx2, src_crop_w)
                    
                    # Resize to halves (1080x960 each)
                    res1 = cv2.resize(crop1, (1080, 960))
                    res2 = cv2.resize(crop2, (1080, 960))
                    final_frame = np.vstack((res1, res2))
                else:
                    # Tek parça (1080x1920)
                    x1, x2 = self._compute_crop_bounds(current_cx1, src_crop_w, orig_w)

                    crop = frame[0:orig_h, x1:x2]
                    final_frame = cv2.resize(crop, (1080, 1920))

                try:
                    stdin.write(final_frame.tobytes())
                except (BrokenPipeError, OSError) as exc:
                    stderr_tail = ""
                    if ffmpeg_proc.stderr is not None:
                        stderr_tail = ffmpeg_proc.stderr.read().decode("utf-8", errors="replace")[-500:]
                    raise RuntimeError(f"FFmpeg encode pipe kırıldı: {stderr_tail or str(exc)}") from exc

            cap.release()
            stdin.close()
            ffmpeg_proc.stdin = None
            _, ffmpeg_stderr = ffmpeg_proc.communicate()

            if ffmpeg_proc.returncode != 0:
                stderr_tail = (ffmpeg_stderr or b"").decode("utf-8", errors="replace")[-500:]
                raise RuntimeError(f"FFmpeg encode hatası: {stderr_tail}")

            if self._device == "cuda":
                gc.collect()
                torch.cuda.empty_cache()

            # --- Adım 3: Ses birleştir ---
            logger.info("🎵 Ses birleştiriliyor...")
            cmd_merge = [
                "ffmpeg", "-y",
                "-i", temp_video_only, "-i", temp_cut,
                "-c:v", "copy", "-c:a", "aac",
                "-map", "0:v:0", "-map", "1:a:0",
                output_filename,
            ]
            merge_result = self._run_command_with_cancel(
                cmd_merge,
                timeout=300,
                cancel_event=cancel_event,
            )
            if merge_result.returncode != 0:
                merge_stderr = merge_result.stderr or ""
                logger.error(f"FFmpeg ses birleştirme hatası: {merge_stderr[-500:]}")
                if _is_nvenc_error(merge_stderr):
                    logger.warning("⚠️ NVENC kaynaklı hata algılandı, CPU fallback ile tekrar deneniyor...")
                    cmd_cpu_fallback = [
                        "ffmpeg", "-y",
                        "-i", temp_video_only, "-i", temp_cut,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                        "-c:a", "aac",
                        "-map", "0:v:0", "-map", "1:a:0",
                        output_filename,
                    ]
                    fallback_result = self._run_command_with_cancel(
                        cmd_cpu_fallback,
                        timeout=300,
                        cancel_event=cancel_event,
                    )
                    if fallback_result.returncode != 0:
                        fallback_stderr = fallback_result.stderr or ""
                        logger.error(f"FFmpeg CPU fallback hatası: {fallback_stderr[-500:]}")
                        raise RuntimeError(f"Ses birleştirilemedi: {fallback_stderr[-300:]}")
                else:
                    raise RuntimeError(f"Ses birleştirilemedi: {merge_stderr[-300:]}")

            if not os.path.exists(output_filename):
                raise RuntimeError(f"Çıktı dosyası oluşturulamadı: {output_filename}")
            if os.path.getsize(output_filename) <= 0:
                raise RuntimeError(f"Çıktı dosyası boş: {output_filename}")
        finally:
            cap.release()
            if ffmpeg_proc is not None:
                if ffmpeg_proc.stdin is not None and not ffmpeg_proc.stdin.closed:
                    ffmpeg_proc.stdin.close()
                if ffmpeg_proc.poll() is None:
                    ffmpeg_proc.kill()
                    ffmpeg_proc.wait()

            for f in (temp_cut, temp_video_only):
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass  # Dosya zaten yoksa sorun yok
                except OSError as e:
                    logger.warning(f"Dosya silinemedi: {f} - {e}")

        logger.success(f"🎉 Çıktı hazır: {output_filename} ({frame_count} kare)")

    def cut_segment_only(
        self,
        input_video: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Sadece zaman aralığını keser. Crop/resize yok. Orijinal boyut korunur."""
        duration = end_time - start_time
        logger.info(f"✂️ Zaman kesimi: {start_time} - {end_time} sn (orijinal boyut) → {output_filename}")

        cmd_nvenc = [
            "ffmpeg", "-y", "-i", input_video,
            "-ss", str(start_time), "-t", str(duration),
            "-c:v", "h264_nvenc", "-preset", "p6", "-b:v", "8M",
            "-c:a", "aac", "-b:a", "192k", output_filename,
        ]
        cmd_cpu = [
            "ffmpeg", "-y", "-i", input_video,
            "-ss", str(start_time), "-t", str(duration),
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k", output_filename,
        ]
        try:
            result = self._run_command_with_cancel(cmd_nvenc, timeout=300, cancel_event=cancel_event)
            if result.returncode != 0:
                stderr = result.stderr or ""
                if "nvenc" in stderr.lower() or "cuda" in stderr.lower():
                    logger.warning("⚠️ NVENC kullanılamadı, CPU fallback...")
                    cpu_result = self._run_command_with_cancel(cmd_cpu, timeout=300, cancel_event=cancel_event)
                    if cpu_result.returncode != 0:
                        raise RuntimeError("CPU fallback ile video kesilemedi")
                else:
                    raise RuntimeError(f"Video kesilemedi: {stderr[-300:]}")
        except RuntimeError as e:
            if "timeout" in str(e).lower():
                raise RuntimeError("Video kesme işlemi timeout oldu (5 dakika)") from e
            raise
        logger.success(f"🎉 Zaman kesimi hazır: {output_filename}")
