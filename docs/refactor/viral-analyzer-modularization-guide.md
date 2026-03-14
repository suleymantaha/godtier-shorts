# Viral Analyzer Modüler Refactor Rehberi

## Amaç
- Uzun methodları küçük ve test edilebilir parçalara bölmek.
- LLM/fallback/parsing akışlarını ayrıştırıp bakım maliyetini düşürmek.
- Dış arayüzü (`ViralAnalyzer`) koruyarak güvenli geçiş yapmak.

## Uygulanan Mimari
- `viral_analyzer.py`: Facade + orkestrasyon
- `viral_analyzer_core.py`: Saf yardımcı fonksiyonlar
- `viral_llm_adapters.py`: Provider-adapter katmanı (OpenRouter / LM Studio)

## Parçalama Stratejisi
1. **Pure logic extraction**
- `build_fallback_segments`, `parse_llm_json_response`, `build_*_prompt` saf fonksiyonlara taşındı.

2. **Orchestration facade**
- `analyze_metadata` ve `analyze_transcript_segment` sadece akış sırası/yönlendirme yapıyor.

3. **Cross-cutting helpers**
- `_status_callback`, `_cancel_checker`, `_engine_label`, `_resolve_client`, `_persist_segments` ile tekrar azaltıldı.

## SOLID / DRY / KISS
- **SRP**: Prompt/parsing/fallback tek modülde, çağrı akışı ayrı modülde.
- **DIP**: LLM provider farkları adapter sınıfları arkasında izole.
- **DRY**: Cancel/status/fallback tekrarları helper metodlara alındı.
- **KISS**: Public API korunup iç ayrıştırma yapıldı.

## Adapter Pattern (Yeni)
- `OpenRouterAdapter`:
  - `extra_headers` ve opsiyonel `include_reasoning` body enjekte eder.
- `LMStudioAdapter`:
  - Aynı request sözleşmesini provider-özel ek opsiyonsuz kullanır.
- `create_adapter(engine, ...)`:
  - Engine'e göre doğru adapter instance üretir.

## Test Yazılabilirliği Artışı
- Saf fonksiyonlar bağımsız unit test için uygun hale geldi.
- Mevcut analyzer testleri kırılmadan geçti.
- Entegrasyon doğrulaması backend test paketi ile yapıldı.

## Örnek Refactor Şablonu
- Problemli blok: tek method içinde prompt+request+parse+fallback+persist.
- Refactored yapı:
  - `full_text = build_transcript_text(...)`
  - `prompt = build_metadata_prompt(...)`
  - `result = _call_llm(...)`
  - `result = _fallback_result(...)`

## Ekip Standardı Önerisi
- Method > 60 satırsa decomposition zorunlu.
- I/O ve saf logic aynı method içinde tutulmamalı.
- Refactor PR’ında parity kanıtı + rollback planı şart.
- Yeni abstraction için en az 1 test eklenmeli.

## Araçlar
- `pytest` (unit + integration)
- `py_compile` (hızlı sentaks kontrolü)
- ESLint/complexity yaklaşımı frontendde warning ile başlayıp kademeli strict

## Sonuç (Bu Refactor)
- `viral_analyzer.py`: 470 -> 329 satır
- Yardımcı logic: `viral_analyzer_core.py` içine ayrıldı
- Tüm backend testleri yeşil: `65 passed, 1 skipped`
