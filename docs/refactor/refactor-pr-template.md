# Refactor PR Template

## 1. Kapsam
- Refactor edilen modül/dosyalar:
- Dış API/method imzası değişti mi?:
- Değişmediyse parity garantisi nasıl sağlandı?:

## 2. Behavior Parity Kanıtı
- Korunan akışlar:
- Eski/yeni davranış karşılaştırması:
- Örnek input/output veya response shape notları:

## 3. Risk Listesi
- Teknik riskler:
- Operasyonel riskler:
- Geri alma (rollback) planı:

## 4. Taşınan Kod Haritası
- Kaynak method/dosya -> hedef workflow/helper:
- Silinen tekrar kod blokları:
- Yeni abstraction noktaları:

## 5. Test Çıktısı (zorunlu)
- Backend: `pytest backend/tests`
- Frontend lint: `npm run lint`
- Frontend test: `npm run test -- --reporter=dot`
- Ek failure-mode testleri:

## 6. Dokümantasyon
- ADR-lite eklendi mi?:
- Data-flow diyagramı/failure-mode tablosu güncellendi mi?:

## 7. Merge Kontrol Listesi
- [ ] Public API kırılımı yok (veya açıkça duyuruldu)
- [ ] Parity testleri geçti
- [ ] Yeni guardrail/test eklendi
- [ ] Rollback adımı dokümante edildi
