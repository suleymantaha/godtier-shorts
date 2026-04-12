# Manual Cut

Tek veya çoklu manuel kesim. Zaman aralığı veya cut_points ile belirlenir.

## Varyantlar

| Varyant                 | Tetikleyici                                                 | Orchestrator Metodu                  |
| ----------------------- | ----------------------------------------------------------- | ------------------------------------ |
| Tek klip                | `POST /api/manual-cut-upload` (num_clips=1, cut_points yok) | `run_manual_clip()`                  |
| Cut points              | `POST /api/manual-cut-upload` (cut_points JSON)             | `run_manual_clips_from_cut_points()` |
| Tek klip (mevcut proje) | `POST /api/process-manual`                                  | `run_manual_clip()`                  |

## Tek Klip Akışı

1. Proje/master video belirleme
2. Transkript yükleme (proje veya isteğe gönderilen)
3. `_shift_timestamps`: Aralık dışı segmentleri filtrele, zamanları 0'a hizala
   - Kelime payload'ında `score: null` gelirse normalizasyon aşamasında `1.0` kabul edilir
4. ASS altyazı üretimi (skip_subtitles=False ise)
5. Video işleme:
   - `cut_as_short=True`: YOLO + SteadyCam crop
   - `cut_as_short=False`: Sadece segment kesimi (crop yok)
   - `center_x` verildiyse tracking yerine manuel merkez kullanılır
6. Burn-in (altyazı varsa)
7. Kalite metadata'sı ve opsiyonel debug artifact kaydetme

## Cut Points Akışı

`cut_points=[t0, t1, t2, ...]` → Aralıklar: [t0-t1], [t1-t2], ...

Her aralık için `run_manual_clip()` çağrılır.

## API Parametreleri

### manual-cut-upload (Form)

| Parametre      | Tip        | Açıklama               |
| -------------- | ---------- | ---------------------- |
| file           | UploadFile | Video dosyası          |
| start_time     | float      | Başlangıç (sn)         |
| end_time       | float      | Bitiş (sn)             |
| style_name     | str        | HORMOZI vb.            |
| skip_subtitles | bool       | Altyazı atlama         |
| num_clips      | int        | 1-20 (batch için)      |
| cut_points     | str        | JSON array [t0,t1,...] |
| cut_as_short   | bool       | YOLO crop kullan       |

Response contract:

- `POST /api/manual-cut-upload` ilk response'ta `status`, `job_id`, `project_id` döndürür.
- `clip_name` ve `output_url` alanları terminal `completed` olana kadar `null` kalır.
- Arka plan exception'ları job'u sessizce bırakmaz; terminal `error` durumuna yazılır.

### process-manual (JSON)

| Parametre            | Açıklama                    |
| -------------------- | --------------------------- |
| project_id           | Proje ID                    |
| start_time, end_time | Aralık                      |
| transcript           | Opsiyonel segment listesi   |
| style_name           | Altyazı stili               |
| center_x             | Manuel kadraj merkezi (0-1) |
| layout               | single / split              |

## Çıktı

- `workspace/projects/{project_id}/shorts/manual_{job_id}.mp4` veya `cut_{n}_{start}_{end}.mp4`
- Public erişim: `/api/projects/{project_id}/shorts/{clip_name}`
- Her klip için `.json` metadata; `render_quality_score`, `tracking_quality`, `transcript_quality`, `audio_validation`, `debug_artifacts` alanlarını içerebilir

Owner-scoped path note:

- Diskte gerçek proje yolu `workspace/projects/<subject_hash>/<project_id>/...` olarak tutulur.
- API public path'i değişmez; owner scope route seviyesinde korunur.

## İlgili

- [Editor routes](../../backend/api/routes/editor.py)
- [Orchestrator](../../backend/core/orchestrator.py) – `run_manual_clip`, `run_manual_clips_from_cut_points`
- [Video Processor](../architecture/video-processor.md)

## Verification Note 2026-04-01

- `process-manual`, `manual-cut-upload`, ve batch manual varyantları backend full suite içinde tekrar geçti.
- Background failure'lar artık terminal job state'e düşürülüyor; job izleme tarafında sessiz asılı kalma beklenmez.
