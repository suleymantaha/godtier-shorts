# Frontend

God-Tier Shorts frontend'i React 19, TypeScript, Vite ve Zustand ile yazildi. Bu paket; clip uretim akisi, subtitle editor, clip editor ve job izleme yuzeylerini backend API + WebSocket katmani ile baglar.

## Gereksinimler

- Node.js `22.x`
- npm `10.x`
- Backend API'nin calisiyor olmasi (`VITE_API_URL`)
- Clerk ile giris kullaniliyorsa `VITE_CLERK_PUBLISHABLE_KEY` ve `VITE_CLERK_JWT_TEMPLATE`

Repo referans surumleri kok dizinde tutulur:

- [`.nvmrc`](../.nvmrc)
- [`.python-version`](../.python-version)

## Ortam Degiskenleri

Frontend'in okudugu temel env alanlari [src/config.ts](./src/config.ts) ve [src/main.tsx](./src/main.tsx) icindedir:

- `VITE_API_URL`: backend taban URL'i. Production'da zorunludur.
- `VITE_API_KEY`: opsiyonel statik API key fallback.
- `VITE_CLERK_PUBLISHABLE_KEY`: Clerk publishable key.
- `VITE_CLERK_JWT_TEMPLATE`: Clerk token template adi.
- `VITE_MAX_UPLOAD_BYTES`: UI upload limiti gostergesi.
- `VITE_API_REQUEST_TIMEOUT_MS`, `VITE_API_RETRY_COUNT`: API timeout/retry ayarlari.
- `VITE_AUTH_BOOTSTRAP_TIMEOUT_MS`, `VITE_AUTH_TOKEN_EXPIRY_SKEW_MS`, `VITE_OFFLINE_AUTH_SNAPSHOT_TTL_MS`, `VITE_ENABLE_OFFLINE_TOKEN_CACHE`: auth bootstrap ve offline snapshot davranisi.

## Komutlar

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test -- --reporter=dot
npm run test:coverage -- --reporter=dot
npm run build
```

Kanonik kalite kapilari:

- `npm run verify`
- kok dizinden `bash scripts/verify.sh`
- coverage governance icin kok dizinden `bash scripts/check_coverage.sh`

## Yuzeyler

- `CONFIGURE`: job baslatma, stil secimi, clip galerisi ve operasyonel ayarlar
- `AUTO CUT`: video yukleme, aralik secimi, manuel veya AI tabanli clip uretimi
- `SUBTITLE EDIT`: proje/clip transcript duzenleme, kalite uyarilari, reburn ve kaydetme
- `Clip Editor`: kadraj, overlay, preview ve clip bazli duzeltmeler

UI akislari icin ust seviye referanslar:

- [Kok README](../README.md)
- [Auto Cut dokumani](../docs/pages/auto-cut/README.md)
- [Subtitle Edit dokumani](../docs/pages/subtitle-edit/README.md)
- [Clip Editor dokumani](../docs/pages/clip-editor/README.md)

## Dizin Rehberi

- [src/api](./src/api): HTTP istemcisi, request/response modellari, degrade fallback'ler
- [src/auth](./src/auth): Clerk bootstrap, token ve offline auth snapshot akislari
- [src/components](./src/components): sayfa ve feature bazli UI katmani
- [src/components/autoCutEditor](./src/components/autoCutEditor): auto-cut ekran state/controller/bolumleri
- [src/components/clipGallery](./src/components/clipGallery): clip listeleme ve secim akislari
- [src/components/jobForm](./src/components/jobForm): pipeline/job olusturma formu
- [src/components/subtitleEditor](./src/components/subtitleEditor): transcript editor, recovery ve reburn akislari
- [src/components/subtitlePreview](./src/components/subtitlePreview): preview model ve style parity yardimcilari
- [src/config](./src/config): runtime config ve subtitle style config
- [src/hooks](./src/hooks): WebSocket, media ve ortak hook'lar
- [src/store](./src/store): Zustand store'lari
- [src/test](./src/test): API, component, store ve unit testleri
- [src/types](./src/types): paylasilan API ve UI tipleri
- [src/utils](./src/utils): subtitle timing ve yardimci util katmani

## Test Stratejisi

- API istemcisi ve fallback modelleri: [src/test/api](./src/test/api)
- Auth ve websocket yardimcilari: [src/test/auth](./src/test/auth), [src/test/unit](./src/test/unit)
- Buyuk editor akislari: [src/test/components](./src/test/components)
- Store ve utility parity kontrolleri: [src/test/store](./src/test/store), [src/test/utils](./src/test/utils)

Ozellikle subtitle preview/render tarafinda frontend ile backend'in ayni karar yuzeyini korumasi icin parity fixture'lari vardir:

- [src/test/utils/subtitleTiming.parity.test.ts](./src/test/utils/subtitleTiming.parity.test.ts)
- [tests/fixtures/subtitle_parity_cases.json](../tests/fixtures/subtitle_parity_cases.json)

## Gelistirme Notlari

- Protected media URL'leri ve auth bootstrap akislari testlerde ozellikle hedefli fixture ile ele alinmali; aksi halde asenkron source-resolution gurbultusu uretebilir.
- `subtitleEditor`, `autoCutEditor` ve `clipGallery` feature'lari controller/state/sections desenini kullanir; yeni davranislar eklerken bu ayrimi koruyun.
- Subtitle style degisikligi yapiliyorsa frontend preview parity'sini ve backend render dogrulamasini birlikte kontrol edin.
- Repo genel dogrulama ve coverage notlari icin [scripts/README.md](../scripts/README.md) dosyasina bakin.
