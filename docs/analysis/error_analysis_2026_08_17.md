# 🛠️ Hata Analizi ve Kök Neden Raporu (17 Ağustos 2026)

Bu rapor, oturum boyunca karşılaşılan teknik aksaklıkları, kök nedenlerini, log kanıtlarını ve uygulanan kalıcı çözümleri belgelemektedir.

---

## 1. 🛑 Faster-Whisper CUDA DLL Eksikliği (`cublas64_12.dll`)

### 🔍 Belirti
Whisper modeli yüklenirken transkripsiyon süreci durakladı ve sistem CTranslate2 DLL yükleme hatası verdi (`cublas64_12.dll not found`).

### 🧬 Kök Neden
Sanal ortamda (`.venv`) PyTorch CUDA kütüphaneleri bulunmasına rağmen, `faster-whisper`'ın bağımlı olduğu NVIDIA CTranslate2 çalışma zamanı paketi (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, `nvidia-cuda-nvrtc-cu12`) eksikti.

### 🛠️ Yapılan Çözüm
1. Pip üzerinden ilgili NVIDIA CUDA cu12 paketleri sanal ortama kuruldu:
   - `nvidia-cublas-cu12`
   - `nvidia-cudnn-cu12`
   - `nvidia-cuda-nvrtc-cu12`
2. `backend/services/transcription.py` içerisinde çalışma zamanında DLL arama dizinleri güncellendi.
3. **Doğrulama**: `faster-whisper-large-v3` modeli GPU (FP16) üzerinde başarıyla transkripsiyonu tamamladı.

---

## 2. ⚡ Görev İptal İşleminde CORS / 500 Hatası (`CancelJobRequest` Şema Uyuşmazlığı)

### 🔍 Belirti
Arayüzden bir görev iptal edilmek istendiğinde konsolda şu hata görüldü:
`Access to fetch at 'http://localhost:8000/api/cancel-job/...' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present`

### 🧬 Kök Neden
CORS engeli gerçek bir güvenlik kuralı değil, arka planda meydana gelen 500 Unhandled Exception hatasının yan etkisidir. Ön yüzden gelen JSON isteğinde `confirmed` ve `source` alanları gönderilirken, `backend/models/schemas.py` içerisindeki `CancelJobRequest` Pydantic şemasında bu alanlar tanımlı değildi. FastAPI yanıt veremeden çöktüğü için varsayılan CORS başlıkları yanıta eklenemedi.

### 🛠️ Yapılan Çözüm
- `backend/models/schemas.py`:
  ```python
  class CancelJobRequest(BaseModel):
      confirmed: bool = True
      source: str | None = None
  ```
- **Doğrulama**: `pytest backend/tests/test_job_ownership.py` (4/4 test PASSED).

---

## 3. 🤖 OpenRouter Yer Tutucu Key Uyuşmazlığı & NVIDIA NIM Fallback

### 🔍 Belirti
Viral analiz adımı OpenRouter API çağrısında takılı kaldı veya hata döndürdü.

### 🧬 Kök Neden
`.env` dosyasında `OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...` şeklinde varsayılan bir yer tutucu (placeholder) anahtar tanımlıydı. `viral_analyzer.py` bu anahtarın geçerli olmadığını tespit edemeyip OpenRouter isteği atmaya çalışıyordu.

### 🛠️ Yapılan Çözüm
- `backend/services/viral_analyzer.py` içerisine `_is_usable_key()` fonksiyonu eklendi.
- Yer tutucu / geçersiz anahtar tespit edildiğinde sistem otomatik olarak `NVIDIA_API_KEY` (`nvidia/nemotron-3-ultra-550b-a55b`) motoruna yönlendirildi.
- **Doğrulama**: `pytest backend/tests/test_viral_analyzer_params.py` (14/14 test PASSED).

---

## 4. 🐢 Render Sürecinin Yavaşlaması & CPU Fallback

### 🔍 Belirti
Video oluşturma adımı beklenenden uzun sürdü (5-10 kat yavaşlama).

### 🧬 Kök Neden (Log Kanıtı)
Eşzamanlı yürütülen test işlemleri PyTorch CUDA bağlamını kilitlediği için FFmpeg `h264_nvenc` donanım kodlayıcısı anlık sürücü çakışması verdi:
```text
[h264_nvenc] CUDA error: driver mismatch
WARNING: NVENC burn basarisiz, encoder fallback karari veriliyor.
SUCCESS: Altyazi işlendi (CPU), video hazır.
```
Sistem işlem tamamlanabilsin diye koruma mekanizmasını devreye sokarak video altyazı gömmeyi CPU (`libx264`) moduna düşürdü.

### 🛠️ Yapılan Çözüm
- Test süreçleri tamamlandıktan sonra GPU donanım kodlayıcısı test edildi (`ffmpeg -c:v h264_nvenc`) ve **4.4x GPU hızıyla** çalıştığı doğrulandı.

---

## 5. 🔄 Sunucu Süreç Yenilenmesi & 404 / 500 İletişim Kopukluğu

### 🔍 Belirti
Yeni eklenen `/api/settings/ai-status` rotası için konsolda `404 Not Found` hatası alındı.

### 🧬 Kök Neden
Geliştirme sunucusu (`localhost:8000`), yeni rota ve şema değişiklikleri kodlanmadan önce başlatılan eski bir Python sürecinde (`PID 21608`) kalmıştı.

### 🛠️ Yapılan Çözüm
1. Port 8000 üzerindeki eski süreç sonlandırıldı.
2. Arka plan (FastAPI `uvicorn`) ve Ön yüz (Vite `npm run dev`) servisleri senkronize bir şekilde yeniden başlatıldı.

---

## Ek: 20 Ağustos 2026 Oturumu — Compose/Social Sekme Temizliği ve Main Merge

Bu ek, `claude/keen-gagarin-e9913d` dalında yapılan Social/Compose sekme
sadeleştirmesi sırasında ve `main`'e merge öncesi doğrulama sırasında ortaya
çıkan, bir kısmı bu oturumla ilgisiz ama kritik olan bulguları belgeler.

### 6. 🧨 `.gitignore`'daki çapasız `models/` kuralı `backend/models/`'ı da yutuyordu

#### 🔍 Belirti
`keen-gagarin-e9913d` worktree'sinde `tsc -b` temizdi ama backend'i import
etmeye çalışınca `ModuleNotFoundError: No module named 'backend.models'`
alındı. `backend/api/routes/account.py`, `editor.py`, `jobs.py` ve 7 test
dosyası bu modüle bağımlıydı.

#### 🧬 Kök Neden
`.gitignore` içinde büyük ML model ağırlıkları için eklenmiş `models/`
kuralı çapasızdı (kök dizine göre değil, her yerde eşleşiyordu). Bu yüzden
kök dizindeki gerçek hedefi (`/models/`) değil, `backend/models/`'ı
(tüm backend'in bağımlı olduğu Pydantic şema paketi, `schemas.py`) da
gizliyordu. `git log --all -- backend/models/schemas.py` boş döndü:
**bu dosya repo tarihinde hiçbir zaman commit edilmemiş**, sadece ana
worktree'nin diskinde tesadüfen duruyordu. Her yeni worktree/clone backend'i
çalıştıramıyordu.

#### 🛠️ Yapılan Çözüm
- `.gitignore`: `models/` → `/models/` (yalnızca kök dizini hedefler).
- `backend/models/__init__.py` ve `schemas.py` ilk kez commit edildi.
- **Doğrulama**: `python -c "from backend.api.server import app"` başarılı
  (13 route), `pytest backend/tests` 352 passed.

#### 📌 Ders
Gitignore kuralları eklenirken mutlaka kök-çapalı (`/path/`) yazılmalı;
çapasız bir klasör adı (`models/`, `cache/`, `data/` vb.) repo içinde aynı
isimli ama tamamen farklı amaçlı bir alt dizini sessizce yutabilir ve bu
hiçbir hata mesajı vermeden, yalnızca "neden bu dosya hiç repoda yok"
şeklinde çok geç fark edilir. Yeni bir ignore kuralı eklerken
`git check-ignore -v <şüpheli-yol>` ile çapraz kontrol faydalı olur.

### 7. 🧨 Aynı `.gitignore` `.github/workflows/`'ı da dışlıyordu (hâlâ açık)

#### 🔍 Belirti
`pytest backend/tests/test_toolchain_contract.py` içindeki iki test
`.github/workflows/verify.yml` dosyasını okumaya çalışıp
`FileNotFoundError` ile başarısız oluyor.

#### 🧬 Kök Neden
`.gitignore`'da `.github/workflows/` satırı vardı — CI workflow'ları asla
gitignore edilmemeli. Ancak bu durumda dosya yalnızca gizlenmiş değil,
hiçbir dalda/worktree'de gerçekten hiç var olmamış (`git log --all`
sonucu boş). Yani bu, `models/` vakasının aksine "yanlışlıkla gizlenmiş
mevcut dosya" değil, "hiç yazılmamış CI dosyası" durumu.

#### 🛠️ Durum
- `.gitignore`'dan `.github/workflows/` satırı kaldırıldı (gelecekte biri
  workflow eklerse artık gizlenmeyecek).
- **`.github/workflows/verify.yml` dosyasının kendisi hâlâ yazılmadı.**
  Bu, kapsamı bu oturumun dışına taşan ayrı bir iş — testin ne beklediğini
  (`ROOT / ".github" / "workflows" / "verify.yml"`) doğrulayıp gerçek CI
  pipeline'ı authoring etmek gerekiyor. `test_toolchain_contract.py`
  şu an bilinçli olarak "kırmızı" bırakıldı, sahte/boş bir CI dosyasıyla
  yeşile boyanmadı.

### 8. 🧨 Yarım commit edilmiş özellik: AI Motor Durum Rozeti main'i kırıyordu

#### 🔍 Belirti
`main`'in tip'i olan commit, `/api/settings/ai-status` için frontend
wiring'i (`api/client.ts`, `JobForm` kullanımı, i18n) ve backend router
kaydını (`server.py`'de `include_router`) içeriyordu ama üç yeni dosya
hiç `git add` edilmemişti: `backend/api/routes/settings.py`,
`backend/tests/test_settings_api.py`,
`frontend/src/components/ui/AiStatusBadge.tsx`. Sonuç: `tsc -b` frontend'de
`Cannot find module '../ui/AiStatusBadge'` veriyordu; backend tarafında da
`server.py` var olmayan bir route modülünü import etmeye çalışıyordu.

#### 🧬 Kök Neden
Özelliği geliştiren oturum, mevcut dosyalardaki değişiklikleri commit etmiş
ama yeni oluşturulan dosyaları unutmuş — klasik "git add eksik" hatası.
Dosyalar diskte (ana worktree'de) sağlam ve çalışır durumdaydı, sadece
git'e hiç girmemişti.

#### 🛠️ Yapılan Çözüm
Üç dosya incelendi (gizli anahtar/secret yok, `os.environ` üzerinden okuma,
`_mask_key` ile maskeleme, `require_policy("view_settings")` ile auth
kontrolü var), gerçek içerikleriyle commit edildi.
**Doğrulama**: `pytest backend/tests/test_settings_api.py` (2/2 passed),
`tsc -b` temiz, tam vitest suite yeşil (57 dosya / 294 test).

#### 📌 Ders
Yeni dosya oluşturan bir değişiklik commit edilmeden önce `git status`
mutlaka kontrol edilmeli — "modified" dosyalar `git add -u` ile
kolayca yakalanır ama "untracked" yeni dosyalar sessizce dışarıda
kalabilir ve commit "başarılı" görünse de eksik/kırık kalır. Bu ikinci kez
aynı hata kalıbıyla karşılaşıldı (bkz. madde 6) — commit öncesi
`git status --porcelain` çıktısında `??` satırı kalmadığından emin olmak
rutin bir adım olmalı.

---

## Ek: 20 Ağustos 2026 Oturumu (2) — Compose/Social Sekme Temizliği (`claude/compose-social-tabs-cleanup-88f810`, PR #3–#11)

Bu ek, madde 8'deki AI durum rozeti kurtarmasından hemen sonra aynı gün
içinde yürütülen ayrı bir oturumu belgeler: Social sekmesinin öncelik
sıralı bir panoya dönüştürülmesi, ölü `ShareComposerModal` yolunun
kaldırılması ve bu değişiklikler sırasında ortaya çıkan dört ayrı kök
nedenin bulunup düzeltilmesi. Tüm commit'ler zaten `main`'e merge edildi
(bu doküman güncellemesi ayrı, sonraki bir oturumda yazıldı).

### 9. 🐢 `SocialRepository.read_analytics` "platforms" verisini hiç önbelleğe almıyordu — Social sayfası her açılışta canlı Postiz senkronizasyonu bekliyordu

#### 🔍 Belirti
Social sekmesi her açıldığında (3 paralel istek: overview/accounts/posts +
platforms) gözle görülür şekilde yavaştı; sayfa yüklenmesi saniyeler
sürüyordu.

#### 🧬 Kök Neden
`backend/services/social/repository.py` içindeki `refresh_analytics`,
`overview`, `accounts` ve `posts` scope'larını `upsert_analytics_snapshot`
ile önbelleğe alıyordu ama `platforms` aggregate'ini hiç yazmıyordu.
`read_analytics` ise `platforms` alanını doğrudan
`self.refresh_analytics(subject=subject)["platforms"]` çağırarak
dolduruyordu — yani önbellek ısınmış olsa bile her okuma, canlı Postiz
provider senkronizasyonu dahil tam bir `refresh_analytics()` tetikliyordu.
Diğer üç alan önbellekten geliyor gibi görünse de fonksiyonun kendisi
zaten tetiklenmiş oluyordu, bu yüzden önbelleğin faydası sıfırdı.

#### 🛠️ Yapılan Çözüm
- `refresh_analytics` artık `platforms` scope'unu da
  `upsert_analytics_snapshot(subject, scope="platforms", ...)` ile yazıyor.
- `read_analytics`, dört scope'un (`overview`, `accounts`, `platforms`,
  `posts`) hepsi doluysa önbellekten okuyor; yalnızca biri eksikse
  `refresh_analytics`'e düşüyor.
- Regresyon testi eklendi (`test_social_read_analytics_uses_cache_without_forcing_refresh`,
  [backend/tests/test_social_connections.py](backend/tests/test_social_connections.py)):
  `refresh_analytics`'i sayaçla sarıp ısınmış önbellekte
  `read_analytics`'in onu **sıfır kez** çağırdığını doğruluyor.

#### 📌 Ders
Kısmi önbellekleme tehlikelidir: bir agregat fonksiyonun döndürdüğü
alanlardan biri bile önbellek yerine "kaynağı yeniden hesapla" yoluna
düşüyorsa, önbelleğin geri kalanı da fiilen işe yaramaz hale gelir —
çünkü o tek eksik alan zaten tüm pahalı işlemi tetikler. Yeni bir alan
eklerken "hangi scope'ların cache'e yazıldığı" listesi ile "hangi
scope'ların cache'ten okunduğu" listesi birbirine göre çapraz kontrol
edilmeli.

### 10. 🎭 Postiz manuel API-key kartı, gerçek bağlantı modu bilinmeden (hatta bazen hiç bilinmeden) gösteriliyordu

#### 🔍 Belirti
Compose sayfası her açıldığında, yönetilen (managed) bağlantı modundaki
kullanıcılar için bile kısa süreliğine ham API-key giriş kartı
görünüyordu. Daha ciddisi: henüz bir klip seçilmemişken bu görünüm
**kalıcı** olarak yanlış kalıyordu.

#### 🧬 Kök Neden
`useShareComposerController.ts` içindeki state, `connectionMode`'u
`SocialConnectionMode` tipinde ve varsayılan değeri `'manual_api_key'`
literal'i olarak tanımlıyordu. Gerçek değer yalnızca accounts API
yanıtı geldiğinde çözülüyordu; ama bu istek yalnızca bir klip ve proje
bilindiğinde tetikleniyordu. Klip seçilmeden önce gerçek değer hiç
gelmediği için varsayılan (`manual_api_key`) kalıcı olarak ekranda
kalıyordu.

#### 🛠️ Yapılan Çözüm
- `connectionMode` tipi `SocialConnectionMode | null` olarak genişletildi,
  varsayılan `null` yapıldı; kart artık yalnızca gerçek değer
  geldiğinde render ediliyor.
- Çözümleme mantığı (accounts API yanıtından) değiştirilmedi — sadece
  "bilinmiyor" durumu artık dürüstçe temsil ediliyor.

#### 📌 Ders
Bir API'den gelecek değer için yerel state'e "en olası" ya da "en güvenli
görünen" bir literal varsayılan atamak, veri gelene kadar geçen sürede
yanlış bilgi göstermekle aynı şeydir. Değer gelene kadar geçen pencere
her zaman sıfır olmayabilir (bu vakada bazı yollarda hiç kapanmıyordu) —
bu yüzden "henüz bilinmiyor" durumu `null`/`undefined` ile açıkça temsil
edilmeli, UI da bu duruma göre render'ı ertelemeli.

### 11. 📐 `aspect-ratio` + `max-height` ikilisi, genişlik `w-full` ile sabitlenmeden CSS'te öngörülemeyen şekilde daralıyordu

#### 🔍 Belirti
İlk düzeltme turunda (4819f32) 9:16 önizleme placeholder'larına
`max-h-[720px]` eklendi (gerçek `<video>` elementiyle aynı üst sınır).
Ancak bir sonraki manuel testte placeholder, panelin genişliğini
doldurmak yerine dar bir sütuna küçüldü ve yanında büyük boş bir alan
kaldı (30ada91). Aynı sınıftan ayrı bir bulgu olarak, klip galerisi
ızgarasındaki `ClipCard`'lar da (1abf049) az sayıda klip olduğunda
`minmax(228px, 1fr)` yüzünden orantısız şekilde büyüyordu.

#### 🧬 Kök Neden
`aspect-ratio` ve `max-height` birlikte tanımlı ama genişliği belirsiz
(`auto`) bir blok kutuda, tarayıcı 9:16 oranını tam olarak korumak için
genişliği daraltır — sütunu doldurmaz. Gerçek `<video>` elementi bu
tuzağa hiç düşmüyordu çünkü zaten `max-h-[720px]` ile birlikte
`w-full` de tanımlıydı; genişlik sabit olduğu için yükseklik tek başına
sınırlanabiliyordu. İlk düzeltme bu ikiliyi kopyalamadan yalnızca
`max-h-[720px]`'i taşıdı. Izgara vakasında ise kök neden farklı ama aynı
aileden: `1fr` üst sınırsız olduğu için boş sütun genişliği kartın
en-boy oranı üzerinden yüksekliğe orantılı olarak yansıyordu.

#### 🛠️ Yapılan Çözüm
- `SocialComposePage.tsx`'teki üç placeholder durumuna (`!clip`, `error`,
  `!resolvedSrc`) `max-h-[720px]` yanına `w-full` eklendi — gerçek
  `<video>` elementinin zaten kullandığı ikili aynen kopyalandı.
- `clipGallery/sections.tsx`'teki ızgara şablonu `minmax(228px, 1fr)`'dan
  `minmax(228px, 280px)`'e çekildi; sütunlar 228px'e kadar daralabiliyor
  ama artık üst sınırsız büyüyemiyor, fazla satır alanı boş kalıyor.

#### 📌 Ders
`aspect-ratio` kullanan bir kutuya `max-height` eklerken genişliğin de
(`w-full` veya eşdeğeri) açıkça sabitlenip sabitlenmediği kontrol
edilmeli — aksi halde tarayıcı oranı korumak için genişliği sessizce
küçültür ve bu, üst sınırı ekleyen commit'in kendisinde fark edilmeyip
bir sonraki manuel testte ayrı bir "bug" olarak ortaya çıkar. Aynı
en-boy-oranı-yüksekliği-sürüklüyor deseni `minmax(x, 1fr)` grid
sütunlarında da tekrar edebilir; ikisi de "sınırsız `1fr`/`auto`
boyut + sabit en-boy oranı" kombinasyonunun aynı ailesidir.

### 12. 🧱 Eşit olmayan yükseklikteki iki sütunlu dashboard grid'i `items-start` ile büyük bir boşluk bırakıyordu

#### 🔍 Belirti
Geniş ekranlarda, az aktivite olduğunda (Needs Attention/Week/Performance
boş) Social dashboard'ının ana sütunu Connections rayının çok altında
bitiyor, aradaki fark çıplak sayfa arkaplanı olarak görünüyordu.

#### 🧬 Kök Neden
İki sütunlu grid `items-start` kullanıyordu; her sütun kendi doğal
yüksekliğinde bitiyordu. Connections rayı veriden bağımsız neredeyse
sabit yükseklikteyken ana sütunun yüksekliği tamamen veriye bağlıydı —
ikisi arasındaki fark hizalanmıyordu.

#### 🛠️ Yapılan Çözüm
- Grid `items-start` → `items-stretch` yapıldı; her sütun artık
  `flex flex-col` ile sarmalandı.
- Her sütundaki son panel (solda Performance, sağda rayın kendi Panel'i)
  `flex-1`/`h-full` ile artan boşluğu kendi çerçevesinin içine alıyor,
  böylece iki sütunun kenarlıkları içerik miktarından bağımsız hep aynı
  çizgide bitiyor.

---

### 📋 Bu Oturumun Yan Ürünü: Ölü Kod ve Navigasyon Sadeleştirmesi (hata değil, kayıtlı iyileştirme)

- `ShareComposerModal.tsx` ve `shareComposer/sections.tsx` (627 satır) uygulamadan hiç
  çağrılmıyordu — `SocialComposePage` compose yüzeyini çoktan devralmıştı, modal
  yalnızca kendi testleriyle hayatta tutuluyordu. Modal'a özgü işlevsellik
  (manuel API-key bağlan/kes, taslak sıfırlama banner'ı, iş onay/iptal)
  `SocialComposePage`'e taşındıktan sonra ölü dosyalar, kullanılmayan controller
  alanları (`openSocialWorkspace`, `openSocialComposePage`, `connectUrl`,
  `handleManagedConnectOpen`, `ShareComposerController` tipi) ve yetim
  `shareComposer.*` i18n anahtarları (en/tr) silindi.
- Ayrı "Social Compose" üst-nav sekmesi ve config ekranındaki yinelenen
  "Open Composer"/"Open Workspace" butonları kaldırıldı; Social artık compose
  alt-görünümündeyken de vurgulu kalıyor, oraya yalnızca klip paylaşım
  aksiyonları ve dashboard'ın kendi compose linkinden ulaşılıyor.
- **Not**: `docs/analysis/repo-deep-scan-2026-03-17-appendix.md` ve
  `docs/analysis/TECHNICAL_AUDIT_APPENDIX_2026-03-13.md` hâlâ artık var
  olmayan `ShareComposerModal.tsx`/`shareComposer/sections.tsx`'e referans
  veriyor — bunlar tarihe damgalı (point-in-time) denetim raporları olduğu
  için bilinçli olarak güncellenmedi; canlı bir mimari doküman değiller.

---

## 🚀 Sonuç ve Sistem Sağlığı (Güncel: 20 Ağustos 2026, ikinci oturum)

17 Ağustos oturumundaki tüm hatalar kök nedenleriyle çözülmüş ve
doğrulanmıştı. 20 Ağustos'taki ilk oturumda `main`'e merge öncesi yapılan
doğrulama sırasında üç yeni, birbirinden bağımsız kök neden daha bulundu
ve ikisi (`backend/models/` gitignore çakışması, yarım commit edilmiş AI
durum rozeti özelliği) çözülüp doğrulandı; üçüncüsü
(`.github/workflows/verify.yml` eksikliği) hâlâ açık.

Aynı gün içindeki ikinci oturumda (Compose/Social sekme temizliği, PR
#3–#11), Social sekmesinin öncelik sıralı panoya dönüştürülmesi sırasında
dört yeni kök neden daha bulunup düzeltildi: bir backend önbellek
bug'ı (madde 9, gerçek performans etkisi olan), bir "veri gelmeden önce
yanlış varsayılan state" bug'ı (madde 10), CSS `aspect-ratio`/`max-height`/
`w-full` etkileşiminden doğan ve ilk düzeltmenin kendisinin yeni bir görsel
regresyona yol açtığı iki parçalı bir bug (madde 11) ve bir grid hizalama
bug'ı (madde 12). Ayrıca 627 satırlık ölü kod yolu ve yinelenen navigasyon
kaldırıldı.

**Doğrulama durumu**: Her commit kendi anlık testleriyle doğrulandı
(commit mesajlarında ayrıntılı). Bu doküman güncellemesinin yazıldığı
worktree'de backend için kurulu bir `venv` ve frontend için güncel bir
`node_modules` kurulumu bulunmadığından, tam test paketi bu oturumda
yeniden çalıştırılmadı — bu iki eksik kurulum, bu worktree'ye özgü bir
ortam farkı olup ayrı bir "hata" değildir. Bir sonraki geliştirme
oturumunda ana worktree'de `pytest backend/tests` ve
`cd frontend && npm run test` ile tam doğrulama yapılması önerilir.

**Bilinen açık sorun**: `.github/workflows/verify.yml` hâlâ yazılmadı
(bkz. madde 7); `pytest backend/tests/test_toolchain_contract.py` içindeki
ilgili iki test bilinçli olarak kırmızı bırakıldı.
