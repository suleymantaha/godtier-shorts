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

## 🚀 Sonuç ve Sistem Sağlığı (Güncel: 20 Ağustos 2026)

17 Ağustos oturumundaki tüm hatalar kök nedenleriyle çözülmüş ve
doğrulanmıştı. 20 Ağustos oturumunda `main`'e merge öncesi yapılan
doğrulama sırasında üç yeni, birbirinden bağımsız kök neden daha bulundu
ve ikisi (`backend/models/` gitignore çakışması, yarım commit edilmiş AI
durum rozeti özelliği) çözülüp doğrulandı. Üçüncüsü
(`.github/workflows/verify.yml` eksikliği) bilinçli olarak açık bırakıldı
ve ayrı bir iş olarak takip edilmeli.

**Güncel test durumu**: `pytest backend/tests` → 352 passed, 2 skipped,
2 failed (yalnızca madde 7'deki bilinen açık sorun). Frontend: `tsc -b`
temiz, `vitest run` → 57 dosya / 294 test passed, 4 skipped.
