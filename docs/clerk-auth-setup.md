# Clerk Authentication Setup Guide (GodTier Shorts)

Bu doküman, projedeki Clerk tabanlı kimlik doğrulama akışını sıfırdan kurmak, doğrulamak ve sorun gidermek için hazırlanmıştır.

## 1) Amaç ve Mimari

Bu projede güvenlik modeli:

- Tüm `GET/POST /api/*` endpoint’leri kimlik doğrulama ister.
- `/ws/progress` websocket bağlantısı token ister.
- Backend JWT doğrulamasında `issuer + audience + roles` kontrolü yapar (fail-closed).
- Clerk token alınamazsa veya claims eksikse istek reddedilir.

## 2) Ön Koşullar

- Clerk hesabı ve bir Clerk application/instance
- Projede backend + frontend kurulumu tamamlanmış olmalı
- `.env` dosyasını düzenleme erişimi

## 3) Clerk Dashboard Konfigürasyonu

## 3.1 JWT Template oluştur

Clerk Dashboard:

1. `https://dashboard.clerk.com` aç
2. Projeni seç
3. Sol menüden `JWT Templates` bölümüne gir
4. `New template` / `Create template` seç

Örnek template:

- Template Name: `godtier-backend`
- Claims:

```json
{
  "aud": "godtier-shorts-api",
  "roles": "{{user.public_metadata.roles}}"
}
```

Notlar:

- `aud` backend’deki `CLERK_AUDIENCE` ile birebir aynı olmalı.
- `roles` claim’i zorunlu. Boş veya eksik olursa backend token’ı reddeder.
- Bu repo için önerilen model:
  - yeni kullanıcılar: `["member"]`
  - proje sahibi hesabı: `["admin"]`

## 3.2 Hangi roller neye erişir?

Backend policy map’i `backend/api/security.py` içindedir. Özet:

- `member`: UI’daki normal akışların tamamı
- `admin`: aynı normal akışlar + yönetimsel işlemler
- ownership transfer endpoint’leri artık kullanılmıyor; kullanıcılar başka projeleri sahiplenemez

## 3.3 Otomatik Varsayılan Rol Atama

Yeni kullanıcıların Clerk Dashboard’dan tek tek metadata düzenlenmeden rol alması için backend webhook kullanılabilir.

Backend route:

```text
POST /api/clerk/webhooks
```

Gerekli backend env’leri:

```dotenv
CLERK_SECRET_KEY=sk_test_xxx
CLERK_WEBHOOK_SIGNING_SECRET=whsec_xxx
CLERK_DEFAULT_USER_ROLES=member
CLERK_ADMIN_EMAILS=suleymantahab@gmail.com
```

Davranış:

- `user.created` eventi geldiğinde yeni kullanıcıya `public_metadata.roles=["member"]` yazılır.
- `CLERK_ADMIN_EMAILS` içindeki email’ler otomatik olarak `["admin"]` alır.

Clerk Dashboard:

1. `Webhooks` -> `Add Endpoint`
2. Endpoint URL olarak deploy ettiğin backend adresini gir:
   `https://YOUR-DOMAIN/api/clerk/webhooks`
3. Event olarak `user.created` seç
4. Oluşan `Signing Secret` değerini `CLERK_WEBHOOK_SIGNING_SECRET` olarak backend’e yaz

Not:

- Lokal makinede Clerk cloud doğrudan `localhost`a erişemez. Bu akışı lokal test etmek için ngrok benzeri bir tunnel gerekir.
- Webhook kullanmayacaksan kullanıcı rollerini Clerk Dashboard -> Users -> Metadata -> Public metadata alanından manuel girebilirsin.

## 4) .env Ayarları

`.env` dosyasında aşağıdakiler tanımlı olmalı:

```dotenv
CLERK_ISSUER_URL=https://YOUR-INSTANCE.clerk.accounts.dev
CLERK_AUDIENCE=godtier-shorts-api
VITE_CLERK_JWT_TEMPLATE=godtier-backend
CLERK_JWKS_CACHE_TTL_SECONDS=3600
CLERK_JWKS_TIMEOUT_SECONDS=5
CLERK_SECRET_KEY=sk_test_xxx
CLERK_WEBHOOK_SIGNING_SECRET=whsec_xxx
CLERK_DEFAULT_USER_ROLES=member
CLERK_ADMIN_EMAILS=suleymantahab@gmail.com
```

Opsiyonel static fallback (automation/test için):

```dotenv
API_BEARER_TOKENS=<VERY_STRONG_RANDOM_TOKEN>:admin,editor
```

Önemli:

- Placeholder bırakma (`YOUR_...` gibi).
- Aynı key’i birden fazla kez yazma (son yazılan geçerli olur, debug zorlaşır).
- Gerçek secret/token’ları asla public paylaşma; sızdıysa hemen rotate et.

Offline ve degraded auth davranışı için opsiyonel frontend ayarları:

```dotenv
# local development icin raw JWT cache acik olabilir
VITE_ENABLE_OFFLINE_TOKEN_CACHE=true

# production icin false kalmasi daha guvenlidir
# VITE_ENABLE_OFFLINE_TOKEN_CACHE=false

VITE_AUTH_BOOTSTRAP_TIMEOUT_MS=6000
VITE_API_REQUEST_TIMEOUT_MS=15000
VITE_API_RETRY_COUNT=1
VITE_AUTH_TOKEN_EXPIRY_SKEW_MS=60000
VITE_OFFLINE_AUTH_SNAPSHOT_TTL_MS=43200000
```

Not:

- `VITE_ENABLE_OFFLINE_TOKEN_CACHE` local development icin pratik bir fallback'tir.
- Production'da varsayilan yaklasim token'i localStorage'a yazmamak ve sadece son dogrulanmis auth snapshot'i ile shell fallback acmaktir.
- Gercek offline API erisimi icin token'in suresi dolmamis olmali ve backend JWKS cache'i onceden dolmus olmalidir.
- Frontend korumali istekleri token `exp - 60s` penceresine girdiginde sessizce yenilemeyi dener.
- Sessiz yenileme basarisiz olursa shell acik kalir, ancak korumali HTTP/WebSocket trafigi pause edilir.

## 5) Uygulamayı Başlatma

```bash
conda activate godtier-shorts
pkill -f "python -m backend.main|vite" || true
./run.sh
```

## 6) Doğrulama Adımları

## 6.1 Backend auth çalışıyor mu?

Tokensuz:

```bash
curl -i http://localhost:8000/api/projects
```

Beklenen: `401 Unauthorized`

Static token ile:

```bash
curl -i -H "Authorization: Bearer <STATIC_TOKEN>" http://localhost:8000/api/projects
```

Beklenen: `200 OK`

## 6.2 Clerk token üretimi çalışıyor mu? (Browser Console)

Uygulamada login olduktan sonra:

```js
const t = await window.Clerk.session.getToken({ template: 'godtier-backend' });
const payload = JSON.parse(atob(t.split('.')[1]));
payload
```

Beklenen:

- `payload.aud === "godtier-shorts-api"`
- `payload.roles` dolu bir dizi

## 6.3 WebSocket doğrulaması

Login sonrası backend logunda sürekli `auth_failed` görmemen gerekir.
Token yoksa/yanlışsa `/ws/progress` reject olur (beklenen davranış).

## 7) Frontend’de API/Media Entegrasyonu

## 7.1 API çağrıları

Frontend `client.ts` her istekten once gecerli backend JWT'yi hazirlar ve sonra `Authorization: Bearer ...` header'ini uretir.

Normal akış:

1. Gecerli token varsa ayni token kullanilir.
2. Token bitmeye 60 saniye veya daha az kaldiysa Clerk'ten sessiz refresh yapilir.
3. API `401 token_expired` dondururse token bir kez zorla yenilenir ve istek bir kez replay edilir.
4. Refresh/replay toparlanamazsa kullanici signed out yapılmaz; korumali trafik pause edilir ve banner gosterilir.

## 7.2 Video kaynakları (kritik nokta)

`/api/projects/...` gibi korumalı video URL’leri `<video src>` ile doğrudan çalışmaz (header eklenemez).
Bu yüzden akış:

1. Token ile `fetch(videoUrl, { Authorization })`
2. `blob` üret
3. `URL.createObjectURL(blob)` ile `<video src=blob:...>`

Bu yaklaşım NotSupportedError/401-JSON-as-video sorununu engeller.

## 8) Sık Hatalar ve Çözümler

## Hata: `Auth config eksik: CLERK_AUDIENCE zorunlu`

Sebep:

- `CLERK_ISSUER_URL` var ama `CLERK_AUDIENCE` yok/boş.

Çözüm:

- `.env` içine doğru audience değerini ekle.
- Servisleri yeniden başlat.

## Hata: `No JWT template exists with name: godtier-backend`

Sebep:

- Dashboard’da template yok ya da adı farklı.

Çözüm:

- Clerk’te `godtier-backend` template oluştur veya `.env`de template adını mevcut olanla eşleştir.

## Hata: `401 Geçersiz kimlik doğrulama bilgisi`

Sebep:

- Token yanlış/expired
- `aud` eşleşmiyor
- `roles` claim eksik

Çözüm:

- Browser’dan token payload kontrol et (`aud`, `roles`).

## Hata: `401 token_expired`

Sebep:

- Onbellekteki ya da aktif Clerk token'inin suresi doldu.

Çözüm:

- Kullanıcıyı yeniden giris akısına yonlendir.
- JWT template lifetime ayarini ihtiyaca gore gozden gecir.

## Hata: `503 auth_provider_unavailable`

Sebep:

- Clerk JWKS endpoint'i erişilemiyor ve backend tarafinda kullanilabilir cache yok.

Çözüm:

- Internet baglantisini ve Clerk durumunu kontrol et.
- `CLERK_JWKS_CACHE_TTL_SECONDS` ile cache penceresini local/prod ihtiyacina gore ayarla.

## Hata: `Uncaught NotSupportedError: no supported sources`

Sebep:

- Video yerine 401/JSON response gelmesi.

Çözüm:

- Korumalı media URL’lerini auth’lu fetch + blob URL ile oynat.

## 9) Production Checklist

- Clerk production keys kullanılıyor.
- Tüm sızmış API key/token’lar rotate edildi.
- `.env` dosyası repo’ya commit edilmiyor.
- `CLERK_AUDIENCE` ve template claim `aud` birebir eşleşiyor.
- `roles` claim’i tüm tokenlarda mevcut.
- Offline fallback kullaniliyorsa frontend timeout/retry env'leri dogrulandi.
- CI test/lint/build yeşil.

## 10) Hızlı Özet

1. Clerk JWT template oluştur (`godtier-backend`)
2. `aud` + `roles` claimlerini ekle
3. `.env`’de issuer/audience/template eşle
4. Uygulamayı restart et
5. `curl` + browser console ile doğrula
6. Korumalı video için blob akışını kullan
