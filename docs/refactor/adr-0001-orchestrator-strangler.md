# ADR-0001: Orchestrator için Incremental Strangler Refactor

- Durum: Accepted
- Tarih: 2026-03-12
- Karar Sahibi: Backend Team

## Bağlam
`GodTierShortsCreator` içinde çok uzun methodlar (pipeline/manual/batch/reburn) bakım ve değişiklik riskini artırıyordu.

## Karar
- Dışa açık façade sınıfı korunacak.
- İç akışlar workflow sınıflarına taşınacak.
- Ortak teknik detaylar helper modüllere bölünecek:
  - subprocess/cancel -> `CommandRunner`
  - media yardımcıları -> `media_ops`
  - temp/progress yardımcıları -> `workflow_helpers`

## Sonuçlar
### Pozitif
- Modülerlik ve test edilebilirlik arttı.
- Akışların sorumluluk sınırları netleşti.
- Refactor adımları daha küçük ve geri alınabilir hale geldi.

### Negatif / Trade-off
- Dosya sayısı arttı.
- İlk geçişte import ve dependency haritası daha karmaşık görünebilir.

## Rollback Stratejisi
- Workflow delegasyon commit’i geri alındığında façade eski davranışa dönebilir.
- Dış API değişmediği için rollback etkisi sınırlı.

## Takip Aksiyonları
- Aynı pattern diğer monolitik modüllere uygulanacak.
- Guardrail testleri her modülde genişletilecek.
