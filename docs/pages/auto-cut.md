# AUTO CUT Sayfası

Video yükleme, zaman aralığı seçimi ve otomatik/manuel kesim işlemleri. AutoCutEditor bileşeni bu sayfayı oluşturur.

## Bileşen

- **AutoCutEditor** | `frontend/src/components/AutoCutEditor.tsx`

## Özellikler

1. **Video Kaynağı**
   - Yerel dosya yükleme (drag & drop veya file input)
   - Mevcut proje seçimi (dropdown)

2. **Zaman Aralığı**
   - `RangeSlider` ile start/end süre seçimi
   - Video önizleme ile senkron

3. **Kesim Modları**
   - **Tek klip**: start–end aralığında tek klip
   - **Çoklu klip**: `cut_points` (marker) ile manuel kesim noktaları
   - **Otomatik**: `num_clips` ile AI aralıkta eşit bölümlere ayırır

4. **Oturum Saklama**
   - `localStorage` ile `godtier-auto-cut-session` (projectId, startTime, endTime, currentJobId)

## API Endpoint'leri

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/api/upload` | Video yükle + transkripsiyon başlat |
| POST | `/api/manual-cut-upload` | Video + zaman aralığı ile async kesim (tek/çoklu); ilk response `job_id` döndürür |
| POST | `/api/process-batch` | Mevcut projede aralıkta async toplu klip üretimi |
| GET | `/api/projects` | Proje listesi |
| GET | `/api/clips` | Tüm klipler |

## Kullanıcı Akışı

1. Video yükle veya proje seç
2. Transkripsiyon tamamlanana kadar bekle (WebSocket ile takip)
3. RangeSlider ile start/end ayarla
4. İsteğe bağlı: marker ekle (cut_points) veya num_clips belirle
5. "Kes" veya "Toplu Üret" butonuna bas
6. İlk response sadece job başlangıcını teyit eder; terminal durum `GET /api/jobs` veya WebSocket üzerinden izlenir
7. Job `completed` olduğunda klipler ClipGallery'de görünür; `error`, `review_required`, `empty` gibi terminal durumlar da UI'da gösterilir

## İlgili Dokümantasyon

- [Upload & Transcribe](../flows/upload-transcribe.md)
- [Manual Cut](../flows/manual-cut.md)
- [Batch Clips](../flows/batch-clips.md)

## Verification Note 2026-04-01

- `manual-cut-upload` artık job tabanlı async kontratla çalışır; final `clip_name` ve `output_url` terminal başarıda yazılır.
- `process-batch` terminal durum garantisiyle backend full suite içinde tekrar geçti.
- Auto Cut ile ilgili frontend full suite ve hedef subtitle/editor akış testleri geçti.
