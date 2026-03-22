# Clip Editor

Tek bir klip üzerinde manuel düzenleme: kadraj, stil, zaman aralığı, reburn. Editor bileşeni kullanılır. ClipGallery'den "Edit" ile veya doğrudan `editingClip` state ile açılır.

## Bileşen

- **Editor** | `frontend/src/components/Editor.tsx`

## Modlar

| Mod | Açıklama |
|-----|----------|
| `master` | Yeni video yükleme + kesim (AutoCutEditor benzeri) |
| `clip` | Mevcut klip üzerinde düzenleme |

## Özellikler

1. **Video Kaynağı**
   - `master`: Yerel upload veya proje seçimi
   - `clip`: `targetClip.url` ile mevcut klip

2. **Kadraj (VideoOverlay)**
   - Sürükle-bırak ile `center_x` ayarı
   - SteadyCam crop merkez noktası

3. **Zaman Aralığı**
   - RangeSlider ile start/end
   - `startTime`, `endTime` → ManualJobRequest

4. **Stil**
   - Subtitle style dropdown (HORMOZI, TIKTOK vb.)
   - Layout: single / split

5. **Oturum Saklama**
   - `godtier-editor-master-session` (master modu)
   - `godtier-editor-clip-session:{project}:{clip}` (klip modu)

## API Endpoint'leri

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/api/process-manual` | Manuel klip render (start, end, center_x, style) |
| POST | `/api/reburn` | Altyazı yeniden basma |
| POST | `/api/upload` | Video yükleme (master modu) |
| GET | `/api/transcript` | Proje transkripti |
| GET | `/api/clip-transcript/{clip_name}` | Klip transkripti |

## Kullanıcı Akışı

1. ClipGallery'den "Edit" ile veya doğrudan klip seç
2. VideoOverlay ile kadrajı ayarla (center_x)
3. RangeSlider ile zaman aralığını belirle
4. Stil seç
5. "Render" veya "Reburn" butonuna bas
6. Job tamamlanınca yeni klip üretilir

## İlgili Dokümantasyon

- [Manual Cut](../../operations/manual-cut/README.md)
- [Reburn](../../operations/reburn/README.md)
- [Video Processor](../../logic/video-processor/README.md)
