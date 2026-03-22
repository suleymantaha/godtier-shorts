# GodTier Shorts - SEO Keyword ve Site Haritasi

**Tarih:** 2026-03-21  
**Kapsam:** Ilk dalga SEO bilgi mimarisi, 20 sayfalik URL plani, keyword niyeti, CTA ve schema onerileri  
**Not:** Keyword'ler arama niyeti hipotezidir. Hacim, zorluk ve ulke bazli oncelik Search Console + keyword araci ile ayrica dogrulanmalidir.

## 1) Varsayimlar

- Birincil pazar: global, English-first ticari SEO
- Ikincil pazar: Turkish founder-led content ve yerel arama varyasyonlari
- Uygulama auth-gated oldugu icin SEO yuzeyi public marketing/docs katmaninda kurulacak
- Ilk sprintte amac "en cok trafik" degil, "en dogru ticari niyetli URL seti"dir

## 2) Sayfa Kume Mantigi

Ilk 20 sayfa 5 kumeye ayrilir:

- Foundation: marka ve para sayfalari
- Feature: urun kabiliyetlerini ayri niyetlere baglayan sayfalar
- Use-case: personaya gore sayfalar
- Compare: rakip aramalarini yakalayan sayfalar
- Education: how-to ve docs katmani

## 3) Ilk 20 URL Matrisi

| # | URL | Sayfa tipi | Funnel | Arama niyeti | Primary keyword | Secondary keyword'ler | Ana aci / promise | CTA | Onerilen schema |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` | Home | BOFU/MOFU | Kategori + marka | ai shorts generator | youtube shorts generator, video repurposing tool | Long-form videodan premium short uret | Start free / Book demo | `WebSite`, `Organization` |
| 2 | `/features` | Hub | MOFU | Ozellik kesfi | video repurposing software features | ai clipping features, short video workflow | Tum kabiliyetleri tek haritada goster | Explore features | `BreadcrumbList` |
| 3 | `/pricing` | Money page | BOFU | Satin alma | ai shorts generator pricing | video repurposing software pricing | Fiyatlandirma ve kullanim modeli | Start free | `BreadcrumbList` |
| 4 | `/use-cases/youtube-to-shorts` | Use-case | BOFU | Donusum gorevi | youtube to shorts | turn youtube video into shorts, youtube clip maker | YouTube videodan kisa video uret | Try workflow | `BreadcrumbList`, `FAQPage` |
| 5 | `/use-cases/podcast-to-clips` | Use-case | BOFU | Donusum gorevi | podcast to clips | podcast clips generator, podcast highlights maker | Podcast bolumlerini viral kliplere cevir | Try workflow | `BreadcrumbList`, `FAQPage` |
| 6 | `/use-cases/course-to-shorts` | Use-case | MOFU/BOFU | Education repurposing | course video to shorts | webinar to clips, educational content repurposing | Ders ve webinar icerigini kisa formata donustur | See examples | `BreadcrumbList` |
| 7 | `/use-cases/for-agencies` | Use-case | BOFU | Ajans cagrisi | video repurposing for agencies | social media agency clip workflow | Ajanslar icin olceklenebilir short uretim akisi | Book demo | `BreadcrumbList`, `FAQPage` |
| 8 | `/features/auto-cut` | Feature | MOFU | Ozellik arastirmasi | auto clip generator | ai auto cut video, auto clipping tool | AI ile otomatik clip secimi | See auto cut | `BreadcrumbList` |
| 9 | `/features/kinetic-subtitles` | Feature | MOFU | Ozellik arastirmasi | kinetic subtitle generator | animated subtitles for shorts, tiktok subtitle style | Premium gorunen kinetic subtitle sistemi | See subtitle styles | `BreadcrumbList` |
| 10 | `/features/viral-clip-detection` | Feature | MOFU | Ozellik arastirmasi | viral clip generator | ai viral moment finder, highlight detection | Viral anlarin secimi ve puanlanmasi | See how it works | `BreadcrumbList` |
| 11 | `/features/transcript-editor` | Feature | MOFU | Ozellik arastirmasi | video transcript editor | subtitle editor for clips, transcript reburn | Transcript duzelt, kaydet, yeniden bas | Edit transcript | `BreadcrumbList` |
| 12 | `/features/clip-editor` | Feature | MOFU | Ozellik arastirmasi | clip editor for shorts | vertical video editor for clips, short form editor | Kadran, overlay ve reburn duzeltmeleri | Open editor | `BreadcrumbList` |
| 13 | `/compare/opus-clip-alternative` | BOFU compare | BOFU | Rakip alternatifi | opus clip alternative | alternative to opus clip, opus clip competitor | Daha fazla kontrol ve subtitle/editor odagi | Compare now | `BreadcrumbList`, `FAQPage` |
| 14 | `/compare/submagic-alternative` | BOFU compare | BOFU | Rakip alternatifi | submagic alternative | alternative to submagic, subtitle tool alternative | Subtitle kalitesi + workflow kontrolu | Compare now | `BreadcrumbList`, `FAQPage` |
| 15 | `/compare/captions-alternative` | BOFU compare | BOFU | Rakip alternatifi | captions alternative | alternative to captions app, captions competitor | Editing + repurposing workflow farki | Compare now | `BreadcrumbList`, `FAQPage` |
| 16 | `/blog/how-to-turn-youtube-videos-into-shorts` | Blog | TOFU/MOFU | Nasil yapilir | how to turn youtube videos into shorts | make shorts from long videos, repurpose youtube videos | Egitici rehber + urune gecis | Read guide / Try app | `Article`, `BreadcrumbList` |
| 17 | `/blog/how-to-add-kinetic-subtitles-to-video` | Blog | TOFU/MOFU | Nasil yapilir | how to add kinetic subtitles to video | animated subtitles tutorial, short video subtitles | Subtitle problemi uzerinden giris | Read guide / See feature | `Article`, `BreadcrumbList` |
| 18 | `/blog/best-ai-shorts-generators` | Blog / listicle | TOFU/MOFU | Karsilastirma | best ai shorts generators | best tools for youtube shorts, best video repurposing tools | Kategori talebini topla, tarafli ama guvenilir liste | See comparison | `Article`, `BreadcrumbList` |
| 19 | `/docs/youtube-shorts-workflow` | Docs | MOFU | Uygulama/teknik anlayis | youtube shorts workflow | shorts production workflow, clip pipeline | Urun is akisini acikla | View workflow / Try app | `TechArticle`, `BreadcrumbList` |
| 20 | `/tools/youtube-shorts-hook-ideas` | Free tool | TOFU/MOFU | Arac kullanimi | youtube shorts hook generator | hook ideas for shorts, short video hook ideas | Ucretsiz aracla lead capture | Generate hooks | `WebApplication`, `BreadcrumbList` |

## 4) Kume Bazli Notlar

Foundation:

- Home ve pricing sayfalari en guclu ic link alan URL'ler olmali
- Header ve footer link yapisi burayi guclendirmeli

Feature:

- Her feature sayfasi bir use-case ve bir docs sayfasina link vermeli
- Ana feature hub, alt feature sayfalarina anlamli anchor text ile baglanmali

Use-case:

- Persona dili ve ROI odagi kuvvetli olmali
- Ornek workflow ve output screenshot/video eklenmeli

Compare:

- Denge, kanit ve acik trade-off dili kullanilmali
- Yuzeysel "biz daha iyiyiz" tonu yerine "kim icin hangi secenek uygun" anlatilmali

Education:

- Blog sayfalari ticari CTA ile bitmeli
- Docs sayfalari ise urun ozelliklerine geri akmali

## 5) Ic Linkleme Kurallari

- Home -> features, pricing, use-cases, compare hub
- Features hub -> tum feature sayfalari
- Her feature -> ilgili use-case + ilgili blog + ilgili docs
- Her use-case -> pricing + feature + comparison
- Her comparison -> pricing + relevant feature + demo CTA
- Blog -> use-case veya feature CTA
- Docs -> ilgili feature ve use-case CTA

## 6) Ilk Dalgada Uretilmesi Gereken Asset'ler

- Ana marka OG image
- Her comparison page icin ozel OG image
- Subtitle style gallery gorselleri
- Workflow diyagramlari
- Hero demo screenshot'lari
- FAQ bloklari

## 7) Icerik Brief Kalibi

Her sayfa brief'i su alanlari icermeli:

- search intent
- primary keyword
- 3-5 supporting keyword
- unique angle
- target persona
- proof points
- objection handling
- CTA
- internal links in/out
- schema

## 8) Lokasyon ve Dil Stratejisi

Onerilen ilk kademe:

- Ticari sayfalar English-first
- Founder's blog veya case notlari Turkish olarak ikinci katmanda yayinlanabilir
- Product UI dili ile SEO dili birebir ayni olmak zorunda degil

Ikinci kademe:

- Turkish use-case sayfalari
- Turkish how-to blog cluster'i
- EN/TR hreflang yalniz gercekten esit kalite saglanirsa acilmali

## 9) Sonraki Uretim Sirasi

En mantikli yayin sirasi:

1. `/`
2. `/features`
3. `/pricing`
4. `/use-cases/youtube-to-shorts`
5. `/features/kinetic-subtitles`
6. `/compare/opus-clip-alternative`
7. `/blog/how-to-turn-youtube-videos-into-shorts`
8. `/docs/youtube-shorts-workflow`
9. `/use-cases/podcast-to-clips`
10. `/tools/youtube-shorts-hook-ideas`

## 10) Referanslar

- Google SEO Starter Guide: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- Title links: https://developers.google.com/search/docs/advanced/appearance/title-link
- Snippets and meta descriptions: https://developers.google.com/search/docs/appearance/snippet
- Structured data genel kurallar: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
- Sitemap rehberi: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Sitelinks rehberi: https://developers.google.com/search/docs/appearance/sitelinks
