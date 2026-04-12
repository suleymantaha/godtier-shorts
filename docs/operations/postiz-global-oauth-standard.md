# Postiz Global OAuth Standardi

Bu belge, paylasimli ve gercek kullanima acik kurulumlarda Postiz entegrasyonunun nasil yonetilecegini standartlastirir.

## Hedef Model

- Tek bir global Postiz kurulumu kullanilir.
- Tek bir global Google OAuth app/client kullanilir.
- Son kullanicidan `Postiz API Key` istenmez.
- Her kullanici kendi Google/YouTube hesabina bir kez izin verir.
- Kullaniciya ait baglanti tokenlari subject bazli saklanir.
- Uygulama ici sosyal publish her zaman kullanicinin kendi bagli hesabiyla calisir.

## Global Olanlar

Asagidaki ayarlar servis duzeyindedir ve global kalir:

- `POSTIZ_JWT_SECRET`
- `POSTIZ_DB_USER`
- `POSTIZ_DB_PASSWORD`
- `POSTIZ_DB_NAME`
- `TEMPORAL_DB_USER`
- `TEMPORAL_DB_PASSWORD`
- `POSTIZ_YOUTUBE_CLIENT_ID`
- `POSTIZ_YOUTUBE_CLIENT_SECRET`
- `POSTIZ_BIND_PORT`
- `POSTIZ_SPOTLIGHT_PORT`
- `POSTIZ_TEMPORAL_PORT`
- `POSTIZ_TEMPORAL_UI_PORT`
- `POSTIZ_API_BASE_URL`
- `SOCIAL_ENCRYPTION_SECRET`

Bu ayarlar operator tarafindan yonetilir. Son kullanici bunlari gormez veya degistirmez.

## Kullanici Bazli Olanlar

Asagidaki veri kullanici bazlidir:

- Postiz icindeki sosyal baglanti kaydi
- Google/YouTube consent sonucu olusan kullanici tokenlari
- Uygulama tarafinda subject bazli saklanan Postiz credential kaydi
- Secilebilir publish hedef hesaplari

Bu veriler her kullanici icin ayridir ve baska kullaniciya gosterilmemelidir.

## Kesin Kurallar

Paylasimli veya production benzeri ortamlarda:

- `POSTIZ_API_KEY` uygulama `.env` dosyasinda bulunmamalidir.
- `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK` kapali olmalidir.
- Kullanici baglantisi uygulama ici akistan yapilmalidir.
- Postiz UI `http://localhost:4007` uzerinden acilmalidir; `127.0.0.1` OAuth baslangicinda CORS sorunu uretebilir.

Sadece tek kullanicili lokal gelistirme icin:

- `POSTIZ_API_KEY`
- `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1`

gecici fallback olarak kullanilabilir.

## Timezone ve Windows Uyum Kurali

- Social scheduler payload'lari icin canonical IANA timezone adlari kullanin.
- Backend, `UTC`, `Etc/UTC`, `Etc/GMT`, ve `Europe/Istanbul` icin fallback cozumleme saglar.
- Bunun disindaki timezone'lar icin host tzdata/zoneinfo verisinin kurulu olmasi operasyon onkosuludur.
- Windows operator ortamlari scheduler rollout oncesi timezone parse davranisini dogrulamalidir.

## Operasyon Akisi

1. Operator global Postiz stack'i ayaga kaldirir.
2. Operator `.env.secure` icinde global JWT, DB ve OAuth client ayarlarini yonetir.
3. Uygulama `.env` icinde yalniz `POSTIZ_API_BASE_URL` ve `SOCIAL_ENCRYPTION_SECRET` tutulur.
4. Son kullanici uygulamaya normal auth ile girer.
5. Son kullanici Google/YouTube hesabini bir kez baglar.
6. Sonraki publish isleri otomatik olarak kendi bagli hesabi uzerinden ilerler.

Preflight:

- `python -m pytest backend/tests/test_social_routes.py backend/tests/test_social_connections.py backend/tests/test_social_postiz.py backend/tests/test_social_crypto.py`
- En az bir scheduled publish akisi `scheduled_at + timezone` ile staging ortaminda denenmelidir.

## Bakim Kurali

Bakim zamani operatorun mudahale ettigi tek yerler:

- `/home/arch/postiz-docker-compose/.env.secure`
- Google Cloud Console icindeki OAuth client ayarlari
- Gerekiyorsa Postiz/Temporal DB credential rotation

Son kullanici tarafinda API key dagitimi veya manuel secret girisi yapilmaz.
