# Viral Analyzer

LLM ile transkript analizi ve viral segment seçimi. OpenRouter/Claude veya local (LM Studio) destekler.

## Dosya

`backend/services/viral_analyzer.py`

## Sınıf

`ViralAnalyzer(engine: str = "cloud")`

- `engine="cloud"`: OpenRouter API (moonshotai/kimi-k2.5, Claude vb.)
- `engine="local"`: LM Studio local server

## Ana Metodlar

| Metod | Açıklama |
|-------|----------|
| `analyze_metadata(metadata_file, num_clips, duration_min, duration_max)` | Tüm transkriptten viral segmentler seçer (YouTube pipeline) |
| `analyze_transcript_segment(transcript_data, limit, window_start, window_end)` | Belirli aralıktan segment seçer (Batch clips) |

## ViralSegment Çıktısı

```python
{
  "start_time": float,
  "end_time": float,
  "hook_text": str,      # İlk 3 sn kanca metni
  "ui_title": str,       # Dashboard başlığı
  "social_caption": str,  # TikTok/Shorts açıklaması
  "viral_score": int     # 1-100
}
```

## Fallback

LLM başarısız olursa `_build_fallback_segments()`:
- Transkript segmentlerinden sliding window
- Yoğunluk skoru (chars/duration + segment sayısı)
- min_duration, max_duration aralığında segmentler

## Ortam Değişkenleri

- `OPENROUTER_API_KEY`: OpenRouter API anahtarı
- `ANTHROPIC_API_KEY`: Claude için (opsiyonel)
- `LMSTUDIO_MODEL`: Local model adı
- `LMSTUDIO_BASE_URL`: Local server URL (varsayılan: http://localhost:1234/v1)

## Çıktı Dosyası

YouTube pipeline: `workspace/projects/{id}/viral_segments.json`
