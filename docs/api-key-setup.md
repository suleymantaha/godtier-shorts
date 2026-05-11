# API Key ve .env Kurulum Rehberi

Bu rehber, projedeki `.env` dosyasında yer alan API key ve secret alanlarini son kullanici gozunden aciklar:

- Hangisi zorunlu?
- Nereden alinir?
- `.env` dosyasina ne yazilir?
- Hangi alan su an gercekten kullaniliyor?

Bu rehberde gercek key degeri yoktur. Repoda veya yerel makinede gercek key varsa bunlari dokumana kopyalamayin.

## En Kisa Ozet

Bu projeyi son kullanici olarak sorunsuz acmak icin en pratik yol su:

1. Clerk hesabi ac, uygulama olustur.
2. `VITE_CLERK_PUBLISHABLE_KEY`, `CLERK_ISSUER_URL`, `CLERK_AUDIENCE`, `VITE_CLERK_JWT_TEMPLATE` alanlarini doldur.
3. `SOCIAL_ENCRYPTION_SECRET` icin guclu bir rastgele secret uret.
4. AI icin iki yoldan birini sec:
   - Bulut LLM: `OPENROUTER_API_KEY`
   - Lokal LLM: `LMSTUDIO_HOST` ve tercihen `LM_STUDIO_API_KEY=lm-studio`
5. Sosyal medya paylasimi kullanacaksan paylasimli kullanimda global Postiz + global OAuth app kur ve kullanicinin baglantiyi uygulama icinden yapmasini sagla. Yalniz tek kullanicili lokal gelistirme icin `POSTIZ_API_KEY`, `POSTIZ_API_BASE_URL` ve `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1` kullan.

## Hangileri Gercekten Zorunlu?

### Zorunlu

| Degisken | Neden zorunlu? | Nereden gelir? |
|----------|----------------|----------------|
| `VITE_CLERK_PUBLISHABLE_KEY` | Frontend Clerk olmadan acilmaz. | Clerk Dashboard -> API Keys |
| `CLERK_ISSUER_URL` | Backend JWT dogrulamasi icin gerekli. | Clerk Dashboard -> API Keys / Frontend API URL |
| `CLERK_AUDIENCE` | Backend token `aud` kontrolu yapiyor. | Siz belirliyorsunuz |
| `VITE_CLERK_JWT_TEMPLATE` | Frontend bu template ile token uretiyor. | Siz belirliyorsunuz |
| `SOCIAL_ENCRYPTION_SECRET` | Backend acilista bu secret'i zorunlu kontrol ediyor. | Siz uretiyorsunuz |

### AI icin zorunlu ama secime bagli

Bu ikisinden biri yeterlidir:

- `OPENROUTER_API_KEY`
- `LMSTUDIO_HOST` (+ tercihen `LM_STUDIO_API_KEY`)

AI analizi hic calismayacaksa sistem fallback davranisa gecebilir, ama gercek kullanim icin bir AI secenegi tanimlamaniz tavsiye edilir.

### Opsiyonel

| Degisken | Durum |
|----------|-------|
| `POSTIZ_API_KEY` | Yalniz explicit dev fallback acik ise kullanilir; normal akista uygulama ici credential tercih edilir |
| `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK` | `POSTIZ_API_KEY` env fallback'ini yalniz tek kullanicili dev modunda acmak icin kullanilir |
| `POSTIZ_API_BASE_URL` | Postiz cloud/self-hosted kullaniyorsan gerekli |
| `SOCIAL_CONNECTION_MODE` | `managed` ise UI manuel API key istemez; `manual_api_key` ise dev fallback akisi acik kalir |
| `PUBLIC_APP_URL` | Buyuk videolarin URL import ile Postiz'e yuklenmesinde gerekli |
| `HF_TOKEN` | Cogu kurulumda opsiyonel |
| `API_BEARER_TOKENS` | Test/dev fallback, son kullanici icin tavsiye edilmez |
| `YOUTUBE_API_KEY` | Bu repoda aktif kullanim bulamadim; su an bos kalabilir |
| `LM_STUDIO_API_KEY` | Gercek vendor key degil; cogu durumda `lm-studio` yazmak yeterli |

## 1. Clerk Kurulumu

Bu proje icin en kritik entegrasyon Clerk'tir. Mevcut frontend kodu `VITE_CLERK_PUBLISHABLE_KEY` yoksa dogrudan hata vererek durur ve backend de `CLERK_ISSUER_URL` + `CLERK_AUDIENCE` bekler.

### 1.1 Clerk hesabi ve uygulama olustur

1. `https://dashboard.clerk.com` adresine gidin.
2. Yeni bir application olusturun.
3. `API Keys` sayfasina girin.
4. Asagidaki iki bilgiyi alin:
   - Publishable Key -> `VITE_CLERK_PUBLISHABLE_KEY`
   - Frontend API URL -> `CLERK_ISSUER_URL`

Not:

- Publishable Key genelde `pk_test_` veya `pk_live_` ile baslar.
- Development ortaminda Frontend API URL tipik olarak `https://<slug>.clerk.accounts.dev` formatindadir.
- Bu projede `CLERK_ISSUER_URL` alanina Frontend API URL yazilir.

### 1.2 JWT template olustur

1. Clerk Dashboard -> `JWT Templates`
2. `New template`
3. Template adini yazin. Ornek: `godtier-backend`
4. Claims alanina sunu girin:

```json
{
  "aud": "godtier-shorts-api",
  "roles": ["viewer"]
}
```

Buradaki mantik:

- `aud` degeri -> `.env` icindeki `CLERK_AUDIENCE` ile birebir ayni olmali
- template adi -> `.env` icindeki `VITE_CLERK_JWT_TEMPLATE` ile birebir ayni olmali
- `roles` bos olmamali

Rol ornekleri:

- `viewer`: sadece goruntuleme
- `editor`: transcript kaydetme, reburn, manuel isler
- `producer`: publish ve daha genis operasyonlar
- `admin`: tam yetki

### 1.3 `.env` icine ne yazacagim?

```dotenv
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxx
CLERK_ISSUER_URL=https://your-app.clerk.accounts.dev
CLERK_AUDIENCE=godtier-shorts-api
VITE_CLERK_JWT_TEMPLATE=godtier-backend
```

### 1.4 En basit anlatimla bu alanlar ne ise yarar?

- `VITE_CLERK_PUBLISHABLE_KEY`: frontend login ekranini acan public key
- `CLERK_ISSUER_URL`: backend token'in hangi Clerk instance'indan geldigini buradan anlar
- `CLERK_AUDIENCE`: bu token bu backend icin mi uretilmis, onu kontrol eder
- `VITE_CLERK_JWT_TEMPLATE`: frontend token isterken Clerk'te hangi template'i kullanacagini soyler

## 2. SOCIAL_ENCRYPTION_SECRET

Bu bir dis servis key'i degil. Uygulamanin kendi ic secret'idir.

Ne ise yarar?

- Kaydedilen sosyal medya credential'larini sifrelemek icin kullanilir
- Bu repo acilis sirasinda bu degeri zorunlu kontrol ediyor

En kolay uretim:

```bash
openssl rand -base64 32
```

Sonra `.env`:

```dotenv
SOCIAL_ENCRYPTION_SECRET=buraya_urettiginiz_degeri_yapin
```

Not:

- Bunu kaybederseniz daha once bu secret ile sifrelenmis bazi veriler cozulmeyebilir
- Production'da sabit tutun, sik degistirmeyin

## 3. AI Secimi: OpenRouter mi, LM Studio mu?

Son kullanici icin en kolay secim:

- Kolay ve hizli baslangic: OpenRouter
- Lokal ve bulutsuz kullanim: LM Studio

## 3A. OpenRouter API Key

### Nereden alinir?

1. `https://openrouter.ai`
2. Hesap acin
3. Dashboard / key settings sayfasindan yeni API key olusturun
4. Gerekirse kredi ekleyin

### `.env` ayari

```dotenv
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
```

### Ne ise yarar?

- Viral analiz servisinin cloud LLM ile calismasini saglar
- Bu projede backend OpenAI uyumlu istemciyi `https://openrouter.ai/api/v1` adresine baglar

### Son kullaniciya en basit anlatim

"Buluttan AI kullanacaksan OpenRouter hesabina gir, yeni bir key uret, `OPENROUTER_API_KEY` alanina yapistir."

## 3B. LM Studio

LM Studio tarafinda gercek bir cloud API key almazsiniz. Bu servis lokal calisir.

### Kurulum

1. `https://lmstudio.ai` adresinden uygulamayi indirin
2. Bir model indirin
3. `Developer` sekmesinden local server'i baslatin
4. Gerekirse `lms server start` komutunu kullanin

### `.env` ayari

```dotenv
LMSTUDIO_HOST=http://localhost:1234
LM_STUDIO_API_KEY=lm-studio
```

Not:

- Bu projedeki backend kodu `LM_STUDIO_API_KEY` bos ise zaten `lm-studio` fallback degeri kullaniyor
- Yani burada gercek bir vendor portalindan key kopyalamiyorsunuz

### Ne ise yarar?

- Viral analiz servisinin lokal LLM ile calismasini saglar
- Internet olmadan kullanmak isteyenler icin uygundur

### En basit anlatim

"LM Studio'yu kur, bir model indir, local server'i ac, `LMSTUDIO_HOST=http://localhost:1234` yaz. Istersen `LM_STUDIO_API_KEY=lm-studio` birak."

## 4. Postiz Kurulumu

Bu kisim sadece sosyal medya yayinlama ozelligini kullanacaksan gerekli.

### 4.0 Onerilen production modeli

Paylasimli/global kullanimda hedef model su olmalidir:

- Postiz operator tarafinda tek kez kurulur
- Google OAuth client operator tarafinda tek kez tanimlanir
- Uygulama `.env` tarafinda `SOCIAL_CONNECTION_MODE=managed` kullanilir
- `POSTIZ_API_KEY` son kullaniciya dagitilmaz
- Son kullanici uygulamada kendi hesabini baglar
- Kullanici tokenlari subject bazli saklanir

Detayli operasyon standardi:

- [postiz-global-oauth-standard.md](operations/postiz-global-oauth-standard.md)

### 4.1 Nereden alinir?

Postiz cloud veya self-hosted kullanabilirsiniz.

- Cloud base URL: `https://api.postiz.com/public/v1`
- Self-hosted base URL: kendi alan adiniz + `/public/v1` veya `/api/public/v1`

Managed OAuth2 app bilgileri alma adimi:

1. Postiz'e giris yapin
2. `Settings -> Developers -> OAuth Apps` (veya self-hosted panelde esdeger ekran)
3. `Client ID` ve `Client Secret` degerlerini alin
4. Callback URL'i `SOCIAL_OAUTH_CALLBACK_URL` ile birebir ayni tanimlayin

### 4.2 `.env` ayari

Managed OAuth2 (onerilen paylasimli/global model):

```dotenv
POSTIZ_API_BASE_URL=https://api.postiz.com/public/v1
SOCIAL_CONNECTION_MODE=managed
POSTIZ_OAUTH_CLIENT_ID=your_postiz_oauth_client_id
POSTIZ_OAUTH_CLIENT_SECRET=your_postiz_oauth_client_secret
SOCIAL_OAUTH_CALLBACK_URL=https://api.yourdomain.com/api/social/oauth/callback
SOCIAL_OAUTH_RETURN_URL=https://app.yourdomain.com
SOCIAL_OAUTH_STATE_TTL_SECONDS=600
PUBLIC_APP_URL=http://localhost:8000
```

Tek kullanicili lokal dev fallback (opsiyonel):

```dotenv
POSTIZ_API_BASE_URL=http://localhost:4007/api/public/v1
SOCIAL_CONNECTION_MODE=manual_api_key
POSTIZ_API_KEY=your_postiz_api_key
ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1
```

### 4.3 Bu alanlar ne ise yarar?

- `POSTIZ_OAUTH_CLIENT_ID` / `POSTIZ_OAUTH_CLIENT_SECRET`: OAuth authorization-code exchange icin kullanilir
- `SOCIAL_OAUTH_CALLBACK_URL`: Postiz callback'in donecegi backend endpoint URL'i
- `SOCIAL_OAUTH_RETURN_URL`: callback sonrasinda frontend'e donecek URL
- `SOCIAL_OAUTH_STATE_TTL_SECONDS`: signed OAuth state suresi (saniye)
- `POSTIZ_API_BASE_URL`: hangi Postiz sunucusuna gidecegini soyler
- `POSTIZ_API_KEY`: sadece `manual_api_key` modunda dev fallback icin
- `PUBLIC_APP_URL`: buyuk videolar dogrudan dosya olarak degil URL ile aktarilacaksa GodTier backend'in public adresi gerekir

### 4.4 Son kullaniciya en basit anlatim

"Postiz kullanacaksan operator bir kez OAuth app kurar. Sen uygulamada `Baglantiyi Postiz'de Ac` ile kendi hesabini baglarsin; API key girmen gerekmez."

### 4.5 Onemli not

`POSTIZ_API_KEY` env fallback'i varsayilan olarak kapali. Yalniz tek kullanicili lokal gelistirmede `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1` ile acilabilir. Cok kullanicili veya paylasilan ortamlarda Postiz credential'larini uygulama icinden subject bazli baglamak gerekir.

## 5. HF_TOKEN

Bu alan Hugging Face token'i icindir.

### Nereden alinir?

1. `https://huggingface.co/settings/tokens`
2. `New token`
3. Gerekliyse `read` veya `fine-grained` token olustur

### `.env` ayari

```dotenv
HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
```

### Gerekli mi?

Cogu kurulumda hayir. Bu repo icindeki aktif akista zorunlu degil. Gated veya ozel model erisimi gereken senaryolarda faydali olabilir.

## 6. YOUTUBE_API_KEY

Bu alan `.env` dosyasinda var ama repo icinde aktif kullanimini bulamadim.

### Pratik sonuc

- Su anki YouTube pipeline `yt-dlp` ile calisiyor
- Bu nedenle son kullanici kurulumunda `YOUTUBE_API_KEY` alanini bos birakabilirsiniz

### Ne zaman lazim olabilir?

Ileride YouTube Data API v3 ile metadata, arama, kota veya resmi API tabanli ozellik eklenirse kullanilabilir.

## 7. API_BEARER_TOKENS

Bu da bir dis servis API key'i degil; backend icin statik token fallback mekanizmasi.

Ornek:

```dotenv
API_BEARER_TOKENS=super_guclu_bir_token:admin,editor
```

Fakat bu proje son kullanici tarafinda Clerk ile tasarlandigi icin en basit ve dogru kurulum olarak bunu onermiyorum.

Ne zaman kullanilir?

- test
- lokal automation
- gecici backend dogrulama

## Hazir `.env` Ornekleri

### En kolay kurulum: Clerk + OpenRouter

```dotenv
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxx
CLERK_ISSUER_URL=https://your-app.clerk.accounts.dev
CLERK_AUDIENCE=godtier-shorts-api
VITE_CLERK_JWT_TEMPLATE=godtier-backend
SOCIAL_ENCRYPTION_SECRET=replace_with_a_strong_random_secret

OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx

LMSTUDIO_HOST=http://localhost:1234
LM_STUDIO_API_KEY=lm-studio

FRONTEND_URL=http://localhost:5173
API_HOST=0.0.0.0
API_PORT=8000
PUBLIC_APP_URL=http://localhost:8000
DEBUG=false
```

### Lokal AI kurulum: Clerk + LM Studio

```dotenv
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxx
CLERK_ISSUER_URL=https://your-app.clerk.accounts.dev
CLERK_AUDIENCE=godtier-shorts-api
VITE_CLERK_JWT_TEMPLATE=godtier-backend
SOCIAL_ENCRYPTION_SECRET=replace_with_a_strong_random_secret

LMSTUDIO_HOST=http://localhost:1234
LM_STUDIO_API_KEY=lm-studio

FRONTEND_URL=http://localhost:5173
API_HOST=0.0.0.0
API_PORT=8000
PUBLIC_APP_URL=http://localhost:8000
DEBUG=false
```

## Son Kontrol Listesi

1. `.env.example` dosyasini `.env` olarak kopyalayin
2. En azindan Clerk + `SOCIAL_ENCRYPTION_SECRET` alanlarini doldurun
3. AI icin OpenRouter veya LM Studio secin
4. Sosyal paylasim kullaniyorsaniz Postiz ayarlarini ekleyin
5. Uygulamayi baslatin
6. Login olun
7. Bir job baslatip AI analizinin geldiginin kontrolunu yapin

## SSS

### `VITE_CLERK_PUBLISHABLE_KEY` olmadan sistem acilir mi?

Hayir. Mevcut frontend bu key yoksa hata veriyor.

### `SOCIAL_ENCRYPTION_SECRET` kullanmiyorsam bos birakabilir miyim?

Hayir. Mevcut backend startup akisi bunu zorunlu kontrol ediyor.

### `LM_STUDIO_API_KEY` icin panelden key almam gerekiyor mu?

Hayir. LM Studio lokal server oldugu icin genelde `lm-studio` gibi bir deger yeterli.

### `YOUTUBE_API_KEY` zorunlu mu?

Hayir. Mevcut repo akisinda zorunlu degil.

## Resmi Kaynaklar

- Clerk environment variables: https://clerk.com/docs/guides/development/clerk-environment-variables
- Clerk JWT templates: https://clerk.com/docs/guides/sessions/jwt-templates
- OpenRouter API authentication: https://openrouter.ai/docs/api/reference/authentication
- Hugging Face user access tokens: https://huggingface.co/docs/hub/security-tokens
- LM Studio local server: https://lmstudio.ai/docs/developer/core/server
- LM Studio OpenAI compatibility: https://lmstudio.ai/docs/developer/openai-compat
- Postiz Public API: https://docs.postiz.com/public-api/introduction
- YouTube Data API credentials: https://developers.google.com/youtube/registering_an_application
