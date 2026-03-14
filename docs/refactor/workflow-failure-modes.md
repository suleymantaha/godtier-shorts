# Workflow Data-Flow ve Failure Modes

## Data-Flow (Pipeline)
1. URL doğrulama
2. Proje çözümleme (`ProjectPaths`)
3. Master asset hazırlığı (yt-dlp + ffmpeg)
4. Transkript üretimi (WhisperX)
5. Viral segment analizi
6. Segment render + metadata persist

## Failure-Mode Tablosu

| Akış Adımı | Olası Hata | Belirti | Kök Neden | Mitigasyon |
|---|---|---|---|---|
| URL doğrulama | `ValueError` | İş başlamadan hata | Geçersiz URL/ID | Erken validation + anlaşılır mesaj |
| Komut çalıştırma | `RuntimeError` timeout | Uzun bekleme sonrası fail | Dış süreç yanıt vermiyor | `CommandRunner` timeout + cancel kill |
| Transkript | `RuntimeError` | Pipeline 30-45% civarı durur | WhisperX/IO problemi | Stage-level try/except + status güncelleme |
| LLM analiz | segment yok | "viral segment bulunamadı" | düşük kaliteli transcript veya model cevabı | fallback/prompt tuning + retry stratejisi |
| Render | ffmpeg/yolo hatası | klip üretimi yarım kalır | GPU/codec/asset bozukluğu | per-clip izolasyon + temp cleanup |
| Reburn | metadata overwrite riski | JSON bozulması | beklenmeyen metadata shape | load/merge guard + schema doğrulama |

## Cancel/Timeout Sözleşmesi
- `cancel_event` set olduğunda subprocess kill edilir.
- Timeout durumunda iş adımı `RuntimeError` ile fail edilir.
- Temp artifact cleanup her iki durumda da çalışmalıdır.
