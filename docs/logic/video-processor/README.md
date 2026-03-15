# Video Processor

YOLO11 tabanlı `person` takibi, deterministik hedef seçimi ve 9:16 dikey crop üretimi.

## Dosya

`backend/services/video_processor.py`

## Sınıf

`VideoProcessor(model_version=None, device="cuda")`

- **Lazy load**: YOLO modeli ilk render çağrısında yüklenir
- **unload_model()**: transkripsiyon öncesi VRAM boşaltma
- **Tracking modu**: `track(..., persist=True, tracker="bytetrack.yaml", classes=[0])`

## Ana Metodlar

| Metod | Açıklama |
|------|----------|
| `create_viral_short(...)` | Tracking, crop, A/V merge ve kalite raporu ile dikey klip üretir |
| `cut_segment_only(...)` | Sadece zaman aralığı kesimi yapar |

## create_viral_short Parametreleri

| Parametre | Açıklama |
|-----------|----------|
| `input_video` | Kaynak video |
| `start_time`, `end_time` | Kesim aralığı |
| `output_filename` | Çıktı dosyası |
| `manual_center_x` | Manuel merkez; verildiğinde tracking by-pass edilir |
| `layout` | `single` / `split` |
| `cut_as_short` | `True` ise dikey crop, `False` ise düz segment cut |

## Tracking ve Crop Kuralları

- Aday bbox'lar `min_detection_confidence` ve `min_track_accept_score` eşiklerinden geçmelidir.
- Hedef seçim skoru continuity, bbox alanı, confidence, center penalty ve aspect ratio penalty bileşenlerinden oluşur.
- Kısa kayıplarda `grace`, sonrasında `controlled return` uygulanır.
- Aynı ID ve yeni ID ile reacquire kuralları farklıdır; anlık tek-frame zıplama kabul edilmez.
- Hard/soft shot-cut heuristic continuity kararını etkiler.
- Split kararı klibin başına değil klip geneline yayılan örnek pencerelerle alınır.
- Crop hareketi yatay clamp ve frame başına pan limiti ile sınırlandırılır.

## A/V Guardrail

- Render öncesi CFR normalize edilir.
- Merge sonrası `source_fps`, `normalized_fps`, `merged_output_drift_ms`, `dropped_or_duplicated_frame_estimate` ölçülür.
- `audio_validation` içinde `has_audio`, `audio_sample_rate`, `audio_channels`, `audio_duration`, `audio_validation_status` tutulur.
- Drift yüksekse render hard-fail olur.

## Debug ve Metadata

- Render raporu `tracking_quality`, `debug_tracking`, `debug_timing`, `audio_validation` alanlarını üretir.
- `DEBUG_RENDER_ARTIFACTS=1` ise geçici overlay çıktısı kalıcı debug bundle'a taşınır.
- Kalıcı debug yolu: `workspace/projects/<project_id>/debug/<clip_stem>/`

## Model

- Varsayılan model: `backend/config.YOLO_MODEL_PATH`
- Ultralytics YOLO kullanılır
