# SUBTITLE EDIT Sayfası

Proje veya klip transkriptini düzenleme. SubtitleEditor bileşeni bu sayfayı oluşturur.

## Bileşen

- **SubtitleEditor** | `frontend/src/components/SubtitleEditor.tsx`

## Özellikler

1. **Mod Seçimi**
   - **Proje**: Proje transkripti (`transcript.json`)
   - **Klip**: Klip transkripti (`.clip.json` metadata)

2. **Proje/Klip Seçimi**
   - Dropdown ile proje veya klip seçimi
   - Video önizleme (master.mp4 veya klip URL)

3. **Transkript Düzenleme**
   - Segment listesi (word-level timing)
   - Metin değişikliği
   - Kaydet butonu

4. **Reburn**
   - Stil değiştir → "Reburn" ile yeni altyazı basma

## API Endpoint'leri

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/transcript?project_id=` | Proje transkripti |
| POST | `/api/transcript` | Transkript kaydetme |
| POST | `/api/reburn` | Altyazı yeniden basma |
| GET | `/api/clip-transcript/{clip_name}` | Klip transkripti |
| GET | `/api/projects` | Proje listesi |
| GET | `/api/clips` | Klip listesi |

## Kullanıcı Akışı

1. Mod seç (proje / klip)
2. Proje veya klip seç
3. Transkript yüklenir
4. Gerekirse metin düzenle
5. "Kaydet" → proje/klip transkript güncellenir
6. İsteğe bağlı: stil değiştir → "Reburn" ile yeni altyazı bas

## İlgili Dokümantasyon

- [Transcript Save](../operations/transcript-save/README.md)
- [Reburn](../operations/reburn/README.md)
- [Subtitle Styles](../logic/subtitle-styles/README.md)
