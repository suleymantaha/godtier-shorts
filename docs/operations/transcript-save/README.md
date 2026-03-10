# Transcript Save

Proje veya klip transkriptinin kaydedilmesi. SubtitleEditor veya Editor'dan tetiklenir.

## Akış

```
Frontend (düzenlenmiş segment listesi) → POST /api/transcript → JSON dosyaya yazma
```

## Tetikleyici

- **API**: `POST /api/transcript`
- **Backend**: `backend/api/routes/editor.py` → `save_transcript()`

## Parametreler

| Parametre | Açıklama |
|-----------|----------|
| Body | `TranscriptSegment[]` (Pydantic list) |
| project_id | Proje ID (query param, opsiyonel) |

## Hedef Dosya

- `project_id` varsa: `workspace/projects/{project_id}/transcript.json`
- Yoksa: `VIDEO_METADATA` (varsayılan proje)

## TranscriptSegment Yapısı

```json
{
  "text": "Metin",
  "start": 0.0,
  "end": 2.5,
  "speaker": "Bilinmeyen",
  "words": [
    {"word": "Metin", "start": 0.0, "end": 0.5, "score": 1.0}
  ]
}
```

## Notlar

- Proje transkripti: Tüm videonun transkripti
- Klip transkripti: Klip metadata'sında (`shorts/{clip}.json`) – reburn/save ile güncellenir

## İlgili

- [Subtitle Edit](../pages/subtitle-edit/README.md)
- [Reburn](./reburn/README.md)
