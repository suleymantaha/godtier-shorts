# Postiz Self-Hosted Kurulum ve Sorun Giderme Rehberi

Bu belge, **GodTier Shorts** projesinde yerel Postiz (`http://localhost:4007`) entegrasyonu sırasında karşılaşılan teknik sorunları, log kanıtları ile tespit edilen kök nedenleri ve uygulanan kalıcı çözümleri içermektedir.

---

## 🛠️ Karşılaşılan Sorunlar ve Çözümleri

### 1. Temporal OSS Arama Nitelikleri Çakışması (`3 INVALID_ARGUMENT`)
- **Belirti / Log:** Postiz backend başlatılırken crash oluyordu ve Nginx `502 Bad Gateway` veriyordu.
- **Kök Neden:** Temporal OSS veritabanında en fazla 3 adet `Text` türünde search attribute izni bulunur. `temporalio/auto-setup` varsayılan olarak `CustomTextField` ve `CustomStringField` eklediği için Postiz backend kendi arama niteliklerini eklerken limit aşılıyordu.
- **Çözüm:**
  ```bash
  docker exec postiz-temporal temporal operator search-attribute remove --address 172.22.0.4:7233 --name CustomTextField --name CustomStringField --yes
  ```

---

### 2. Eksik Storage Provider Tanımı (`Unsupported storage provider: undefined`)
- **Belirti / Log:** Postiz frontend arayüzünde React crash ekranı oluşuyordu: `Error: Unsupported storage provider: undefined`.
- **Kök Neden:** `docker-compose.yml` içinde medyanın yerel mi yoksa bulut mu saklanacağını belirten ortam değişkeni tanımsızdı.
- **Çözüm:** `docker/postiz/docker-compose.yml` ortam değişkenlerine eklendi:
  ```yaml
  STORAGE_PROVIDER: "local"
  UPLOAD_DIRECTORY: "/uploads"
  NEXT_PUBLIC_UPLOAD_DIRECTORY: "/uploads"
  ```

---

### 3. SSRF Güvenlik Koruması Engeli (`Error: Blocked IP`)
- **Belirti / Log:**
  ```text
  Error: Blocked IP
      at GetAddrInfoReqWrap.callback (ssrf.safe.dispatcher.ts:27:31)
      at YoutubeProvider.youtubeMediaSize
  ```
- **Kök Neden:** Postiz yerleşik SSRF koruması (`ssrf.safe.dispatcher.ts`), `localhost` / `127.0.0.1` adreslerinden medya indirilmesini varsayılan olarak engelliyordu.
- **Çözüm:** `docker-compose.yml` dosyasına yerel sistem izni verildi:
  ```yaml
  DISABLE_SSRF_PROTECTION: "true"
  ```

---

### 4. Konteyner İçi Port Uyuşmazlığı (`ECONNREFUSED 127.0.0.1:4007`)
- **Belirti / Log:**
  ```text
  Error: connect ECONNREFUSED 127.0.0.1:4007
      at TCPConnectWrap.afterConnect (node:net:1637:16)
      at YoutubeProvider.youtubeMediaSize
  ```
- **Kök Neden:** Konteyner içindeki Nginx varsayılan olarak yalnızca `5000` portunu dinliyordu. Dış ortam değişkeni `MAIN_URL: "http://localhost:4007"` olarak ayarlandığı için, Postiz orchestrator işçisi konteyner içerisinden `http://localhost:4007/uploads/...` adresine bağlamaya çalıştığında `127.0.0.1:4007` kapalı olduğundan istek `ECONNREFUSED` ile düşüyordu.
- **Çözüm:**
  - `docker/postiz/nginx.conf` dosyası güncellenerek Nginx'e `listen 4007;` dinleyicisi eklendi.
  - `docker-compose.yml` dosyasına `volumes: - ./nginx.conf:/etc/nginx/nginx.conf:ro` eklenerek kalıcı hale getirildi.

---

## 🚀 Konfigürasyon Özeti (`docker/postiz/docker-compose.yml`)

```yaml
  postiz:
    image: ghcr.io/gitroomhq/postiz-app:latest
    container_name: postiz
    restart: unless-stopped
    environment:
      MAIN_URL: "http://localhost:4007"
      NEXT_PUBLIC_BACKEND_URL: "http://localhost:4007/api"
      JWT_SECRET: "postiz-godtier-shorts-jwt-secret-key-9f8e"
      DATABASE_URL: "postgresql://postiz-user:postiz-password-secure@postiz-postgres:5432/postiz-db"
      REDIS_URL: "redis://postiz-redis:6379"
      FRONTEND_URL: "http://localhost:4007"
      BACKEND_INTERNAL_URL: "http://localhost:3000"
      TEMPORAL_ADDRESS: "temporal:7233"
      IS_LOCAL: "true"
      IS_GENERAL: "true"
      DISABLE_REGISTRATION: "false"
      RUN_CRON: "true"
      STORAGE_PROVIDER: "local"
      UPLOAD_DIRECTORY: "/uploads"
      NEXT_PUBLIC_UPLOAD_DIRECTORY: "/uploads"
      DISABLE_SSRF_PROTECTION: "true"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "127.0.0.1:4007:5000"
```
