# Geri Dönüş (Rollback) Planı - Altyazı Sistemi Genişletme

**Tarih:** 2026-03-07  
**Amaç:** Implementasyon sırasında oluşabilecek hatalar için geri dönüş stratejileri

---

## 1. Değişiklik Özeti

### Yapılacak Değişiklikler

| Dosya                     | Değişiklik Türü                   | Risk Seviyesi |
| ------------------------- | --------------------------------- | ------------- |
| `subtitle_styles.py`      | Model genişletme + Yeni presetler | Orta          |
| `subtitle_renderer.py`    | Opsiyonel - gradient desteği      | Yüksek        |
| `test_subtitle_styles.py` | Yeni dosya                        | Düşük         |

---

## 2. Geri Dönüş Senaryoları

### Senaryo A: Model Uyumsuzluğu

**Belirti:**

- `StyleManager.get_preset()` çağrısı hata veriyor
- Pydantic validation hatası
- Mevcut presetler yüklenemiyor

**Çözüm (Adım Adım):**

```bash
# 1. Hangi satırda hata olduğunu kontrol et
cd /home/arch/godtier-shorts
python -c "from backend.services.subtitle_styles import StyleManager; print(StyleManager.list_presets())"

# 2. Eğer hata varsa, dosyayı orijinal haline getir
git checkout backend/services/subtitle_styles.py

# 3. Veya yedekten geri yükle
# cp backup/subtitle_styles.py backend/services/subtitle_styles.py

# 4. Test et
python -c "from backend.services.subtitle_styles import StyleManager; s=StyleManager.get_preset('HORMOZI'); print(s.name)"
```

### Senaryo B: Render Süreci Hatası

**Belirti:**

- ASS dosyası oluşturulamıyor
- FFmpeg burn-in hatası
- Altyazı videoda görünmüyor

**Çözüm:**

```bash
# 1. Log dosyasını kontrol et
tail -100 workspace/logs/renderer_*.log

# 2. subtitle_renderer.py'yi geri al
git checkout backend/services/subtitle_renderer.py

# 3. Mevcut testi çalıştır
python -m pytest backend/tests/ -v -k "subtitle" 2>/dev/null || echo "Test yok veya hata var"
```

### Senaryo C: Frontend Uyumsuzluğu

**Belirti:**

- Frontend build hatası
- TypeScript tip hataları
- UI'da stil seçimi çalışmıyor

**Çözüm:**

```bash
# 1. Frontend tip tanımlarını geri al
git checkout frontend/src/types/index.ts

# 2. JobForm'u geri al
git checkout frontend/src/components/JobForm.tsx

# 3. Frontend'i yeniden build et
cd frontend && npm run build
```

---

## 3. Hızlı Geri Dönüş Komutları

```bash
# Tüm değişiklikleri geri al (en hızlı)
git checkout -- backend/services/subtitle_styles.py
git checkout -- backend/services/subtitle_renderer.py

# Sadece subtitle_styles.py'yi geri al
git checkout backend/services/subtitle_styles.py

# Belirli bir commit'e geri dön
git revert HEAD --no-edit

# Yedek dosyadan geri yükle
cp backup/subtitle_styles.py backend/services/subtitle_styles.py
```

---

## 4. Doğrulama Kontrol Listesi (Geri Dönüş Sonrası)

- [ ] `StyleManager.list_presets()` çalışıyor
- [ ] `StyleManager.get_preset("HORMOZI")` doğru değerleri döndürüyor
- [ ] `SubtitleStyle()` varsayılan değerlerle oluşuyor
- [ ] Mevcut video işleme testleri başarılı
- [ ] FFmpeg burn-in komutu çalışıyor

---

## 5. İletişim Protokolü

| Durum              | Action                | Kim       |
| ------------------ | --------------------- | --------- |
| Hata tespit edildi | Rollback başlat       | Developer |
| Rollback başarılı  | Test çalıştır         | Developer |
| Hata devam ediyor  | Ekibi bilgilendir     | Developer |
| Sistem stabil      | İmplementasyona devam | Team Lead |

---

## 6. Önleyici Tedbirler

Implementasyon sırasında hata oluşmaması için:

1. **Her değişiklikten önce** mevcut hali yedekle
2. **Küçük adımlarla** ilerle (model → preset → test)
3. **Test odaklı** geliştir (her özellikten sonra test et)
4. **Loglama ile** takip et (artırımlı debug)

---

_Bu plan, implementasyon sırasında hata oluşması durumunda hızlıca geri dönmek için hazırlanmıştır._
