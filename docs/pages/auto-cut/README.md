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
| POST | `/api/manual-cut-upload` | Video + zaman aralığı ile kesim (tek/çoklu) |
| POST | `/api/process-batch` | Mevcut projede aralıkta toplu klip üretimi |
| GET | `/api/projects` | Proje listesi |
| GET | `/api/clips` | Tüm klipler |

## Kullanıcı Akışı

1. Video yükle veya proje seç
2. Transkripsiyon tamamlanana kadar bekle (WebSocket ile takip)
3. RangeSlider ile start/end ayarla
4. İsteğe bağlı: marker ekle (cut_points) veya num_clips belirle
5. "Kes" veya "Toplu Üret" butonuna bas
6. Job tamamlanınca ClipGallery'de görünür

## İlgili Dokümantasyon

- [Upload & Transcribe](../operations/upload-transcribe/README.md)
- [Manual Cut](../operations/manual-cut/README.md)
- [Batch Clips](../operations/batch-clips/README.md)
