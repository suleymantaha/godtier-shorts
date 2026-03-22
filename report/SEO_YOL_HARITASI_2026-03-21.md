# GodTier Shorts - SEO Yol Haritasi

**Tarih:** 2026-03-21  
**Kapsam:** Tam kapsamli organik buyume, teknik SEO, bilgi mimarisi, icerik sistemi, olcum ve dagitim  
**Durum:** Plan dokumani  
**Not:** Bu dokuman repo incelemesi ve resmi Google SEO rehberleri baz alinarak hazirlanmistir. Keyword hacimleri burada dogrulanmamis, niyet-temelli hipotez olarak onerilmistir.

## 1) Executive Summary

GodTier Shorts icin ciddi SEO kazanimi elde etmek istiyorsak, mevcut urun SPA'sinin icine birkac meta tag eklemek yeterli olmayacak. Mevcut frontend buyuk olcude auth-gated tek bir uygulama kabugu gibi calisiyor ve public, indekslenebilir sayfa agi sunmuyor. Bu nedenle SEO hedefi uygulamanin kendisi degil, uygulamanin etrafinda kurulacak public marketing/docs/content katmani olmalidir.

Onerilen model:

- `godtiershorts.com` veya ana domain: public marketing + docs + blog + comparison + tool sayfalari
- `app.godtiershorts.com` veya `/app`: mevcut urun arayuzu
- Public katman icin `Astro` tercih edilir; ikinci secenek `Next.js`
- Ilk 90 gunde hedef: indekslenebilir bilgi mimarisi, 20 cekirdek sayfa, Search Console kurulumu, teknik SEO tabani, ilk icerik ve comparison cluster'i

## 2) Repo Tabanli Mevcut Durum

Mevcut repo sinirlari:

- [frontend/index.html](../frontend/index.html) icinde yalniz temel `title` ve `description` var; sayfa bazli head yonetimi yok.
- [frontend/src/App.tsx](../frontend/src/App.tsx) tek uygulama kabugu gibi calisiyor.
- [frontend/src/app/sections.tsx](../frontend/src/app/sections.tsx) sekmeli, auth sonrasi kullanilan UI akisini tasiyor; URL bazli public route agi yok.
- [frontend/src/main.tsx](../frontend/src/main.tsx) Clerk publishable key bekliyor; bu da public crawl edilen sayfa modeli icin dogru temel degil.
- [backend/api/server.py](../backend/api/server.py) API/websocket odakli; public sitemap, robots veya SSR/SSG serving modeli tanimlamiyor.

Sonuc:

- Uygulama ici ekranlar dogrudan SEO hedefi olmamali.
- SEO icin ayri bir public bilgi mimarisi kurulmasi gerekiyor.
- Docs ve README icerigi yeniden paketlenerek public SEO varliklarina donusturulebilir.

## 3) Is Hedefi

SEO'nun burada amaci yalniz trafik degil, nitelikli boru hatti uretmektir.

Birincil hedefler:

- AI video repurposing kategorisinde aranabilir bir marka haline gelmek
- Ticari niyetli sorgulardan demo/signup/deneme akisi yaratmak
- Docs ve use-case sayfalariyla problem temelli girisler toplamak
- Comparison ve alternative sayfalariyla rakip talebini yakalamak
- Blog ve free tool yapisiyla ust-funnel organik trafik toplamak

Basari metrikleri:

- Indeksli sayfa sayisi
- Non-brand organik tiklama ve impression
- Ticari sayfalardan signup/demo oranlari
- Top 10 ve top 3 keyword sayisi
- Comparison page conversion rate
- Search Console coverage ve enhancement sagligi
- Core Web Vitals gecis orani

## 4) Hedef Kitle ve Mesaj

Oncelikli ICP gruplari:

- Solo creator ve YouTube creator
- Podcast sahipleri ve klip ekipleri
- Ajanslar ve social media operatorleri
- Online course / education creator'lari
- Kisa video odakli repurposing workflow arayan ekipler

Temel mesaj eksenleri:

- Long-form videodan hizli short uretimi
- AI destekli clip secimi
- Kinetic subtitle ve premium gorunum
- Lokal-first / kontrol hissi / is akisi sahipligi
- Editor + reburn + subtitle parity ile operasyonel duzeltilebilirlik

## 5) Onerilen Bilgi Mimarisi

Ana agac:

- `/`
- `/features`
- `/pricing`
- `/use-cases/...`
- `/compare/...`
- `/blog/...`
- `/docs/...`
- `/tools/...`
- `/about`
- `/contact`
- `/app` veya `app.` subdomain

Ilke:

- Ticari sayfalar ana domain kokune yakin olmali
- Documentation ana domainde `/docs` altinda yer almali
- Auth-gated uygulama SEO alanindan ayrilmali
- Her URL tek niyet tasimali

## 6) Teknik SEO Is Paketleri

### A. Mimari ve render modeli

- Public site icin `Astro` ile static-first kurulum yap
- Gereken yerlerde hybrid SSR kullan
- Uygulamayi ayri origin veya `/app` altina tasi
- Public katmanda JS bagimliligini azalt

### B. Indexation ve crawlability

- `robots.txt` olustur
- XML `sitemap.xml` ve gerekirse `sitemap-index.xml` olustur
- Sayfalarin kanonik URL'lerini belirle
- Gereksiz filtre/preview/test URL'lerini indeks disi birak
- Search Console property kur

### C. On-page temel

- Her sayfa icin benzersiz `title`
- Her sayfa icin benzersiz `meta description`
- Tutarli `h1`
- Open Graph / Twitter meta
- `WebSite`, `Organization`, uygun sayfalarda `SoftwareApplication`, `FAQPage`, `BreadcrumbList` schema
- Ic link agi ve breadcrumb yapisi

### D. Performans ve CWV

- LCP hedefi: <= 2.5s
- INP hedefi: <= 200ms
- CLS hedefi: <= 0.1
- Hero gorselleri, fontlar ve script yukunu optimize et
- PageSpeed Insights ve Search Console Core Web Vitals takibi kur

### E. Medya ve SERP gorunurlugu

- OG image pipeline
- Buyuk thumbnail'ler icin uygun onizleme kontrolu
- Gorseller icin anlamli `alt` text
- Video veya demo sayfalarinda uygun structured data arastir

## 7) Icerik ve Sayfa Stratejisi

Sayfa katmanlari:

- Money pages: home, features, pricing, key feature pages
- Use-case pages: creator, podcast, agency, course
- Comparison pages: rakip alternatif sayfalari
- Problem-solution pages: nasil yapilir ve workflow icerikleri
- Docs pages: urun kabiliyetlerini destekleyen yardimci bilgi katmani
- Tool pages: ucretsiz mini araclar veya generator sayfalari

Icerik ilkeleri:

- Her sayfa tek birincil keyword etrafinda yazilsin
- Sayfa niyeti ile CTA uyumlu olsun
- Template bazli ama kopya olmayan yapilar kullanilsin
- Rakip odakli sayfalarda dengeli, kanit temelli ve faydaci anlatim tercih edilsin
- Blog yazilari docs'u, docs sayfalari money pages'i beslesin

## 8) Olcum ve Operasyon

Kurulacak sistemler:

- Google Search Console
- Google Analytics 4 veya tercih edilen analytics
- CTA event tracking
- Demo / signup attribution
- Search query -> landing page -> conversion raporu
- Haftalik SEO scorecard

Operasyon ritmi:

- Haftalik: Search Console query review, yeni icerik yayini, internal link guncelleme
- Aylik: sitemap ve coverage audit, title/CTR optimizasyonu, comparison page refresh
- Ceyreklik: bilgi mimarisi genisletme, tool page ve programmatic SEO iterasyonu

## 9) 90 Gunluk Faz Plani

### Faz 0 - Hazirlik (2-4 gun)

- Domain ve URL karari ver
- Public site stack karari ver
- ICP ve positioning notlarini kesinlestir
- Search Console ve analytics hesabini hazirla

Cikis kriteri:

- Mimari karari net
- Alan adi/plansiz blokaj yok

### Faz 1 - Temel Altyapi (1-2 hafta)

- Marketing site iskeletini kur
- Home, features, pricing, docs hub, blog hub, comparison hub olustur
- robots, sitemap, canonical, schema, OG altyapisini ekle
- Search Console property ac

Cikis kriteri:

- Public site deploy edildi
- En az 8 temel sayfa indekslenebilir durumda

### Faz 2 - Cekirdek Ticari Yuzey (2-3 hafta)

- 4 use-case sayfasi
- 4 feature sayfasi
- 3 comparison sayfasi
- Pricing ve home copy iterasyonu
- CTA ve signup takibi

Cikis kriteri:

- Ilk 15-20 ticari URL yayinda
- Ic link agi kurulmus

### Faz 3 - Icerik Motoru (3-5 hafta)

- Haftalik 2-4 yazi
- Problem/solution blog cluster'i
- Docs sayfalarinin SEO uyumlu yeniden paketlenmesi
- FAQ, glossary ve workflow icerikleri

Cikis kriteri:

- Ilk 30+ indekslenebilir URL
- Search Console'da duzenli query girisi basladi

### Faz 4 - Olcek ve Savunma (surekli)

- Programmatic SEO
- Free tool pages
- Rakip sayfalarin genisletilmesi
- Backlink ve launch dagitimi
- CTR ve conversion optimizasyonu

## 10) Oncelik Sirasi

P0:

- Public site mimarisi
- Indexation altyapisi
- Home / features / pricing / use-cases / compare cekirdegi
- Search Console + analytics

P1:

- Docs yeniden paketleme
- Blog cluster
- FAQ ve schema genisletmesi
- CWV optimizasyonu

P2:

- Programmatic SEO
- Free tools
- Cok dilli genisleme
- Backlink playbook

## 11) Repo Icindeki Somut Uygulama Onerisi

Bu repo icin pratik uygulama:

- Kokte yeni bir `marketing/` klasoru ac
- `Astro` tabanli public site kur
- Mevcut `frontend/` urun uygulamasi ayni kalsin
- Ana domain public siteye, `app.` subdomain urun uygulamasina gitsin
- `docs/` altindaki operasyonel ve urunsel bilgi, public docs katmanina secilerek tasinsin

Opsiyonel ikinci model:

- Ayni deploy icinde `/` marketing, `/app` urun uygulamasi

Bu model yalniz deployment karmasikligi kabul ediliyorsa secilmeli.

## 12) Riskler

- Public site ile urun uygulamasi ayni bilgi mimarisine zorlanirsa crawl ve UX karisabilir
- Rakip/alternative sayfalari yuzeysel yazilirsa dusuk kalite gorunebilir
- Blog uretimi yapilip dagitim ve linking yapilmazsa trafik birikimi yavas olur
- Sadece ust-funnel blog yazip ticari sayfa eksik birakmak signup etkisini dusurur
- CWV ve indeksleme takibi olmadan yayina cikmak ileride temizligi pahali hale getirir

## 13) Definition Of Done

Ilk anlamli SEO release'i "tamamlandi" demek icin su kosullar saglanmali:

- Public marketing/docs site yayinda
- `robots.txt` ve XML sitemap aktif
- Search Console bagli
- Home, pricing, features, en az 4 use-case, en az 3 comparison sayfasi yayinda
- Her sayfada unique title, description, h1, canonical mevcut
- Breadcrumb ve temel schema aktif
- Analytics ve CTA eventleri calisiyor
- Ilk 30 gunluk scorecard kurulmus

## 14) Sonraki Net Uygulama Adimi

Bu planin repo icindeki ilk uygulanabilir parcasi:

1. `marketing/` iskeletini kurmak
2. bu plana gore URL agacini dosyalastirmak
3. ilk 20 sayfanin content brief'lerini ve slug'larini cikarmak
4. home/features/pricing/use-case/comparison sayfalarinin ilk kopyasini yazmak

## 15) Referanslar

Resmi kaynaklar:

- Google Search Essentials teknik gereksinimler: https://developers.google.com/search/docs/essentials/technical
- SEO Starter Guide: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- Title links rehberi: https://developers.google.com/search/docs/advanced/appearance/title-link
- Snippet ve meta description rehberi: https://developers.google.com/search/docs/appearance/snippet
- Structured data genel kurallar: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
- Sitemap olusturma ve gonderme: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Robots.txt giris rehberi: https://developers.google.com/search/docs/crawling-indexing/robots/intro
- Robots meta tag spesifikasyonu: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag
- Site names rehberi: https://developers.google.com/search/docs/appearance/site-names
- Sitelinks rehberi: https://developers.google.com/search/docs/appearance/sitelinks
- Web Vitals / Core Web Vitals: https://web.dev/articles/vitals
