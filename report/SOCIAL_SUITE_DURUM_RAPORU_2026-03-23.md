# Social Suite Durum Raporu

Tarih: 2026-03-23

Bu checkpoint, uygulama içine native `Social` sekmesi ekleyen ve Postiz'i yalnız backend orchestration katmanı olarak kullanan ilk entegrasyon dilimini kapsar. Odak, tüm planı tek turda kusursuz kapatmak değil; bağlantı, cache, takvim, kuyruk, analytics ve composer yüzeylerini aynı ürün alanı altında çalışır hale getirip bunu test ve rapor kanıtı ile sabitlemektir.

## 1) SOCIAL-V1 domain ve shell checkpoint

Yapılan işler:
- `Social` ürün yüzeyi `connections`, `composer`, `queue`, `calendar`, `analytics` bölümlerine ayrıldı.
- Backend tarafında provider registry ve repository katmanı eklendi.
- Frontend shell `AppViewMode` içine `social` alındı.
- URL bootstrap için `?tab=social` desteği eklendi.
- Share composer içinden yeni social workspace sekmesine derin link açıldı.

Teknik kanıt:
- [backend/services/social/providers.py](/home/arch/godtier-shorts/backend/services/social/providers.py)
- [backend/services/social/repository.py](/home/arch/godtier-shorts/backend/services/social/repository.py)
- [frontend/src/app/helpers.ts](/home/arch/godtier-shorts/frontend/src/app/helpers.ts)
- [frontend/src/app/sections.tsx](/home/arch/godtier-shorts/frontend/src/app/sections.tsx)
- [frontend/src/components/SocialWorkspace.tsx](/home/arch/godtier-shorts/frontend/src/components/SocialWorkspace.tsx)

Riskler:
- `SocialWorkspace` tek dosyada büyük kaldı; sonraki checkpointte bileşenlere ayrılmalı.
- App shell tarafında yeni sekme davranışı stabil, fakat URL/query tab state’i test izolasyonunu etkiledi; testler buna göre güncellendi.

Doğrulama:
- `python -m py_compile backend/api/routes/social.py backend/services/social/service.py backend/services/social/store.py backend/services/social/repository.py backend/services/social/providers.py backend/services/social/postiz.py`
- `cd frontend && npm run build`

Sonuç:
- Social sekmesi shell içinde render oluyor ve yeni sekmede clip bağlamıyla açılabiliyor.

## 2) SOCIAL-V1 veri modeli ve backend temel checkpoint

Yapılan işler:
- `social_credentials` tablosu token kaynağı, validation/sync zamanları ve scope alanları ile genişletildi.
- `social_publish_jobs` tablosu delivery, publish sync ve analytics alanları ile genişletildi.
- Yeni tablolar eklendi:
  - `social_connection_sessions`
  - `social_account_cache`
  - `social_analytics_snapshots`
  - `social_dashboard_cache`
- Store katmanına connection session, account cache, analytics snapshot ve calendar reschedule yardımcıları eklendi.

Teknik kanıt:
- [backend/services/social/store.py](/home/arch/godtier-shorts/backend/services/social/store.py)

Riskler:
- Şema genişletmeleri SQLite için çalışır durumda, fakat migration disiplini hâlâ uygulama içi bootstrap tabanlı.
- `social_publish_jobs.timeline` mantığı mevcut alanlar üzerinden ilerliyor; ayrı event store henüz yok.

Doğrulama:
- `python -m py_compile backend/services/social/store.py`
- `pytest backend/tests/test_social_routes.py backend/tests/test_social_connections.py -q`

Sonuç:
- Connection/session/cache/analytics veri yüzeyi backend tarafında kalıcı hale geldi.

## 3) SOCIAL-V1 bağlantılar, takvim ve analytics API checkpoint

Yapılan işler:
- Yeni endpoint’ler eklendi:
  - `GET /api/social/providers`
  - `GET /api/social/connections`
  - `POST /api/social/connections/start`
  - `GET /api/social/connections/callback`
  - `POST /api/social/connections/sync`
  - `DELETE /api/social/connections/{account_id}`
  - `GET /api/social/queue`
  - `GET /api/social/calendar`
  - `PATCH /api/social/calendar/{job_id}`
  - `GET /api/social/analytics/overview`
  - `GET /api/social/analytics/accounts`
  - `GET /api/social/analytics/posts`
- Postiz client tarafına connect URL çözümü ve integration delete desteği eklendi.
- OAuth signed-state payload’ı platform ve connection session bilgisi taşıyacak şekilde genişletildi.
- `social.connection.start`, `social.connection.sync`, `social.connection.disconnect`, `social.calendar.update`, `social.analytics.refresh` log event’leri route seviyesinde işlendi.

Teknik kanıt:
- [backend/api/routes/social.py](/home/arch/godtier-shorts/backend/api/routes/social.py)
- [backend/services/social/postiz.py](/home/arch/godtier-shorts/backend/services/social/postiz.py)
- [backend/services/social/service.py](/home/arch/godtier-shorts/backend/services/social/service.py)
- [backend/tests/test_social_connections.py](/home/arch/godtier-shorts/backend/tests/test_social_connections.py)

Riskler:
- Dış provider connect callback’i tam native completion yerine `launch -> user return -> sync` modeliyle kapanıyor.
- Analytics aggregation şu aşamada snapshot + hesap/cache verisi ile çalışıyor; Postiz analytics parity daha sonra derinleştirilmeli.

Doğrulama:
- `pytest backend/tests/test_social_routes.py backend/tests/test_social_connections.py -q`

Sonuç:
- Bağlantı, cache sync, disconnect, queue, calendar ve analytics API yüzeyi canlı hale geldi.

## 4) SOCIAL-V1 frontend workspace ve share entegrasyonu checkpoint

Yapılan işler:
- Yeni `SocialWorkspace` bileşeni eklendi.
- Provider bağlantıları, hesap cache görünümü, composer, queue, calendar ve analytics panelleri tek ekranda toplandı.
- `socialApi` client yüzeyi genişletildi.
- Share composer içine `Open Social Workspace` aksiyonu eklendi.
- İngilizce ve Türkçe i18n kaynaklarına social workspace metinleri eklendi.
- App testleri ve SocialWorkspace testleri yeni navigation/query bootstrap davranışına göre güncellendi.

Teknik kanıt:
- [frontend/src/components/SocialWorkspace.tsx](/home/arch/godtier-shorts/frontend/src/components/SocialWorkspace.tsx)
- [frontend/src/api/client.ts](/home/arch/godtier-shorts/frontend/src/api/client.ts)
- [frontend/src/components/shareComposer/useShareComposerController.ts](/home/arch/godtier-shorts/frontend/src/components/shareComposer/useShareComposerController.ts)
- [frontend/src/components/shareComposer/sections.tsx](/home/arch/godtier-shorts/frontend/src/components/shareComposer/sections.tsx)
- [frontend/src/i18n/resources/en.ts](/home/arch/godtier-shorts/frontend/src/i18n/resources/en.ts)
- [frontend/src/i18n/resources/tr.ts](/home/arch/godtier-shorts/frontend/src/i18n/resources/tr.ts)
- [frontend/src/test/components/SocialWorkspace.test.tsx](/home/arch/godtier-shorts/frontend/src/test/components/SocialWorkspace.test.tsx)

Riskler:
- Composer hâlâ esas olarak clip-context publish için optimize edildi; serbest içerik akışı sonraki checkpointte genişletilmeli.
- `Postiz` referanslarının tamamı tüm eski ekranlardan henüz sökülmedi; yeni workspace ürün dili eklendi, fakat legacy share alanında bazı eski metinler korunuyor.

Doğrulama:
- `cd frontend && npm run test -- src/test/App.test.tsx src/test/components/SocialWorkspace.test.tsx`
- `cd frontend && npm run build`

Sonuç:
- Social workspace frontend’den kullanılabilir, bağlantı başlatabilir ve publish/takvim/analytics verisini gösterebilir durumda.

## Kalite Kapısı Özeti

Başarılı:
- `pytest backend/tests/test_social_routes.py backend/tests/test_social_connections.py -q`
- `cd frontend && npm run test -- src/test/App.test.tsx src/test/components/SocialWorkspace.test.tsx`
- `python -m py_compile backend/api/routes/social.py backend/services/social/service.py backend/services/social/store.py backend/services/social/repository.py backend/services/social/providers.py backend/services/social/postiz.py`
- `cd frontend && npm run build`

Başarısız:
- `bash scripts/verify.sh`

Verify kırılma nedeni:
- Repo genelindeki mevcut `eslint` hataları:
  - [frontend/src/components/HoloTerminal.tsx](/home/arch/godtier-shorts/frontend/src/components/HoloTerminal.tsx#L508)
  - [frontend/src/components/clipGallery/sections.tsx](/home/arch/godtier-shorts/frontend/src/components/clipGallery/sections.tsx#L695)
  - [frontend/src/components/subtitleEditor/playback.ts](/home/arch/godtier-shorts/frontend/src/components/subtitleEditor/playback.ts#L188)

Not:
- Bu verify kırıkları Social Suite değişikliğinin doğrudan açtığı yeni compile/test problemi değil; repo genelindeki mevcut lint kapısı bu dosyalarda hata veriyor.

## Açık Kalanlar

- Social workspace’i daha küçük bileşenlere bölmek.
- Free-form composer akışını clip-context zorunluluğundan çıkarmak.
- Legacy share/postiz metinlerini tam temizlemek.
- Analytics tarafında Postiz parity’yi daha ileri taşımak.
- Repo genelindeki lint hatalarını ayrı bir stabilizasyon checkpointi ile kapatıp `scripts/verify.sh` kapısını yeşile çevirmek.
