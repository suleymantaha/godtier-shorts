# Video Processor

YOLO tabanlı insan tespiti ve SteadyCam modu ile 9:16 dikey video kırpma.

## Dosya

`backend/services/video_processor.py`

## Sınıf

`VideoProcessor(model_version=None, device="cuda")`

- **Lazy load**: YOLO modeli ilk `create_viral_short()` çağrısında yüklenir (faster-whisper ile VRAM çakışması önlenir)
- **unload_model()**: VRAM boşaltma (transkripsiyon öncesi)

## Ana Metodlar

| Metod | Açıklama |
|-------|----------|
| `create_viral_short(...)` | YOLO + SteadyCam ile 1080x1920 dikey klip |
| `cut_segment_only(...)` | Sadece zaman aralığı kesimi (crop yok) |

## create_viral_short Parametreleri

| Parametre | Açıklama |
|-----------|----------|
| input_video | Kaynak video yolu |
| start_time, end_time | Kesim aralığı (sn) |
| output_filename | Çıktı dosyası |
| smoothness | Kamera geçiş yumuşaklığı (lerp, deadzone) |
| manual_center_x | Manuel kadraj merkezi (0-1, None=YOLO otomatik) |
| layout | "single" / "split" (2 kişi varsa ekran bölme) |

## SteadyCam Modu

- YOLO ile her frame'de insan bbox tespiti
- Deadzone: Hareket eşiği altında kamera sabit
- Lerp: Yumuşak geçiş (smoothness)
- 9:16 crop: 1080x1920 dikey çıktı

## FFmpeg

- **Kesim**: h264_nvenc (CUDA), preset p6, 8Mbps
- **Ses**: AAC 192k
- **Çıktı**: MP4

## YOLO Modeli

- Varsayılan: `backend/config.YOLO_MODEL_PATH` (YOLO11)
- Ultralytics YOLO kullanılır
