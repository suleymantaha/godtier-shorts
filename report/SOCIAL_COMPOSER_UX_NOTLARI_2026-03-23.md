# Social Composer UX Notları

Tarih: 2026-03-23

Bu not, gelişmiş sosyal yayın araçlarında görülen compose/publish desenlerini bizim ürüne nasıl uyarladığımızı kayda geçirmek için hazırlandı.

## Gözlenen Ürün Desenleri

### 1. Compose ile dashboard ayrılıyor

Gelişmiş araçlarda paylaşım oluşturma ve operasyon yönetimi tek ekranda ezilmiyor.

- Later, görsel planlama ve feed preview işini `Calendar/Preview` alanında ayrı ele alıyor.
- Hootsuite, içerik takvimini yönetim alanı olarak öne çıkarıyor.
- Sprout Social, compose/publishing akışını planlama ve onay akışlarıyla birlikte ama ayrı ürün yüzeyi olarak konumluyor.

Ürün sonucu:
- `Social dashboard` ile `Social composer` ayrılmalı.
- Dashboard bağlantılar, takvim, queue ve analytics için kalmalı.
- Clip bazlı paylaşım ayrı bir compose sayfasında açılmalı.

## 2. Preview-first deneyim temel beklenti

Özellikle video-first publishing araçlarında kullanıcı boş form değil, yayın önizlemesi görmek istiyor.

- Later Visual Planner scheduled/draft içerikleri görsel preview içinde gösteriyor.
- Sprout ve benzeri publishing araçlarında compose ekranı, yayınlanacak içeriği ve hedef ağları aynı bağlamda sunuyor.

Ürün sonucu:
- Klipten `Paylaş` dendiğinde modal yerine ayrı compose sayfası açılmalı.
- Sayfada video preview ve platforma göre post mockup birlikte yer almalı.
- Kullanıcı yayınlamadan önce hook, caption ve hashtag’i gerçek bağlamda görmeli.

## 3. Otomatik içerik kit’i düzenlenebilir kalıyor

Modern araçlar AI veya metadata ile öneri üretse de kullanıcıyı kilitlemiyor.

- Sprout publishing materyallerinde compose, schedule, approval ve suggestion akışlarının birlikte kullanıldığı görülüyor.
- Buffer/Sprout sınıfı araçlarda öneri mantığı editlenebilir draft yüzeyi üstüne oturuyor.

Ürün sonucu:
- Hook, title, caption ve hashtags otomatik dolu gelmeli.
- Bu alanlar tek tıkla düzenlenebilir olmalı.
- CTA ve keyword hint gibi yardımcı sinyaller preview yanında görünmeli.

## 4. Takvim ve queue compose’dan sonra geliyor

Compose sayfası yayın oluşturmaya odaklı; calendar/queue ise operasyon ekranı.

Ürün sonucu:
- Compose sayfasında sadece ilgili klibin son publish işleri görünmeli.
- Genel queue ve calendar yönetimi dashboard tarafında kalmalı.

## Bizim Entegrasyon Kararı

Bu checkpointte aşağıdaki ürün yönü uygulanmıştır:

- Ana ekrandaki clip kartlarında `Share` aksiyonu artık dedicated compose page açar.
- Yeni sayfa query tabanlı route ile gelir: `/?tab=social-compose&...`
- `Social` sekmesi dashboard olarak kalır.
- `Social Compose` sayfası video preview, post preview, otomatik hook/caption/hashtags/CTA ve publish-schedule aksiyonlarını tek yerde toplar.
- Modal compose yüzeyi korunur, fakat ana galeride ana yol olmaktan çıkarılmıştır.

## Kod Karşılıkları

- [SocialComposePage.tsx](/home/arch/godtier-shorts/frontend/src/components/SocialComposePage.tsx)
- [helpers.ts](/home/arch/godtier-shorts/frontend/src/components/shareComposer/helpers.ts)
- [ClipGallery.tsx](/home/arch/godtier-shorts/frontend/src/components/ClipGallery.tsx)
- [sections.tsx](/home/arch/godtier-shorts/frontend/src/app/sections.tsx)

## Dış Referanslar

- Later Visual Instagram Planner:
  - https://help.later.com/hc/en-us/articles/360043244233-Preview-Your-Feed-With-Your-Visual-Instagram-Planner
- Hootsuite content calendar:
  - https://help.hootsuite.com/hc/it/articles/1260804306009-Gestisci-il-tuo-calendario-dei-contenuti
- Sprout Social Publishing:
  - https://media.sproutsocial.com/uploads/Sprout-Academy-Publishing-Study-Guide-1.pdf
- Buffer publishing/product materials:
  - https://buffer.com/static/downloads/visual-guides.pdf
