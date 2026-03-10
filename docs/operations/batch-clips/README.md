# Batch Clips

Seçilen zaman aralığında AI ile toplu klip üretimi. Viral analiz ile segmentler belirlenir.

## Akış

```
Aralık seçimi (start_time, end_time) → Transkript filtreleme → Viral analiz (analyze_transcript_segment) → N segment → Her biri için run_manual_clip
```

## Tetikleyici

- **Frontend**: AutoCutEditor "Toplu Üret" butonu
- **API**: `POST /api/process-batch`
- **Backend**: `backend/api/routes/editor.py` → `process_batch_clips()`

## Parametreler

| Parametre | Açıklama |
|-----------|----------|
| project_id | Proje ID (transkript buradan okunur) |
| start_time | Aralık başlangıcı (sn) |
| end_time | Aralık bitişi (sn) |
| num_clips | Üretilecek klip sayısı |
| style_name | Altyazı stili |
| layout | single / split |

## Viral Analiz

`ViralAnalyzer.analyze_transcript_segment()`:
- Aralık içindeki transkript segmentlerini filtreler
- LLM veya fallback ile en viral N segment seçer
- Her segment: start_time, end_time, hook_text, ui_title, viral_score

## Fark: YouTube Pipeline vs Batch

| | YouTube Pipeline | Batch Clips |
|---|-----------------|-------------|
| Kaynak | YouTube URL | Mevcut proje |
| Transkript | İndirme sonrası | Proje transcript.json |
| Viral analiz | Tüm video | Sadece seçilen aralık |
| Proje | yt_{video_id} | up_{hash} veya yt_{id} |

## Çıktı

- `workspace/projects/{project_id}/shorts/short_{n}_{hook_slug}.mp4`
- Job tamamlanınca `output_paths` listesi job metadata'da

## İlgili

- [Viral Analyzer](../logic/viral-analyzer/README.md) – `analyze_transcript_segment`
- [Orchestrator](../../backend/core/orchestrator.py) – `run_batch_manual_clips`
- [Manual Cut](./manual-cut/README.md)
