# AI Session Exit Protocol

Bu repo'da AI ile yapılan anlamlı her çalışma oturumu, kapanmadan önce aynı kısa protokolü izlemelidir.

## Zorunlu Checklist

1. `PROJECT_MEMORY.md` güncellenir.
   - Güncel hedef
   - Son durum
   - Geçerli kararlar
   - Açık işler ve sıradaki adımlar
   - Doğrulama durumu
   - Gerekli referanslar
   - Yeni oturum kaydı
2. İlgili test veya doğrulama komutu çalıştırılır.
   - Dar değişiklikte en küçük ilgili test
   - Geniş veya riskli değişiklikte daha kapsamlı doğrulama
   - Bloke ise sebep, çalıştırılamayan komut ve sonraki adım yazılır
3. Gerekli doküman güncellenir.
   - Davranış, kullanım, API, akış, ayar veya görünür UI değiştiyse ilgili doküman aynı turda düzeltilir
   - Doküman değişmediyse bunun nedeni `PROJECT_MEMORY.md` içine yazılır
4. Sonraki oturum için net başlangıç noktası bırakılır.
   - “Devam edilecek” gibi belirsiz not yerine açık görev ve bağlam yazılır

## Ne Zaman Uygulanır

- Kod değişiklikleri
- Config veya env değişiklikleri
- Script değişiklikleri
- Workflow veya API davranış değişiklikleri
- UI davranış değişiklikleri
- AI kuralları ve repo süreç değişiklikleri

## Standart Komutlar

- Geniş doğrulama: `bash scripts/verify.sh`
- Backend: `pytest backend/tests -q`
- Frontend lint: `bash -lc "cd frontend && npm run lint"`
- Frontend test: `bash -lc "cd frontend && npm run test -- --reporter=dot"`
- Frontend build: `bash -lc "cd frontend && npm run build"`

## İlgili Kaynaklar

- `PROJECT_MEMORY.md`
- `.agents/rules/godtier-shorts.mdc`
- `.agents/rules/godtier-shorts-progress.mdc`
- `.agents/rules/godtier-shorts-testing.mdc`
- `.agents/rules/godtier-shorts-docs.mdc`
