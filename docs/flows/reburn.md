# Reburn

Mevcut klibe yeni stil/layout ile altyazı yeniden basma. Video kesimi yapılmaz, sadece altyazı burn-in güncellenir.

## Akış

```
Mevcut klip → Transkript (mevcut veya güncel) → Yeni ASS → burn-in → kalite metadata güncelleme
```

## Tetikleyici

- **Frontend**: SubtitleEditor "Reburn", Editor "Reburn"
- **API**: `POST /api/reburn`
- **Backend**: `backend/api/routes/editor.py` → `reburn_clip()`

## Parametreler

| Parametre | Açıklama |
|-----------|----------|
| clip_name | Klip dosya adı (örn: manual_xxx.mp4) |
| project_id | Proje ID (legacy için null) |
| transcript | Segment listesi (opsiyonel, yoksa mevcut metadata'dan) |
| style_name | Yeni altyazı stili |

Response contract:

- `POST /api/reburn` ilk response'ta yalnız `status` ve `job_id` döndürür.
- Final sonuç `GET /api/jobs`, WebSocket ilerlemesi veya güncellenmiş clip metadata üzerinden okunur.
- Runtime hata olursa job terminal `error` durumuna düşürülür.

## Orchestrator: reburn_subtitles()

1. Klip yolunu çöz (project_id ile `shorts/` veya legacy `outputs/`)
2. Transkript: istekten veya `.json` metadata'dan
3. Geçici ASS dosyası üret
4. `SubtitleRenderer.burn_subtitles_to_video()` ile mevcut videoya burn-in
5. Orijinal klip üzerine yazılır (in-place)
6. `transcript_quality`, `subtitle_layout_quality`, `render_quality_score` ve varsa `debug_artifacts` güncellenir

## Kullanım Senaryoları

- **SubtitleEditor**: Proje/klip transkriptini düzenledikten sonra yeni stille reburn
- **Editor**: Klip üzerinde sadece stil değiştirip reburn (kadraj/zaman değişmez)

## Script

`scripts/reburn_clip.py` – CLI ile reburn:

```bash
python scripts/reburn_clip.py --project ID --clip NAME [--layout split] [--style HORMOZI]
```

## Transkript Kaydetme

Reburn öncesi transkript düzenlemesi yapıldığında `POST /api/transcript` ile kaydedilir.

- **Tetikleyici**: SubtitleEditor veya Editor'dan "Kaydet"
- **Backend**: `save_transcript()` – `backend/api/routes/editor.py`
- **Hedef**: `project_id` varsa `workspace/projects/{project_id}/transcript.json`, yoksa varsayılan proje
- **Body**: `TranscriptSegment[]` (Pydantic list)
- **Not**: Proje transkripti tüm videonun; klip transkripti `shorts/{clip}.json` metadata'da – reburn/save ile güncellenir

## Kalite Özeti

- Reburn yeni tracking üretmez; varsa mevcut tracking/audio metriklerini metadata'dan korur.
- Clip modunda SubtitleEditor bu metadata içinden read-only kalite kartı gösterir.

## Verification Note 2026-04-01

- Reburn backend kontratı ve hata terminalizasyonu backend full suite ile tekrar geçti.
- SubtitleEditor ve Clip Editor reburn tetikleme yolları frontend full suite içinde tekrar geçti.

## İlgili

- [Subtitle Renderer](../architecture/subtitle-renderer.md)
- [Subtitle Styles](../architecture/subtitle-styles.md)
- [Orchestrator](../../backend/core/orchestrator.py) – `reburn_subtitles`
- [Subtitle Editor](../pages/subtitle-editor.md)
