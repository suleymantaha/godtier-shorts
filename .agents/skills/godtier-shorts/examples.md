# God-Tier Shorts Örnek Kullanımlar

## Örnek 1 – Yeni Viral Kırpma Özelliği

- İstek: Kullanıcı, mevcut pipeline’a ek bir “Ultra Kısa (10–15 sn)” mod eklemek istiyor.
- Ajan davranışı:
  - Bu skill’i uygular.
  - `ViralAnalyzer` tarafında ek bir preset üretir (daha kısa süre hedefi).
  - `VideoProcessor` içinde 9:16 kırpma ve NVENC hattını korur, sadece süre ve segment seçim stratejisini ayarlar.

## Örnek 2 – Yeni Altyazı Stili

- İstek: `Ali Abdaal` tarzı sade ama kinetik bir stil eklenmesi.
- Ajan davranışı:
  - `SubtitleStyle` ve `StyleManager` içine yeni bir preset ekler.
  - `.ass` üretim mantığını değiştirmez; sadece renk/font/animasyon parametreleri üzerinden çalışır.

## Örnek 3 – UI’dan Ek Kontrol

- İstek: Kullanıcı UI’da kamera “smoothness” ve LLM motor seçimini değiştirmek istiyor.
- Ajan davranışı:
  - Zustand store’a yeni alanlar ekler (örn. `smoothness`, `engine`).
  - `startJob` isteğine bu alanları dahil eder.
  - Backend’de ilgili parametreleri `VideoProcessor` ve `ViralAnalyzer`’a geçirir.

