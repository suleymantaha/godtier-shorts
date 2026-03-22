Mevcut kod tabanındaki tüm bileşenler için endüstri standartlarında kapsamlı bir kod incelemesi ve analiz raporu hazırlanmasını bekliyorum. Bu inceleme, production ortamında çalışan yazılımlar için uygulanan profesyonel kod denetimi metodolojileri temelinde yürütülmeli; yerel geliştirme ortamında doğrulanabilir, tekrar üretilebilir ve ileride CI/CD pipeline entegrasyonuna uygun detay seviyesinde olmalıdır.

Bu çalışma yalnızca belirli bir dosya veya dar bir modül grubu ile sınırlı kalmamalıdır. İnceleme, proje genelini kapsamalı ve aşağıdaki alanları bütüncül olarak değerlendirmelidir:

- Backend katmanı: `backend/api`, `backend/core`, `backend/services`, `backend/models`
- Frontend katmanı: `frontend/src` altındaki uygulama, API istemcisi, store, hook, component ve editor akışları
- Test katmanı: `backend/tests`, `frontend/src/test`
- Operasyonel ve kalite scriptleri: `scripts/`
- Konfigürasyon ve bağımlılık manifestleri: `pyproject.toml`, `requirements.txt`, `frontend/package.json`, `pyrightconfig.json`, `pyre.toml`
- CI/CD ve doğrulama akışları: `.github/workflows/verify.yml`, `scripts/verify.sh`
- Dokümantasyon ve mevcut teknik raporlar: `README.md`, `docs/`, `report/`

İnceleme, özellikle sistemin yüksek riskli ve iş açısından kritik alanlarına daha fazla derinlik ayırmalıdır. Bu kapsamda transcription, viral analysis, workflow orchestration, video processing, subtitle rendering, clip editor, reburn akışları, API sözleşmeleri, frontend-backend parity, render metadata zinciri ve kalite raporlama davranışları öncelikli değerlendirme alanları olarak ele alınmalıdır.

İnceleme Süreci ve Kapsam Boyutları

Birinci Boyut: Mimari ve Tasarım Analizi

Kod tabanının genel mimarisini, modül sınırlarını, katmanlar arası sorumluluk dağılımını, sınıf hiyerarşilerini, fonksiyon organizasyonunu, bağımlılık yönlerini ve modülerlik seviyesini detaylı şekilde değerlendirin. Backend ve frontend tarafındaki yapıların birbirleriyle nasıl konuştuğunu, orchestrator yaklaşımını, servis ayrışmasını, editor ve render akışlarının nasıl modellendiğini inceleyin.

SOLID prensiplerinin uygulanma durumunu sistematik olarak analiz edin. Open/Closed Principle açısından modüllerin genişlemeye açık, doğrudan değişikliğe bağımlı olup olmadığını; Liskov Substitution Principle açısından soyutlamaların ve veri sözleşmelerinin yer değiştirebilirliğini; Dependency Inversion Principle açısından üst seviye akışların alt seviye implementasyonlara ne kadar sıkı bağlı olduğunu; Single Responsibility Principle açısından sınıf ve fonksiyonların kaç farklı değişim nedenine sahip olduğunu değerlendirin. Interface segregation, encapsulation, abstraction seviyesi, design pattern kullanımı ve God object, feature envy, shotgun surgery, primitive obsession gibi antipattern risklerini belirleyin.

İkinci Boyut: Bağımlılık ve Entegrasyon Analizi

Tüm proje genelindeki modüller, dosyalar ve servisler arasındaki bağımlılıkları derinlemesine analiz edin. Import graph yapısını, bağımlılık yönlerini, katman ihlallerini, döngüsel bağımlılık risklerini ve tight coupling noktalarını tespit edin. Backend servisleri ile API katmanı arasındaki veri akışını, frontend ile backend arasındaki sözleşmeleri, render metadata ve kalite sinyallerinin nasıl üretildiğini ve tüketildiğini, editor ve reburn süreçlerinde veri dönüşümlerinin doğruluğunu inceleyin.

Özellikle şu entegrasyon noktalarını yüksek öncelikle değerlendirin:
- API request/response contract’ları
- Workflow runtime ve helper zinciri
- Subtitle style, render, preview ve overlay parity
- Project/clip metadata üretimi ve tüketimi
- Frontend konfigürasyon katmanı ile backend preset ve runtime davranışlarının tutarlılığı
- Scriptler, verify akışı ve operasyonel komutların güncel kodla uyumu

Interface tanımlarının, veri sınıflarının, serialization/deserialization süreçlerinin ve sözleşme netliğinin yeterliliğini değerlendirin. Gelecekte yapılacak değişikliklerin mevcut sistemi ne ölçüde etkileyeceğini ve kırılgan entegrasyon alanlarını belirleyin.

Üçüncü Boyut: Hata ve Bug Tespiti

Potansiyel mantıksal hataları, exception handling eksikliklerini, hata yönetim stratejilerini ve runtime güvenilirlik problemlerini kapsamlı şekilde inceleyin. Edge case’leri, null/None kaynaklı hataları, tip uyuşmazlıklarını, unutulan return ifadelerini, yanlış varsayılan değerleri, mutable default argument tuzaklarını, yanlış operator precedence durumlarını, off-by-one ve boundary condition hatalarını, kaynak sızıntılarını, yanlış kapsamda tanımlanan değişkenleri ve sessiz fallback davranışlarını sistematik olarak tespit edin.

Error propagation mekanizmalarının yeterliliğini, hata bastırma davranışlarını, loglama ile hata zinciri arasındaki ilişkiyi, subprocess ve dosya sistemi çağrılarındaki dayanıklılığı, timeout/cancel davranışlarını ve yanlış başarı durumlarına yol açabilecek koşulları değerlendirin. Üretim ortamında yanlış pozitif başarı, sessiz veri kaybı veya bozuk çıktı üretimi yaratabilecek senaryoları özellikle vurgulayın.

Dördüncü Boyut: Performans Analizi

Fonksiyonları ve kritik akışları algoritmik karmaşıklık açısından değerlendirin. Gereksiz hesaplamaları, tekrarlayan veri taramalarını, O(n²) veya daha kötü davranışları, nested loop darboğazlarını, fazla object allocation noktalarını, gereksiz string işleme veya JSON yüklerini ve hotspot olabilecek bölgeleri belirleyin.

Memory pressure, large payload handling, rapor şişmesi, gereksiz payload retention, caching eksikliği, subprocess maliyeti, render ve burn süreçlerindeki CPU/GPU fallback davranışları, I/O yoğun alanlar ve büyük transcript veya metadata yükleri altındaki riskleri değerlendirin. Benchmark veya profiling yoksa bunu açıkça belirtin ve performans riski olarak notlayın.

Beşinci Boyut: Kod Tekrarı ve Bakım Kolaylığı

DRY prensibine uyumu değerlendirin ve kod tekrarının bulunduğu noktaları somut satır numaralarıyla belirtin. İsimlendirme kalitesi, okunabilirlik, magic number ve magic string kullanımı, hardcoded davranışlar, konfigürasyon yönetimi, type hint kalitesi, docstring ve inline comment yeterliliği, fonksiyon uzunlukları, cyclomatic complexity ve düşük cohesion alanlarını analiz edin.

Teknik borç üreten yapıları, zaman içinde değişmeyi pahalı hale getiren kararları, brittle test kalıplarını, dar kapsamlı ama sık kırılan sözleşmeleri ve bakım maliyetini artıran yapıları net şekilde belgeleyin. Özellikle “public contract başka bir şey söylüyor ama gerçek implementasyon daha dar davranıyor” türü drift alanlarını ayrı işaretleyin.

Altıncı Boyut: Güvenlik Analizi

Input validation, veri sanitization, path handling, subprocess çağrıları, external tool entegrasyonları, secrets yönetimi, environment variable kullanımı, yetkilendirme kontrolleri, dosya erişim sınırları, güvenli URL/route üretimi, log sanitization ve PII veri işleme davranışlarını değerlendirin.

Command injection, path traversal, insecure deserialization, resource exhaustion, denial-of-service, zayıf doğrulama, yanlış hata mesajı sızıntısı ve log üzerinden hassas veri yayılımı risklerini inceleyin. OWASP Top 10 perspektifiyle anlamlı riskleri haritalayın. Uygunsa CWE referansı verin; yalnız gerçek ve anlamlı eşleşmelerde CVSS/CWE ekleyin. Yapay veya zorlama güvenlik sınıflandırmalarından kaçının.

Yedinci Boyut: Kritik Alt Sistem Analizi

Projedeki kritik alt sistemleri derinlemesine inceleyin. Özellikle şu alanlar için daha ayrıntılı analiz beklenmektedir:
- Subtitle rendering ve subtitle editing pipeline’ı
- Transcription veri akışı ve transcript şeması
- Video processing ve render quality akışları
- Workflow orchestration ve runtime helper zinciri
- Frontend preview, overlay ve editor parity
- Reburn, manual cut, batch clip ve YouTube pipeline süreçleri

Bu bölümde zamanlama doğruluğu, style/preset parity, metadata sürekliliği, kalite alanlarının üretimi, preview ile final render arasındaki farklar, lower-third/safe-area davranışları, overflow ve event overlap sinyalleri, kullanıcıya yansıyan kalite hataları ve operasyonel fallback’ler detaylı olarak ele alınmalıdır.

Sekizinci Boyut: Test Coverage ve Kalite Metrikleri

Mevcut test coverage yaklaşımını, unit/integration/smoke/e2e yüzeylerini, test isolation kalitesini, fixture yönetimini, mocking stratejilerini ve coverage gap’lerini değerlendirin. Testlerin gerçek üretim risklerini ne kadar yakaladığını analiz edin. Yalnız test varlığına değil, testlerin anlamlı riskleri kapsayıp kapsamadığına odaklanın.

Mevcut durumda çalışan doğrulama akışlarını ve eksik kalite kapılarını ayırın. Yerel ortamda çalıştırılabilen testler ile sadece öneri düzeyinde kalan kalite araçlarını net biçimde sınıflandırın. Coverage, lint, type-check, security scan veya dead code detection araçları mevcut değilse bunu eksiklik olarak raporlayın ve entegrasyon önerisi sunun.

Dokuzuncu Boyut: Concurrency ve Thread Safety

Multi-threading, shared mutable state, cancellation, background job yürütümü, subprocess yönetimi, WebSocket veya event tabanlı akışlar, thread-safe olmayan veri alanları, race condition potansiyelleri ve deadlock risklerini inceleyin. GIL etkisi, concurrent access kalıpları, async/await varsa event loop uyumu ve aynı instance’ın çoklu akışta yeniden kullanımı gibi riskleri değerlendirin.

Özellikle mutable report/state objeleri, cache veya singleton davranışları, import-time side effect’ler ve aynı servis nesnesinin tekrar kullanımından doğabilecek veri karışmalarını vurgulayın.

Onuncu Boyut: Internationalization ve Localization

Character encoding, Unicode normalization, mixed-script içerik, RTL/LTR davranışları, font fallback, text measurement doğruluğu, locale-aware formatting ve çok dilli içerik desteğini inceleyin. Özellikle subtitle, preview, overlay ve editor yüzeylerinde CJK, emoji, combining mark, Arabic/Hebrew/Persian ve mixed-direction içeriklerin ne kadar doğru işlendiğini değerlendirin.

Onbirinci Boyut: Dependency Management ve Package Analysis

Python ve frontend bağımlılıklarını analiz edin. `requirements.txt`, `pyproject.toml`, `frontend/package.json` ve lock dosyaları üzerinden outdated dependency, unused dependency, version drift, toolchain uyumsuzluğu, gereksiz paket kullanımı, güvenlik riski taşıyan kütüphaneler ve eksik kalite araçlarını değerlendirin. Transitive dependency risklerini ve manifestlerde tanımlı ama süreçte kullanılmayan araçları da not edin.

Onikinci Boyut: Documentation ve Knowledge Transfer

`README.md`, `docs/`, `report/` ve operasyonel rehberleri değerlendirerek dokümantasyonun güncelliğini, doğruluğunu ve onboarding yeterliliğini inceleyin. Mimari dokümanlar ile gerçek kod davranışları arasındaki farkları, bayat kalmış anlatımları, hatalı örnek komutları ve knowledge transfer eksiklerini tespit edin. Mevcut raporların güncel kodu ne ölçüde yansıttığını ayrıca değerlendirin.

Her tespit edilen sorun için aşağıdaki bilgileri eksiksiz şekilde sağlayın:

- Sorunun başlığı
- Detaylı açıklaması
- Kök neden analizi
- Dosya adı, fonksiyon/sınıf adı ve kesin satır numarası
- Etki seviyesi: `critical`, `high`, `medium`, `low`
- Yeniden üretilebilirlik durumu: `confirmed`, `likely`, `inferred`
- Potansiyel operasyonel etkiler
- Önerilen çözüm stratejisi
- Uygun ve minimal iyileştirilmiş kod örneği
- Alternatif çözüm önerileri
- Uygunsa CWE numarası
- Uygunsa CVSS v3.1 score ve vector string

Rapor Hazırlama Kuralları

Analiz yalnız varsayımsal gözlemlere dayanmamalıdır. Mümkün olan her durumda kod okuması, test çalıştırma, komut çıktısı, import analizi, bağımlılık kontrolü ve mevcut dokümantasyon ile çapraz doğrulama yapılmalıdır. Daha önce hazırlanmış raporlar yardımcı kaynak olarak kullanılabilir; ancak nihai bulgular güncel kod tabanı üzerinden yeniden doğrulanmalıdır.

Araç veya kalite kontrol adımı mevcut ortamda kurulu değilse bu durum açıkça belirtilmeli; “çalıştırılamadı”, “yapılandırılmamış”, “repo içinde tanımlı ama aktif değil” gibi kesin ifadelerle raporlanmalıdır. Mevcut olmayan bir aracın çıktısı uydurulmamalıdır.

Rapor Formatı ve Çıktı Gereksinimleri

Analiz sonunda aşağıdaki bileşenleri eksiksiz şekilde sunun:

- Executive summary
- Scope and methodology
- Repo architecture snapshot
- Severity sırasına göre detaylı bulgular listesi
- Impact x Effort önceliklendirme tablosu
- Probability x Impact risk matrisi
- Backlog formatında eylem önerileri
- Refactoring roadmap
- Teknik borç listesi
- İyileştirme fırsatları
- Test, static analysis ve dependency review özeti
- Dead code / unused import / unreachable code özeti
- Referans materyaller ve kullanılan kaynaklar

Rapor profesyonel bir teknik doküman formatında, Markdown olarak, açık başlık yapısıyla ve gerektiğinde syntax highlighting içeren kod bloklarıyla sunulmalıdır. Kod örnekleri bağlama uygun, minimal, uygulanabilir ve test edilebilir nitelikte olmalıdır. Rapor hem insan tarafından okunabilir hem de ileride otomatik kalite süreçlerine bağlanabilecek kadar yapılandırılmış olmalıdır.

Repo-Özel Notlar

Bu proje lokal-first çalışan, Python backend ve React/Vite frontend içeren, transcription, viral analysis, video processing, subtitle rendering ve editor akışlarını bir arada barındıran bir üretim sistemidir. Denetim bu gerçeğe uygun yapılmalıdır.

Aşağıdaki kaynaklar öncelikli gerçek kaynaklar olarak kabul edilmelidir:
- `README.md`
- `docs/architecture/*`
- `docs/flows/*`
- `docs/pages/*`
- `pyproject.toml`
- `requirements.txt`
- `frontend/package.json`
- `.github/workflows/verify.yml`
- `scripts/verify.sh`

Mevcut raporlar ve analiz dosyaları yardımcı bağlam sağlayabilir; ancak bulgular yalnızca bunlara dayanarak kopyalanmamalı, güncel kod ve güncel doğrulama çıktılarıyla desteklenmelidir.

İnceleme boyunca amaç, projeyi geliştirmeye açık alanları dürüstçe ortaya koymak, hiçbir kod parçasını gereksiz risk altına atmadan, mevcut üretim davranışını koruyacak şekilde eyleme dönüştürülebilir teknik bir denetim çıktısı üretmektir.
