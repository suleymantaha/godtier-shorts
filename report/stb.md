# Full-Stack Durum Raporu

Tarih: 2026-03-22

Kapsam:
- Canlı uygulama: `http://127.0.0.1:5173`
- Canlı kanıt: `.playwright-cli/page-2026-03-21T22-07-04-089Z.yml`, `.playwright-cli/page-2026-03-21T22-07-32-344Z.yml`, `.playwright-cli/page-2026-03-21T22-07-50-058Z.yml`, `.playwright-cli/page-2026-03-21T22-08-18-606Z.yml`, `.playwright-cli/page-2026-03-21T22-08-55-946Z.yml`, `.playwright-cli/network-2026-03-21T22-08-04-085Z.log`, `.playwright-cli/console-2026-03-21T22-06-46-726Z.log`
- Kod yüzeyleri: `frontend/src/app/*`, `frontend/src/auth/*`, `frontend/src/components/{clipGallery,subtitleEditor,autoCutEditor}/*`, `frontend/src/api/*`, gerekli backend auth route’ları
- Test doğrulaması: `cd frontend && npm run test -- src/test/components/ClipGallery.test.tsx src/test/App.test.tsx --reporter=dot`

Not:
- Auto Cut boş durumu canlıda tutarlı göründü; burada önceliklendirilen bulgular çoğunlukla auth/runtime, Clip Library ve Subtitle Editor sınırında kümeleniyor.

## Kritik

### 1. Auth durumu canlı başarıya rağmen `AUTH:PAUSED` olarak kalıyor
- Bulgu:
  - Shell, footer ve HoloTerminal `AUTH:PAUSED` gösterirken aynı oturumda korumalı çağrılar başarılı oluyor ve Clip Library 5 klibi yükleyebiliyor.
- Canlı bağlam:
  - `.playwright-cli/page-2026-03-21T22-07-04-089Z.yml` içinde aynı anda `AUTH:PAUSED`, `5 Clips`, `5 Visible`, görünür clip kartları ve kullanıcı menüsü var.
  - `.playwright-cli/network-2026-03-21T22-08-04-085Z.log` içinde `GET /api/auth/whoami => 200` ve `GET /api/clips?page=1&page_size=200 => 200`.
- Kod/kanıt:
  - Clip Gallery, auth runtime kapalıyken bile recovery fetch çalıştırabiliyor: `frontend/src/components/clipGallery/useClipGalleryController.ts:148-189`, `frontend/src/components/clipGallery/useClipGalleryController.ts:682-694`.
  - Auth chip ve terminal yalnızca runtime store’daki `paused` etiketine bakıyor: `frontend/src/components/ui/ConnectionChip.tsx:19-50`, `frontend/src/components/HoloTerminal.tsx:40-57`.
  - Başarılı token reuse/fetch teoride store’u `fresh` yapmalı: `frontend/src/api/client.ts:214-235`, `frontend/src/auth/runtime.ts:46-55`.
- Tutarsızlık niteliği:
  - Runtime durumu ile gerçek network davranışı ayrışıyor.
- Etkisi:
  - Kullanıcı backend’in kapalı olduğunu düşünüyor.
  - WebSocket ve auth-bağımlı yüzeyler gereksiz yere kısıtlanabiliyor.
  - Hata ayıklama çok zorlaşıyor çünkü UI yanlış sağlık sinyali veriyor.
- Önerilen çözüm yönü:
  - `forceAuthRecovery` ile başarılı olan ilk korumalı çağrıdan sonra auth runtime zorunlu olarak `fresh`e taşınmalı.
  - `bootstrap/refreshing` ile gerçek `paused/auth blocked` durumları ayrı state’ler olarak modellenmeli.

### 2. Subtitle Editor canlı veriye rağmen sahte boş durum üretiyor
- Bulgu:
  - Clip Library aynı shell içinde 5 klip gösterirken Subtitle Editor proje modunda `Henüz proje yok`, klip modunda `Henüz klip yok` diyor.
- Canlı bağlam:
  - `.playwright-cli/page-2026-03-21T22-07-04-089Z.yml`: Clip Library dolu.
  - `.playwright-cli/page-2026-03-21T22-07-32-344Z.yml`: `Henüz proje yok. Video yükleyerek başlayın.`
  - `.playwright-cli/page-2026-03-21T22-07-50-058Z.yml`: `Henüz klip yok.`
- Kod/kanıt:
  - Subtitle bootstrap, `canUseProtectedRequests=false` iken tamamen erken dönüyor: `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts:237-266`.
  - Buna rağmen UI boş array’leri gerçek boşluk gibi sunuyor: `frontend/src/components/subtitleEditor/sections.tsx:554-559`.
  - Clip Gallery ise aynı koşul için recovery ve `auth_blocked` state modeli barındırıyor: `frontend/src/components/clipGallery/useClipGalleryController.ts:148-189`, `frontend/src/components/clipGallery/useClipGalleryController.ts:215-240`, `frontend/src/components/clipGallery/sections.tsx:359-383`.
- Tutarsızlık niteliği:
  - Aynı auth/runtime koşulu iki feature’da farklı yorumlanıyor.
- Etkisi:
  - Mevcut projeler görünmez oluyor.
  - Kullanıcı yanlışlıkla yeniden upload etmeye yönlendiriliyor.
  - “Veri yok” ile “erişim henüz toparlanmadı” ayrımı kayboluyor.
- Önerilen çözüm yönü:
  - Subtitle Editor’a açık `auth_blocked` ve `bootstrap_recovering` durumları eklenmeli.
  - Clip Gallery ile aynı recovery mantığı veya ortak bir protected-resource hook kullanılmalı.

## Yüksek

### 3. `Transcript Ready` rozetli klip, Subtitle Edit akışında `Klip transkripti bulunamadi` olarak açılıyor
- Bulgu:
  - Clip kartı “transcript hazır” diyor; aynı klip subtitle edit akışında `0 / 0 segment` ve recovery paneliyle açılıyor.
- Canlı bağlam:
  - `.playwright-cli/page-2026-03-21T22-07-04-089Z.yml`: clip kartlarında `Transcript Ready`.
  - `.playwright-cli/page-2026-03-21T22-08-55-946Z.yml`: `ODAK KLIP: cut_1_3736_3837.mp4`, `Altyazı (0 / 0 segment)`, `Klip transkripti bulunamadi`.
- Kod/kanıt:
  - Clip Library rozeti yalnızca `clip.has_transcript` alanına bakıyor: `frontend/src/components/clipGallery/sections.tsx:456-464`.
  - Subtitle workspace varsayılan olarak `needs_recovery` ile başlıyor: `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts:170-191`.
  - Transcript yükleme auth kapalıyken hiç başlamıyor: `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts:542-565`.
  - Recovery paneli bu varsayılan durumdan türetiliyor: `frontend/src/components/subtitleEditor/sections.tsx:905-930`.
- Tutarsızlık niteliği:
  - Kullanıcıya aynı clip için birbirini dışlayan iki durum gösteriliyor.
- Etkisi:
  - Gereksiz recovery/reburn denemeleri tetiklenebilir.
  - Clip Library rozetlerine güven azalır.
- Önerilen çözüm yönü:
  - Subtitle Editor, transcript sorgusu yapılmadan `not found` paneli göstermemeli.
  - `has_transcript=true` bilgisi ilk açılışta optimistic ready/pending state olarak taşınmalı.
  - Auth engeli varsa recovery UI yerine blokaj/pending mesajı gösterilmeli.

### 4. Clip Library görünürken sahiplik bağlamı `Account UNKNOWN` kalıyor
- Bulgu:
  - Kütüphane dolu olmasına rağmen header, aktif hesabı çözemiyor ve sahiplik/scope mesajı eksik kalıyor.
- Canlı bağlam:
  - `.playwright-cli/page-2026-03-21T22-07-04-089Z.yml`: `5 Clips` ile birlikte `Account UNKNOWN`.
  - Aynı anda network logunda `GET /api/auth/whoami => 200` var: `.playwright-cli/network-2026-03-21T22-08-04-085Z.log`.
- Kod/kanıt:
  - Ownership diagnostics yalnızca `canUseProtectedRequests=true` ise çalışıyor: `frontend/src/components/clipGallery/useClipGalleryController.ts:386-420`.
  - Recovery fetch yalnızca clip listesini zorluyor; diagnostics yolunu zorlamıyor: `frontend/src/components/clipGallery/useClipGalleryController.ts:360-364`.
  - Header, diagnostics null ise bilinçli olarak `UNKNOWN` yazıyor: `frontend/src/components/clipGallery/useClipGalleryController.ts:482-500`, `frontend/src/components/clipGallery/sections.tsx:152-161`.
- Tutarsızlık niteliği:
  - Varlık listesi görünür, ama kimlik/scope özeti görünmez.
- Etkisi:
  - Ownership recovery paneli doğru zamanda devreye giremiyor.
  - Kullanıcı hangi hesabın hangi klipleri gördüğünü anlayamıyor.
- Önerilen çözüm yönü:
  - Clip fetch recovery ile ownership diagnostics recovery aynı mekanizmada ele alınmalı.
  - En azından `whoami` sonucu kullanılarak geçici subject hash gösterilmeli.

## Orta

### 5. Subtitle Editor dikey short preview’i sabit 16:9 kutuya sıkıştırıyor
- Bulgu:
  - Clip Gallery kartları 9:16 iken Subtitle Editor preview alanı sabit `aspect-video`.
- Canlı bağlam:
  - Bu sorun mevcut auth kilidi yüzünden canlı subtitle preview’de tam görünmedi; kod ve gerçek medya formatları üzerinden doğrulandı.
- Kod/kanıt:
  - Clip kartı doğru olarak `aspect-[9/16]` kullanıyor: `frontend/src/components/clipGallery/sections.tsx:447-449`.
  - Subtitle preview sabit `aspect-video` kullanıyor: `frontend/src/components/subtitleEditor/sections.tsx:665-679`.
- Tutarsızlık niteliği:
  - Aynı clip, galeri ve editör arasında farklı geometriyle sunuluyor.
- Etkisi:
  - Subtitle yerleşimi ve güvenli alan kontrolü hatalı değerlendirilebilir.
- Önerilen çözüm yönü:
  - Aspect ratio metadata’dan veya `loadedmetadata` üzerinden dinamik belirlenmeli.

### 6. Render quality uyarıları ilk 3 maddeye kesiliyor
- Bulgu:
  - Render kalite paneli aynı anda birden fazla risk varken yalnızca ilk 3 uyarıyı gösteriyor.
- Canlı bağlam:
  - Bu varyant canlı shell’de tetiklenmedi; kod ve mevcut subtitle testleri üzerinden doğrulandı.
- Kod/kanıt:
  - Uyarılar `.slice(0, 3)` ile kesiliyor: `frontend/src/components/subtitleEditor/sections.tsx:432-438`.
  - Bu davranış testlerle de normalize edilmiş durumda: `frontend/src/test/components/SubtitleEditor.clip.test.tsx`.
- Tutarsızlık niteliği:
  - Kalite özeti eksik ama “tam” gibi görünüyor.
- Etkisi:
  - Daha ciddi alt uyarılar görünmeden kaybolabilir.
- Önerilen çözüm yönü:
  - Tüm uyarılar gösterilmeli veya “+N daha” genişletilebilir listeye dönülmeli.

### 7. Subtitle kaynak seçicileri yalnızca teknik kimlik ve dosya adına dayanıyor
- Bulgu:
  - Project selector `project.id`, clip selector ise sadece `clip.name` gösteriyor.
- Canlı bağlam:
  - `.playwright-cli/page-2026-03-21T22-07-32-344Z.yml` ve `.playwright-cli/page-2026-03-21T22-07-50-058Z.yml` içinde seçici yüzeyi çok zayıf bağlam sunuyor.
- Kod/kanıt:
  - Project seçenekleri yalnızca `project.id`: `frontend/src/components/subtitleEditor/sections.tsx:621-624`.
  - Clip seçenekleri yalnızca `clip.name`: `frontend/src/components/subtitleEditor/sections.tsx:631-636`.
- Tutarsızlık niteliği:
  - İnsan dostu seçim bilgisi yok; teknik iç anahtarlar doğrudan UI’ye sızıyor.
- Etkisi:
  - Büyük kütüphanelerde yanlış seçim ihtimali artar.
- Önerilen çözüm yönü:
  - `ui_title`, tarih, transcript durumu, süre ve proje etiketi seçeneklerde gösterilmeli.

## Düşük

### 8. Canlı konsolda performans ve bakım uyarıları var
- Bulgu:
  - Tarayıcı konsolunda deprecated API ve GPU stall uyarıları görünüyor.
- Canlı bağlam:
  - `.playwright-cli/console-2026-03-21T22-06-46-726Z.log`
  - Örnekler: `THREE.Clock deprecated`, `GPU stall due to ReadPixels`.
- Kod/kanıt:
  - Bu doğrudan çalışma zamanı sinyali; özellikle Three.js tabanlı arka plan/canvas katmanıyla ilişkili görünüyor.
- Tutarsızlık niteliği:
  - Kullanıcı akışını hemen kırmıyor ama performans ve bakım riskini büyütüyor.
- Etkisi:
  - Düşük FPS, gereksiz GPU baskısı, ileride library upgrade kırılmaları.
- Önerilen çözüm yönü:
  - Canvas render yolunda `ReadPixels` tetikleyen akışlar ve deprecated `Clock` kullanımı temizlenmeli.

### 9. Testler geçiyor ama ClipGallery testinde React `act(...)` uyarısı var
- Bulgu:
  - Hedefli test koşusu yeşil, ancak `ClipGallery` testlerinden biri state update uyarısı üretiyor.
- Canlı bağlam:
  - Komut sonucu: `22` test geçti.
  - Aynı koşuda `An update to ClipGallery inside a test was not wrapped in act(...)` uyarısı alındı.
- Kod/kanıt:
  - Test dosyası: `frontend/src/test/components/ClipGallery.test.tsx`
- Tutarsızlık niteliği:
  - Testler yeşil olsa da zamanlama/etkileşim modelini tam doğru temsil etmiyor olabilir.
- Etkisi:
  - Gelecekte flaky test ve yanlış güven hissi üretebilir.
- Önerilen çözüm yönü:
  - İlk render sonrası async update’ler `act` veya `findBy`/`waitFor` ile tam sarılmalı.

## Genel Desenler

- Tekrarlayan kök neden:
  - `canUseProtectedRequests` değeri, bazı yüzeylerde “backend geçici toparlanıyor” yerine doğrudan “boş veri” veya “kayıp transcript” olarak yorumlanıyor.
- İkinci kök neden:
  - Auth runtime, recovery fetch ve UI status bileşenleri tek bir doğruluk kaynağında birleşmiyor.
- Hızlı kazanımlar:
  - Subtitle Editor’a `auth_blocked/bootstrap_recovering` state eklemek.
  - Recovery sonrası auth runtime’ı `fresh`e senkronize etmek.
  - Clip Library ve Subtitle Editor arasında transcript durumunu tek sözleşmeden üretmek.
