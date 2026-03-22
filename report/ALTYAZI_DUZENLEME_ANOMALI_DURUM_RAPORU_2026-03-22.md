# Altyazi Duzenleme Sayfasi Anomali Durum Raporu

Tarih: 2026-03-22

## Ozet

- Bu surum onceki rapora gore duzeltildi: canli, oturum acilmis UI gozlemi artik raporun ana kaniti.
- Canli shell'e giris basarili oldu; ancak sayfa `signed out` degil, `authenticated shell + AUTH:PAUSED` durumunda aciliyor.
- Bu nedenle canli bulgularin merkezi problemi giris duvari degil; subtitle editor'un `korumali istekler duraklatildi` durumunu yanlis modelleyip bos veri durumu gibi sunmasi.
- Ayrica kod ve workspace verisi uzerinden, canli oturumda dogrudan tetiklenemeyen ama gercek risk olusturan 3 ek sorun dogrulandi: 9:16 preview oranlama, render warning kesme mantigi ve dusuk-guvenli transcript satirlarinin isaretlenmemesi.

## Kanit Tabani

### Canli UI

- Authenticated shell snapshot:
  - `.playwright-cli/page-2026-03-21T21-49-51-832Z.yml`
- Canli `SUBTITLE EDIT` proje modu:
  - `.playwright-cli/page-2026-03-21T21-50-13-034Z.yml`
  - `.playwright-cli/page-2026-03-21T21-50-24-365Z.png`
- Canli `SUBTITLE EDIT` klip modu:
  - `.playwright-cli/page-2026-03-21T21-50-45-550Z.yml`
  - `.playwright-cli/page-2026-03-21T21-50-53-932Z.png`

### Kod

- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts`
- `frontend/src/components/subtitleEditor/sections.tsx`
- `frontend/src/auth/useResilientAuth.ts`
- `frontend/src/auth/useResilientAuth.helpers.ts`
- `frontend/src/test/components/SubtitleEditor.auth.test.tsx`
- `frontend/src/test/components/SubtitleEditor.clip.test.tsx`

### Workspace Verisi

- `workspace/projects/a4069ffa93794396e1a7bf578c6a7b8b/up_a4069ffa93794396e1a7bf578c6a7b8b_1f063fc510c6/transcript.json`
- `workspace/projects/a4069ffa93794396e1a7bf578c6a7b8b/up_a4069ffa93794396e1a7bf578c6a7b8b_1f063fc510c6/shorts/*.json`
- `workspace/projects/a4069ffa93794396e1a7bf578c6a7b8b/yt_a4069ffa93794396e1a7bf578c6a7b8b_mvYVI3wbY_g/shorts/*.json`
- Ornek medya kareleri:
  - `/tmp/subtitle_audit_frames/up_cut1_10s.jpg`
  - `/tmp/subtitle_audit_frames/yt_short1_5s.jpg`

### Test Dogrulamasi

- `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.clip.test.tsx src/test/components/SubtitleEditor.auth.test.tsx --reporter=dot`
- Sonuc: `3` dosya, `19` test, tamami gecti

## Bulgular

### 1. Kritik: `AUTH:PAUSED` durumunda sayfa gercek engeli gizleyip sahte bos durum gosteriyor

- Baglam:
  - Canli subtitle editor shell icinde footer'da `AUTH:PAUSED` gorunuyor.
  - Buna ragmen proje modunda `Henüz proje yok. Video yükleyerek başlayın.`, klip modunda `Henüz klip yok.` mesaji gosteriliyor.
  - Kodda kaynak yukleme etkisi `canUseProtectedRequests === false` oldugunda hic calismiyor; ancak secim state'i varsayilan olarak `projectsStatus='good'`, `projects=[]`, `clips=[]` kaliyor.
- Tutarsizlik turu:
  - Durum modelleme hatasi
  - Nedensellik kopuklugu
  - Yanlis bos durum
- Kanit:
  - Canli proje modu: `.playwright-cli/page-2026-03-21T21-50-13-034Z.yml`
  - Canli klip modu: `.playwright-cli/page-2026-03-21T21-50-45-550Z.yml`
  - `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts:252-266`
  - `frontend/src/components/subtitleEditor/sections.tsx:542-559`
  - `frontend/src/test/components/SubtitleEditor.auth.test.tsx:27-43`
- Etki:
  - Kullanici veri yok saniyor; oysa gercek problem auth/runtime blokaji.
  - Yanlis aksiyon oneriliyor: "Video yükleyerek başlayın." ifadesi, mevcut projeler olsa bile kullaniciyi yeni is yuklemeye itebilir.
  - Sayfa butunlugu bozuluyor: footer `AUTH:PAUSED` diyor, ana icerik `hic veri yok` diyor.
- Onerilen cozum:
  - `canUseProtectedRequests === false` icin subtitle editor'a ozel bir `auth_blocked` state ekleyin.
  - Bu durumda `Henüz proje yok` / `Henüz klip yok` yerine `Korumali istekler duraklatildi` mesaji gosterin.
  - Mümkünse pause reason (`unauthorized`, `token_expired`, `auth_provider_unavailable`) subtitle editor iceriginde acikca yazilsin.

### 2. Yuksek: Auth blokaji sadece footer chip'te kaliyor; asıl çalışma alanında görünür açıklama yok

- Baglam:
  - Canli shell aciliyor ve subtitle editor'a girilebiliyor.
  - Ancak editor iceriginde kullaniciya auth blokajini anlatan inline bir kart, banner veya recovery CTA yok.
  - Aynı uygulamanin log paneli `Protected requests are paused. Reconnect auth to resume live logs.` diyebiliyor; subtitle editor bu netligi tasimiyor.
- Tutarsizlik turu:
  - Baglam iletimi eksikligi
  - Bilgi hiyerarsisi hatasi
- Kanit:
  - `.playwright-cli/page-2026-03-21T21-50-24-365Z.png`
  - `frontend/src/components/HoloTerminal.tsx:46-49`
  - `frontend/src/components/subtitleEditor/sections.tsx:542-559`
- Etki:
  - Kullanici ekranin neden calismadigini anlamiyor.
  - Subtitle editor, uygulamanin geri kalanindaki auth/connection diliyle tutarsiz davraniyor.
  - Sorun tespiti icin footer'in sag altindaki kucuk chip'e bagimlilik olusuyor.
- Onerilen cozum:
  - Subtitle editor icerigine auth-block banner ekleyin.
  - `Reconnect auth`, `refresh session`, `retry protected access` gibi net aksiyonlar sunun.
  - Footer chip'i ikincil sinyal olarak birakin; asil aciklama icerikte olsun.

### 3. Yuksek: Klip preview mantigi 9:16 klipleri sabit 16:9 kutuya zorluyor

- Kanit seviyesi:
  - Kod + workspace verisi
  - Canli oturumda secilebilir klip gelmedigi icin bu bulgu shell icinde tetiklenemedi, ama veri ve component mantigi net.
- Baglam:
  - Orneklenen klipler `1080x1920`.
  - `VideoPreviewCard` sabit `aspect-video` kapsayici kullaniyor.
  - Bu da dikey short preview'un yatay kutuda letterbox ile sunulmasina yol aciyor.
- Tutarsizlik turu:
  - Uzamsal temsil hatasi
  - Medya baglamlama problemi
- Kanit:
  - `frontend/src/components/subtitleEditor/sections.tsx:645-679`
  - `workspace/projects/.../cut_1_3736_3837.mp4` -> `1080x1920`
  - `workspace/projects/.../short_1_şeytanin_bi̇le_siniri_var_ama_.mp4` -> `1080x1920`
  - `/tmp/subtitle_audit_frames/up_cut1_10s.jpg`
  - `/tmp/subtitle_audit_frames/yt_short1_5s.jpg`
- Etki:
  - Subtitle yerleşimi, lower-third collision ve framing kararları hatalı algılanabilir.
  - Kullanici short-format sonucu editor preview'unda dogru temsil edilmis sanabilir.
- Onerilen cozum:
  - Preview oranini secilen medyanin gercek aspect ratio'suna gore hesaplayin.
  - Klip modunda 9:16 varsayimi, proje modunda 16:9 veya metadata tabanli oran kullanin.

### 4. Yuksek: Render warning sistemi ilk 3 mesaja kesiliyor; daha kritik uyarılar sessizce kayboluyor

- Kanit seviyesi:
  - Kod + test + render metadata
- Baglam:
  - `buildRenderWarnings()` butun eslesmeleri topluyor ama `.slice(0, 3)` uyguluyor.
  - Siralama sabit; severity tabanli degil.
  - Testler bilerek `A/V drift`, `audio invalid` ve `lower-third` uyarilarinin dusmesini dogruluyor.
- Tutarsizlik turu:
  - Onceliklendirme hatasi
  - Kalite sinyali kaybi
- Kanit:
  - `frontend/src/components/subtitleEditor/sections.tsx:406-439`
  - `frontend/src/test/components/SubtitleEditor.clip.test.tsx:102-175`
  - `workspace/projects/.../cut_1_7107_7264.json` -> `lower_third_collision_detected=true`
  - `workspace/projects/.../short_1_şeytanin_bi̇le_siniri_var_ama_.json` -> `tracking_quality.status=fallback`, `lower_third_collision_detected=true`
- Etki:
  - Kullanici render kalitesini kismen gorur ama tam risk setini gormez.
  - "Kalite Özeti" basi altinda gercekten kismi bir ozet sunulur.
- Onerilen cozum:
  - Severity tabanli siralama yapin.
  - `+N ek uyari` gostergesi ekleyin.
  - `audio invalid`, `A/V drift`, `lower-third collision`, `NVENC fallback` gibi uyarilari asla sessizce dusurmeyin.

### 5. Orta: Dusuk-guvenli transcript satirlari zaman ve anlam bozulmasi yaratiyor; editor bunu isaretlemiyor

- Kanit seviyesi:
  - Kod + transcript verisi
- Baglam:
  - Workspace transcript'lerinde dusuk skorlu ASR kelimeleri cok sayida.
  - Ozellikle zaman/baglam ifadesi tasiyan satirlarda bozulma var:
    - `9.83-16.87`: `ver yansın tv'den gündem özelliğine Herkese iyi akşamlar Serkan Özle karşınızdayız gündemi`
    - `28.89-37.68`: `inşallah iyi olur Akşamları sabahlarımız bakalım...`
    - `3742.29-3746.07`: `üç gün dördüncü gün aladdin abisi`
  - Editor bu satirlari normal transcript gibi sunuyor; kullaniciya guven sinyali vermiyor.
- Tutarsizlik turu:
  - Temporal anlamsal bozulma
  - Icerik baglami belirsizligi
- Kanit:
  - `workspace/projects/.../up_.../transcript.json`
  - Ozet istatistik:
    - `3801` segment
    - `136` adet `<0.1` skor kelime
    - `787` buyuk gap
  - `frontend/src/components/subtitleEditor/sections.tsx:752-807`
- Etki:
  - Kullanici hatali ASR metnini gercek baglam zannedebilir.
  - Zaman, once-sonra, gun, yarin gibi ifadelerde yanlis yorum riski artar.
- Onerilen cozum:
  - Segment veya kelime guven skorlarini gosterin.
  - `supheli transcript` etiketi ekleyin.
  - `text_word_mismatch` veya dusuk skor alan segmentleri vurgulayin.

### 6. Orta: Proje secimi anlamli kaynak baglami yerine teknik ID mantigina dayaniyor

- Kanit seviyesi:
  - Kod + manifest verisi
- Baglam:
  - Proje secicide yalnizca `project.id` label olarak kullaniliyor.
  - Mevcut local `project_manifest.json` dosyalarinda `title`, `source_type`, `url` alanlari bos.
  - Canli oturum auth blokajinda oldugu icin secilebilir proje gelmedi; fakat kod akisi anlamli kaynak baglami uretmiyor.
- Tutarsizlik turu:
  - Baglam eksikligi
  - Secim zihinsel modeli zayifligi
- Kanit:
  - `frontend/src/components/subtitleEditor/sections.tsx:617-624`
  - `workspace/projects/.../yt_.../project_manifest.json`
  - `workspace/projects/.../up_.../project_manifest.json`
- Etki:
  - Birden fazla proje oldugunda yanlis kaynak secimi riski buyur.
  - Subtitle editor, "hangi video/klip/transcript uzerindeyim" sorusuna guclu cevap vermez.
- Onerilen cozum:
  - Proje secicide baslik, kaynak tipi ve kisa baglam gosterin.
  - Teknik ID'yi ikincil metadata yapin.

## Genel Durum

- Canli UI acisindan en buyuk sorun subtitle editor'un auth blokajini dogru modellememesi.
- Medya ve transcript tarafindaki daha derin kalite riskleri gercek ama canli oturumda tetiklenemeyen ikinci katman problemler olarak ele alinmali.
- Orneklenen ham medya karelerinde fizik kurallarina, biyolojik sureclere veya evrensel zaman akisina aykiri gorsel bir anomali tespit edilmedi.

## Hizli Aksiyon Listesi

1. Subtitle editor'a `auth_blocked` gorunumu ekleyin.
2. `Henüz proje yok` ve `Henüz klip yok` mesajlarini auth blokajinda gostermeyin.
3. Render warning sistemini severity tabanli hale getirin.
4. Klip preview aspect ratio mantigini gercek medya oranina baglayin.
5. Supheli transcript segmentleri icin guven/uyari katmani ekleyin.
