# CONFIGURE Sayfası

Ana yapılandırma ve dağıtım merkezi. YouTube URL ile otomatik pipeline başlatma, stil seçimi, job kuyruğu ve klip galerisi burada yer alır.

## Bileşenler


| Bileşen             | Dosya                                         | Açıklama                                                |
| ------------------- | --------------------------------------------- | ------------------------------------------------------- |
| **JobForm**         | `frontend/src/components/JobForm.tsx`         | YouTube URL, stil, AI engine, klip sayısı, süre aralığı |
| **SubtitlePreview** | `frontend/src/components/SubtitlePreview.tsx` | Seçilen altyazı stilinin canlı önizlemesi               |
| **HoloTerminal**    | `frontend/src/components/HoloTerminal.tsx`    | WebSocket ile job log akışı                             |
| **JobQueue**        | `frontend/src/components/JobQueue.tsx`        | Aktif job listesi, iptal butonu                         |
| **ClipGallery**     | `frontend/src/components/ClipGallery.tsx`     | Üretilen klipler, edit butonu                           |


## Kullanıcı Akışı

1. **JobForm**: YouTube URL gir → stil seç (TIKTOK, HORMOZI vb.) → AI engine seç → klip sayısı belirle → "VİDEOYU ÜRET"
2. **İşlem**: `POST /api/start-job` tetiklenir, job kuyruğa alınır
3. **HoloTerminal**: WebSocket ile gerçek zamanlı log gösterilir
4. **JobQueue**: İşlemler listelenir, iptal edilebilir
5. **ClipGallery**: Tamamlanan klipler görüntülenir, "Edit" ile Clip Editor açılır

## API Endpoint'leri


| Method | Endpoint                   | Açıklama                  |
| ------ | -------------------------- | ------------------------- |
| GET    | `/api/styles`              | Altyazı stilleri listesi  |
| POST   | `/api/start-job`           | YouTube pipeline başlatır |
| GET    | `/api/jobs`                | Tüm job'lar               |
| POST   | `/api/cancel-job/{job_id}` | Job iptali                |
| GET    | `/api/clips`               | Tüm klipler (ClipGallery) |


## İlgili Dokümantasyon

- [YouTube Pipeline](../flows/youtube-pipeline.md)
- [Transcription](../architecture/transcription.md)
- [Viral Analyzer](../architecture/viral-analyzer.md)

