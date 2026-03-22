# GodTier Shorts — Teknik Denetim Raporu

**Tarih:** 20 Mart 2026  
**Denetim tipi:** Repo-geneli üretim odaklı kod incelemesi  
**Ortam:** yerel Linux geliştirme ortamı, Python 3.13.11, Node 22.22.0, npm 10.9.4  
**Çıktı disiplini:** başlangıç snapshot'ı kod değiştirilmeden üretildi; aynı gün içindeki remediation faz kayıtları bu dokümanda ayrıca işaretlenmiştir

## Executive Summary

- Repo güçlü işlevsel kapsam ve iyi test yüzeyi taşıyor, ancak gün başındaki kalite kapısı yeşil değildi. 20 Mart 2026 başlangıç snapshot'ında `scripts/verify.sh` fail etti; frontend lint 3 hata ve 54 warning üretiyordu.
- Faz 1 remediation tamamlandı: frontend lint artık `0` error ve `53` warning veriyor; hedefli frontend test ve `backend/tests/test_social_routes.py` tekrar yeşile döndü.
- Faz planı kapandıktan sonraki ilk bakım checkpoint'inde `GTS-A06` warning azaltımı başlatıldı; frontend lint yükü `45` warning seviyesine indi ve hedefli UI testleri temiz kaldı.
- İkinci bakım checkpoint'inde auth client, websocket ve auto-cut controller/state kümesi sadeleştirildi; frontend lint yükü `37` warning seviyesine indi.
- Üçüncü bakım checkpoint'inde `autoCutEditor/sections.tsx` ve `clipGallery/*` kümesi sadeleştirildi; frontend lint yükü `34` warning seviyesine indi.
- Dördüncü bakım checkpoint'inde `editor/helpers.ts` ve `jobForm/*` kümesi sadeleştirildi; frontend lint yükü `32` warning seviyesine indi.
- Beşinci bakım checkpoint'inde `jobForm` kümesindeki son küçük warning kapatıldı ve `subtitleEditor` için ilk sadeleştirme dilimi atıldı; frontend lint yükü `30` warning seviyesine indi.
- Altıncı bakım checkpoint'inde `subtitleEditor/sections.tsx` içindeki preview/transcript wiring, render warning kuralları ve transcript durum kartları ayrıştırıldı; frontend lint yükü `26` warning seviyesine indi.
- Yedinci bakım checkpoint'inde `subtitleEditor/useSubtitleEditorController.ts` içindeki locked-clip dependency zinciri düzeltildi, transcript loader helper'lara bölündü ve editor action parametre yüzeyi daraltıldı; frontend lint yükü `19` warning seviyesine indi.
- Sekizinci bakım checkpoint'inde `subtitleEditor/useSubtitleEditorController.ts` içindeki job-tracking ve recovery kararları helper katmanına taşındı, controller build çıktısı state/handler bloklarına ayrıldı; frontend lint yükü `16` warning seviyesine indi.
- Dokuzuncu bakım checkpoint'inde `subtitlePreview/helpers.ts` ve `useWebSocket.helpers.ts` içindeki complexity adaları yardımcı çözücülere bölündü; frontend lint yükü `14` warning seviyesine indi.
- Onuncu bakım checkpoint'inde kalan `subtitleStyles`, `useJobStore`, test dosyası warning'leri ve frontend TypeScript build blocker'ları temizlendi; frontend lint yükü `0` warning seviyesine indi ve build yeniden geçti.
- En yüksek teknik riskler şu alanlarda toplandı: frontend auth/media effect yönetimi, sosyal publish approval akışı etrafındaki zaman-duyarlı test kararsızlığı, `backend.core` ile `backend.api` arasındaki katman tersine bağımlılıkları ve subtitle preview/render parity mantığının iki ayrı dilde kopya tutulması.
- Güvenlik tarafında olumlu kontroller mevcut: path sanitization, runtime config validation, role/policy enforcement ve temel response hardening başlıkları uygulanmış. İncelenen yüzeyde hemen istismar edilebilir kritik bir command injection veya path traversal açığı doğrulanmadı.
- Dokümantasyon ve önceki raporlar artık güvenilir tek kaynak olarak kullanılamıyor. Yerel link kontrolünde `54` kırık hedef bulundu; ayrıca eski denetim raporu mevcut test/lint durumuyla çelişiyor.

## Faz Takibi

| Faz | Durum | Tarih | Çıkış kriteri |
|---|---|---|---|
| Faz 1 — Verify hattını sinyal verir hale getirme | Tamamlandı | 20 Mart 2026 | `cd frontend && npm run lint` -> `0` error, `53` warning; `videoOverlay.helpers.test.ts` geçti; `pytest backend/tests/test_social_routes.py -q` -> `12 passed` |
| Faz 2 — Guardrail refactor sözleşmesini geri kazanma | Tamamlandı | 20 Mart 2026 | `backend/core/orchestrator.py` -> `345` satır; `backend/core/workflows_manual.py` -> `217` satır; guardrail testleri temiz |
| Faz 3 — Mimari ayrıştırma ve parity güvenceleme | Tamamlandı | 20 Mart 2026 | `backend.core` içinde doğrudan `backend.api` import'u yok; backend/frontend subtitle parity fixture testleri temiz |
| Faz 4 — Docs ve dependency sertleştirme | Tamamlandı | 20 Mart 2026 | markdown link checker temiz; `requirements.lock` üretildi; `pip-audit` temiz; `bash scripts/verify.sh` geçti |

## Scope And Methodology

İnceleme aşağıdaki yüzeyleri kapsadı:

- Backend: `backend/api`, `backend/core`, `backend/services`, `backend/models`
- Frontend: `frontend/src` altındaki API istemcisi, store, hook, component ve editor akışları
- Testler: `backend/tests`, `frontend/src/test`
- Operasyon ve kalite: `scripts/`, `.github/workflows/verify.yml`, `scripts/verify.sh`
- Manifest ve konfigürasyonlar: `requirements.txt`, `pyproject.toml`, `frontend/package.json`, `pyrightconfig.json`, `pyre.toml`
- Dokümantasyon ve mevcut raporlar: `README.md`, `docs/`, `report/`

Kullanılan doğrulama yöntemi:

1. Kod okuma ve satır-bazlı referans incelemesi
2. Yerelde tekrar üretilebilir komut çalıştırma
3. Repo-içi küçük statik analiz scriptleri ile import/coupling ve doküman drift kontrolü
4. Önceki raporların güncel durumla çapraz doğrulanması

## Repo Architecture Snapshot

| Yüzey | Dosya | Yaklaşık satır |
|---|---:|---:|
| `backend/api` | 42 | 4215 |
| `backend/core` | 55 | 4414 |
| `backend/services` | 55 | 6591 |
| `backend/models` | 6 | 235 |
| `frontend/src/components` | 44 | 10806 |
| `frontend/src/api` | 3 | 827 |
| `frontend/src/store` | 2 | 410 |
| `frontend/src/hooks` | 4 | 339 |
| `scripts` | 21 | 1206 |

Yoğunlaşan modüller:

- `backend/services/video_processor.py` `1857` satır
- `backend/core/workflow_helpers.py` `1341` satır
- `backend/api/routes/clips.py` `1191` satır
- `backend/api/routes/editor.py` `927` satır
- `backend/services/subtitle_renderer.py` `852` satır
- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` `1295` satır
- `frontend/src/components/subtitleEditor/sections.tsx` `1130` satır
- `frontend/src/components/editor/useEditorController.ts` `777` satır
- `frontend/src/api/client.ts` `685` satır

Backend katman bağımlılık özeti:

| Kaynak | Hedef | İthalat sayısı |
|---|---|---:|
| `backend.api` | `backend.core` | 17 |
| `backend.api` | `backend.services` | 16 |
| `backend.core` | `backend.api` | 3 |
| `backend.core` | `backend.services` | 25 |
| `backend.services` | `backend.core` | 7 |

Mutual import tespiti:

- `backend.core.workflow_helpers` `<->` `backend.core.workflows_manual`

## Detailed Findings

### AUD-001 — Frontend kalite kapısı React effect desenleri nedeniyle kırık

- **Durum:** `Tamamlandı (Faz 1, 20 Mart 2026)`
- **Severity:** `high`
- **Reproducibility:** `confirmed`
- **Alan:** frontend, kalite kapısı, runtime davranışı
- **Kanıt:** `frontend/src/auth/useResilientAuth.ts:65-79`, `frontend/src/components/HoloTerminal.tsx:114-118`, `frontend/src/components/ui/protectedMedia.ts:14-29`
- **Kanıt komutu:** `bash scripts/verify.sh` ve `cd frontend && npm run lint`
- **Detay:** ESLint, `react-hooks/set-state-in-effect` kuralı nedeniyle üç yerde hard error veriyor. Kod aynı render döngüsünde state resetlediği için hem CI kırılıyor hem de React 19 altında gereksiz cascading render riski oluşuyor.
- **Kök neden:** Effect’ler veri türetmek veya senkron reset yapmak için kullanılmış; olay-tetikli akış ya da türetilmiş state yerine doğrudan `setState()` çağrısı yapılmış.
- **Operasyonel etki:** `verify` job daha lint aşamasında duruyor; bu yüzden backend test kırıkları ve sonraki kalite sinyalleri tek koşuda görünmüyor. Runtime’da auth ve media yüzeylerinde gereksiz rerender ve geçici UI sıçramaları üretme riski var.
- **Önerilen çözüm:** signed-out/direct-source durumlarını türetilmiş state ve cleanup ile çöz; effect içinde sadece dış sistem senkronizasyonu ve abonelik bırak.
- **Minimal iyileştirme örneği:**

```tsx
const signedOut = isLoaded && !isSignedIn;

useEffect(() => {
  if (signedOut && isOnline) {
    clearAuthSnapshot();
  }
}, [signedOut, isOnline]);

useEffect(() => {
  if (!signedOut) {
    return;
  }
  setApiToken(null);
  resetProtectedRequests();
}, [signedOut, resetProtectedRequests]);
```

- **Remediation özeti (20 Mart 2026):** signed-out ve direct-source davranışı türetilmiş state'e çekildi; `HoloTerminal` expand modal görünürlüğü effect reset yerine türetilmiş `isExpanded` durumuna alındı.
- **Remediation kanıtı:** `cd frontend && npm run lint` -> `0` error, `53` warning.
- **Alternatifler:** reducer ile auth/media state makinesi kurmak; `useMemo` ile türetilmiş null state üretmek; component sınırını bölüp reset davranışını parent seviyesine taşımak.

### AUD-002 — Sosyal publish approval testi takvim ilerledikçe bozuluyor

- **Durum:** `Tamamlandı (Faz 1, 20 Mart 2026)`
- **Severity:** `high`
- **Reproducibility:** `confirmed`
- **Alan:** backend test güvenilirliği, sosyal scheduling
- **Kanıt:** `backend/tests/test_social_routes.py:590-619`, `backend/api/routes/social.py:438-448`, `backend/services/social/store.py:420-423`
- **Kanıt komutu:** `pytest backend/tests -q`
- **Detay:** Test, `scheduled_at` alanını sabit olarak `2026-03-16T03:02` gönderiyor. 20 Mart 2026 tarihinde bu tarih artık geçmişte kaldığı için approval sonrası job “future scheduled” sayılmıyor ve route `scheduled` yerine `approved` döndürüyor. Test bu yüzden kırılıyor.
- **Kök neden:** Zaman-duyarlı davranış, mutlak ve sabit bir tarih ile test edilmiş; test saati ilerlediğinde davranış değişiyor.
- **Operasyonel etki:** Backend test suite sürekli kırık kalır; gerçek sosyal scheduling regresyonlarını maskeleyebilir ve CI güvenilirliğini düşürür.
- **Önerilen çözüm:** Testte göreli gelecek zaman üret; gerekiyorsa zamanı dondur (`freezegun` benzeri) veya clock abstraction kullan.
- **Minimal iyileştirme örneği:**

```python
from datetime import datetime, timedelta, timezone

scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
```

- **Remediation özeti (20 Mart 2026):** approval testi sabit geçmiş tarih yerine göreli gelecek zaman kullanacak şekilde güncellendi.
- **Remediation kanıtı:** `pytest backend/tests/test_social_routes.py -q` -> `12 passed`.
- **Alternatifler:** `approve_publish_job` için injected clock kullanmak; test fixture’da `parse_iso` etrafında frozen-time patch uygulamak.

### AUD-003 — `backend.core` katmanı `backend.api` internallerine bağlanmış durumda

- **Durum:** `Tamamlandı (Faz 3, 20 Mart 2026)`
- **Severity:** `high`
- **Reproducibility:** `confirmed`
- **Alan:** mimari, bağımlılık yönetimi, modülerlik
- **Kanıt:** `backend/core/workflow_helpers.py:149-150`, `backend/core/workflow_helpers.py:574-576`, `backend/core/workflow_helpers.py:1074-1079`, `backend/core/workflows_manual.py:17-24`
- **Destek kanıtı:** repo-içi import grafiği özetinde `backend.core -> backend.api` bağımlılığı ve `workflow_helpers <-> workflows_manual` mutual import çifti doğrulandı.
- **Detay:** Core helper katmanı clip cache invalidation ve websocket broadcast için doğrudan route ve websocket manager import ediyor. Aynı dosya `workflows_manual` import ederek tekrar core içinde döngü kuruyor. Bu, “core is framework-agnostic” sınırını fiilen ortadan kaldırıyor.
- **Kök neden:** Altyapı entegrasyonları için interface/port tanımlamak yerine route ve singleton manager’lar doğrudan helper fonksiyonlarının içine gömülmüş.
- **Operasyonel etki:** Script/CLI kullanımında API runtime olmadan core akışlarını çalıştırmak zorlaşıyor; test izolasyonu pahalılaşıyor; refactor sırasında shot-gun surgery riski büyüyor.
- **Önerilen çözüm:** event yayınlama ve cache invalidation için port/protocol arayüzü tanımla; `OrchestratorContext` üzerinden enjekte et; route katmanında concrete adapter bağla.
- **Minimal iyileştirme örneği:**

```python
class ClipEventPublisher(Protocol):
    def clip_ready(self, *, project_id: str, clip_name: str, job_id: str | None) -> None: ...

class CacheInvalidator(Protocol):
    def invalidate(self, reason: str) -> None: ...
```

- **Remediation özeti (20 Mart 2026):** clip-ready ve clips-cache invalidation davranışı `ClipEventPort` arayüzüne taşındı; API-backed adapter route katmanında enjekte edilir hale geldi.
- **Remediation kanıtı:** `rg -n "from backend\\.api|backend\\.api\\." backend/core` -> sonuç yok; `pytest backend/tests/test_clip_ready_routing.py backend/tests/test_route_imports_smoke.py -q` -> `2 passed`.
- **Alternatifler:** domain event queue; noop default adapter; websocket/cache logic’ini `backend.infrastructure` benzeri ayrı katmana taşıma.

### AUD-004 — Subtitle preview ve final render mantığı iki ayrı kod tabanında kopya tutuluyor

- **Durum:** `Tamamlandı (Faz 3, 20 Mart 2026)`
- **Severity:** `high`
- **Reproducibility:** `likely`
- **Alan:** kritik alt sistem, frontend-backend parity
- **Kanıt:** `frontend/src/utils/subtitleTiming.ts:61-149`, `frontend/src/utils/subtitleTiming.ts:292-303`, `backend/services/subtitle_renderer.py:294-345`, `backend/services/subtitle_renderer.py:415-556`, `backend/services/subtitle_renderer.py:660-666`
- **Detay:** Subtitle chunking, line-break, overflow ve chunk-end köprüleme mantığı hem TypeScript hem Python tarafında ayrı ayrı yaşıyor. Sabitler de iki tarafta manuel kopya (`SMALL_GAP_BRIDGE_THRESHOLD`, split wrap/overflow eşikleri, font clamp kuralları). Bu tasarım preview ile final burn davranışını zamanla drift etmeye çok açık.
- **Kök neden:** Ortak golden fixtures veya parity contract testi yerine iki bağımsız implementasyon büyütülmüş.
- **Operasyonel etki:** Kullanıcı preview’da gördüğü line break/font clamp/aktif kelime davranışını final render’da birebir alamayabilir; özellikle reburn, subtitle editor ve overlay yüzeylerinde güven kaybı oluşur.
- **Önerilen çözüm:** ortak fixture tabanlı parity test paketi kur; aynı transcript/style/layout girdisini hem frontend planner hem backend renderer planning çıktısı üzerinde doğrula.
- **Minimal iyileştirme örneği:**

```json
{
  "layout": "split",
  "transcript": [{"start": 1.0, "end": 2.0, "text": "Hello there", "words": [...]}],
  "expected": {"lineBreakAfter": 0, "overflowStrategy": "split_line_break"}
}
```

- **Remediation özeti (20 Mart 2026):** frontend ve backend için ortak `tests/fixtures/subtitle_parity_cases.json` golden fixture seti eklendi; her iki taraf da aynı beklenen overflow/line-break/font-clamp davranışına karşı test ediliyor.
- **Remediation kanıtı:** `pytest backend/tests/test_subtitle_parity_contract.py -q` -> `1 passed`; `cd frontend && npm run test -- src/test/utils/subtitleTiming.parity.test.ts --reporter=dot` -> `3 passed`.
- **Alternatifler:** backend plan çıktısını frontend’e taşıyan tek kaynaklı planlama; build-time generated constants; parity snapshot suite.

### AUD-005 — Python bağımlılıkları tekrarlanabilir değil, audit araçları aktif değil

- **Durum:** `Tamamlandı (Faz 4, 20 Mart 2026)`
- **Severity:** `medium`
- **Reproducibility:** `confirmed`
- **Alan:** dependency management, supply-chain, CI
- **Kanıt:** `requirements.txt:5-40`, `frontend/package.json:6-57`, `pyrightconfig.json:1-15`, `pyre.toml:1-2`, `scripts/README.md:7-16`
- **Kanıt komutu:** `pyright --version`, `pyre --version`, `pip-audit`, `deptry`, `vulture`, `radon`, `madge`, `ts-prune`, `knip` aramaları; hepsi bu ortamda eksik.
- **Detay:** Python tarafında tüm ana paketler alt sınır (`>=`) ile bırakılmış ve lockfile yok. Frontend tarafında `package-lock.json` mevcut, fakat Python için eşdeğer çözüm yok. Ayrıca repo’da tip ve dependency kalite yapılandırmaları var, ancak araçların CLI’ları ortamda kurulu olmadığı için aktif kalite kapısı oluşturmuyorlar.
- **Kök neden:** Python toolchain için deterministik çözümleme ve güvenlik tarama akışı ürünleştirilmemiş.
- **Operasyonel etki:** Aynı commit farklı makinelerde farklı dependency setleriyle kurulabilir; hata üretimi ve medya stack davranışı sürüklenebilir; CI ile lokal arasında “works on my machine” farkı oluşur.
- **Önerilen çözüm:** `pip-tools`, `uv`, `poetry` veya benzeri ile kilitlenmiş çözümleme üret; `pip-audit` ve en az bir dead-code/dependency aracı CI’ye bağla.
- **Minimal iyileştirme örneği:**

```bash
uv pip compile requirements.txt -o requirements.lock
python -m pip install -r requirements.lock
```

- **Remediation özeti (20 Mart 2026):** `requirements.lock` eklendi; lock üretimi için `scripts/generate_requirements_lock.py` ve `scripts/update_requirements_lock.sh`, audit için `scripts/audit_python_deps.sh` tanımlandı. Audit bulguları üzerinden `PyJWT>=2.12.0` ve `cryptography>=46.0.5` alt sınırları yükseltildi.
- **Remediation kanıtı:** `bash scripts/update_requirements_lock.sh` -> `Wrote requirements.lock`; `bash scripts/audit_python_deps.sh` -> `No known vulnerabilities found`.
- **Alternatifler:** `requirements.in` + `pip-compile`; `uv.lock`; Docker image içinde pinlenmiş wheel cache.

### AUD-006 — Dokümantasyon ve eski denetim raporları güncel gerçeklikle drift etmiş

- **Durum:** `Tamamlandı (Faz 4, 20 Mart 2026)`
- **Severity:** `medium`
- **Reproducibility:** `confirmed`
- **Alan:** documentation, knowledge transfer
- **Kanıt:** `docs/pages/clip-editor/README.md:59-61`, `docs/pages/auto-cut/README.md:48-50`, `docs/pages/subtitle-edit/README.md:49-51`, `docs/pages/config/README.md:36-38`, `docs/operations/manual-cut/README.md:65-67`, `docs/operations/reburn/README.md:51-53`, `docs/operations/youtube-pipeline/README.md:45-48`, `report/TEKNIK_DENETIM_RAPORU_2026-03-12.md:22-29`
- **Kanıt komutu:** repo-içi local markdown link validator; `54` kırık hedef bulundu.
- **Detay:** Alt klasör README’ler yanlış relative path kullanıyor. Ayrıca 12 Mart 2026 tarihli eski denetim raporu frontend lint/testlerin geçtiğini ve `npm audit` sonuçlarını temiz gösteriyor; bu bilgi 20 Mart 2026 itibarıyla yanlış.
- **Kök neden:** Alt dokümanlar refactor sonrası yeniden bağlanmamış; raporlar “append-only” yaşamış ama yeniden doğrulama yapılmamış.
- **Operasyonel etki:** Onboarding ve incident triage sırasında ekip yanlış komut, yanlış dosya ve yanlış kalite beklentisiyle hareket edebilir.
- **Önerilen çözüm:** docs link checker’ı CI’ye ekle; eski raporları “historical snapshot” olarak etiketle; güncel raporları tarih ve commit ile ilişkilendir.
- **Minimal iyileştirme örneği:**

```md
- [Manual Cut](../../operations/manual-cut/README.md)
- [Reburn](../../operations/reburn/README.md)
- [Video Processor](../../logic/video-processor/README.md)
```

- **Remediation özeti (20 Mart 2026):** repo içine `scripts/check_markdown_links.py` eklendi; docs altındaki kırık relative linkler düzeltildi; eski denetim raporları historical snapshot olarak etiketlendi.
- **Remediation kanıtı:** `python scripts/check_markdown_links.py docs README.md` -> `Markdown links ok: 49 files checked`; `bash scripts/verify.sh` -> `all checks passed`.
- **Alternatifler:** tek girişli docs IA; link rewrite script’i; report index’e “freshness verified on YYYY-MM-DD” alanı eklemek.

### AUD-007 — Orchestrator ve workflow modülleri guardrail bütçelerini aşıyor

- **Durum:** `Tamamlandı (Faz 2, 20 Mart 2026)`
- **Severity:** `medium`
- **Reproducibility:** `confirmed`
- **Alan:** bakım kolaylığı, mimari evrim
- **Kanıt:** `backend/tests/test_orchestrator_refactor_guardrails.py:8-17`, `backend/tests/test_orchestrator_refactor_guardrails.py:33-46`, `backend/tests/test_workflows_refactor_guardrails.py:9-28`, `backend/core/orchestrator.py` toplam `366` satır, `backend/core/workflows_manual.py` toplam `233` satır
- **Kanıt komutu:** `pytest backend/tests -q`
- **Detay:** Repo zaten bu dosyalar için satır bütçesi koymuş; mevcut implementasyon bu bütçeleri kırıyor. Bu yalnız estetik bir problem değil; repo’nun kendi mimari hedefiyle çelişen somut teknik borç.
- **Kök neden:** Yeni özellikler eklenirken facade/workflow decomposition kuralı korunmamış.
- **Operasyonel etki:** Her yeni feature fix’i zaten gerilen modülleri daha da büyütür; review ve test izolasyonu pahalılaşır.
- **Önerilen çözüm:** orchestration facade’ı yalnız koordinasyon katmanına indir; medya, metadata, publish ve recovery sorumluluklarını ayrı helper/strategy katmanlarına ayır.
- **Minimal iyileştirme örneği:**

```python
class ManualClipRenderService:
    async def render(self, request: ManualClipRequest) -> str:
        ...

class GodTierShortsCreator:
    async def run_manual_clip_async(...):
        return await self.manual_clip_service.render(...)
```

- **Remediation özeti (20 Mart 2026):** facade delegasyon satırları inceltildi; manual/reburn workflow dosyalarında JSON yazımı ve render payload kullanımı sadeleştirilerek guardrail bütçeleri içine dönüldü.
- **Remediation kanıtı:** `pytest backend/tests/test_orchestrator_refactor_guardrails.py -q` -> `2 passed`; `pytest backend/tests/test_workflows_refactor_guardrails.py -q` -> `3 passed`; `pytest backend/tests/test_route_imports_smoke.py -q` -> `1 passed`.
- **Alternatifler:** workflow command objects; richer context objects; vertical slice decomposition.

### AUD-008 — Frontend helper testi artık geçerli olmayan subtitle aktiflik beklentisini koruyor

- **Severity:** `low`
- **Reproducibility:** `confirmed`
- **Alan:** test kalitesi, subtitle preview
- **Kanıt:** `frontend/src/test/components/videoOverlay.helpers.test.ts:24-35`, `frontend/src/utils/subtitleTiming.ts:97-107`, `frontend/src/utils/subtitleTiming.ts:292-303`
- **Kanıt komutu:** `cd frontend && npm run test -- --reporter=dot`
- **Detay:** Test, `currentTime=1.95` için `activeWordIndex` değerinin `null` dönmesini bekliyor. Ancak planner, chunk’i son kelimenin bittiği anda kapatıyor; bu yüzden helper artık `null` state döndürüyor ve optional chaining sonucu `undefined` geliyor.
- **Kök neden:** Test contract’ı, mevcut subtitle timing planner davranışı ile birlikte güncellenmemiş.
- **Operasyonel etki:** Subtitle preview üzerinde gerçekten bozulmuş parity vakaları ile stale-test kırıkları birbirine karışıyor.
- **Önerilen çözüm:** Testi güncel planner kontratına hizala veya istenen davranış değişecekse planner ve renderer parity fixtures ile birlikte değiştir.
- **Minimal iyileştirme örneği:**

```ts
expect(findCurrentSubtitleState(transcript, 1.95)).toBeNull();
```

- **Alternatifler:** sözleşmeyi `activeWordIndex: null` olacak şekilde değiştirmek; preview davranışını segment sonuna uzatmak.

## Impact x Effort Prioritization

| ID | Etki | Efor | Öncelik |
|---|---|---|---|
| AUD-001 | Yüksek | Düşük-Orta | P0 |
| AUD-002 | Yüksek | Düşük | P0 |
| AUD-003 | Yüksek | Orta-Yüksek | P1 |
| AUD-004 | Yüksek | Orta | P1 |
| AUD-005 | Orta-Yüksek | Orta | P1 |
| AUD-006 | Orta | Düşük-Orta | P1 |
| AUD-007 | Orta | Orta | P2 |
| AUD-008 | Düşük | Düşük | P2 |

## Probability x Impact Risk Matrix

| Olasılık \\ Etki | Düşük | Orta | Yüksek |
|---|---|---|---|
| Yüksek | AUD-008 | AUD-006, AUD-007 | AUD-001, AUD-002 |
| Orta |  | AUD-005 | AUD-003, AUD-004 |
| Düşük |  |  |  |

## Backlog Formatında Eylem Önerileri

| Backlog ID | Eylem | Hedef yüzey | Kabul kriteri |
|---|---|---|---|
| BKL-001 | React effect lint blocker’larını kaldır | auth, media, holo terminal | `npm run lint` error vermesin |
| BKL-002 | Tarih-bağımlı sosyal scheduling testlerini relative time ile düzelt | backend social tests | `pytest backend/tests -q` bu senaryoda takvimden bağımsız geçsin |
| BKL-003 | Core event/cache bağımlılıklarını interface arkasına al | `backend/core` | `backend.core -> backend.api` importları sıfırlansın |
| BKL-004 | Subtitle parity golden fixtures kur | renderer + preview | aynı fixture için frontend/backend plan çıktıları karşılaştırılsın |
| BKL-005 | Python dependency locking ve audit araçlarını ürünleştir | backend toolchain | lockfile + en az bir audit job CI’de çalışsın |
| BKL-006 | Docs link checker ve report freshness policy ekle | docs, report, CI | local markdown link check CI’de yeşil olsun |

## Refactoring Roadmap

### 0-7 gün

- AUD-001, AUD-002, AUD-008 kapat
- `verify` pipeline’ını tek koşuda gerçek sinyal verecek hale getir
- kırık doküman linklerini düzelt

### 1-2 sprint

- AUD-003 için event/cache adapter katmanı çıkar
- AUD-004 için shared parity fixture paketi oluştur
- Python dependency locking ve audit araçlarını CI’ye bağla

### 3+ sprint

- büyük workflow/controller modüllerini dikey dilimlere böl
- render metadata, recovery ve publish akışları için daha ince-grained service boundary oluştur

## Teknik Borç Listesi

- Backend orchestration ve frontend editor/subtitle editor controller’ları aşırı büyümüş durumda.
- Repo’da mimari guardrail testleri var, fakat uygulama bunları artık ihlal ediyor.
- Preview/render parity mantığı iki dilde kopya.
- Python toolchain deterministik değil.
- Operasyon dokümantasyonu alt seviyede link drift yaşamış.

## İyileştirme Fırsatları

- `verify.sh` için fail-fast yerine sonunda özet veren çoklu hata toplama modu eklenebilir.
- Subtitle parity fixture’ları render benchmark script’leriyle birleştirilebilir.
- Docs link checker ve report freshness metadata’sı `verify.yml` içine alınabilir.
- Type-check toolchain repo’da konfigüre ama pasif; CLI kurulumu ve gating ile yüksek kaldıraç sağlanır.

## Faz Sonrası İlerleme Notu

- **Durum:** `GTS-A06` aktif remediation'a alındı; frontend lint warning yükü `53`ten `45`e indirildi.
- **Kapsam:** `useResilientAuth`, `HoloTerminal`, `SubtitlePreview`, `VideoOverlay`, `useAutoCutEditorState` ve `subtitleTiming` testleri küçük responsibility extraction ile sadeleştirildi.
- **Kanıt komutları:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/HoloTerminal.test.tsx src/test/components/SubtitlePreview.test.tsx src/test/components/VideoOverlay.test.tsx src/test/utils/subtitleTiming.test.ts src/test/utils/subtitleTiming.parity.test.ts --reporter=dot`
- **Sonuç:** `0` error, `45` warning ve `43 passed`.
- **İkinci checkpoint:** `frontend/src/api/client.ts`, `frontend/src/hooks/useWebSocket.ts`, `frontend/src/components/autoCutEditor/useAutoCutEditorController.ts` ve `frontend/src/components/autoCutEditor/useAutoCutEditorState.ts` warning kümeleri sadeleştirildi.
- **İkinci checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/api/client.test.ts src/test/unit/useWebSocket.test.tsx src/test/components/AutoCutEditor.flow.test.tsx --reporter=dot`
- **İkinci checkpoint sonucu:** `0` error, `37` warning ve `20 passed`.
- **Üçüncü checkpoint:** `frontend/src/components/autoCutEditor/sections.tsx`, `frontend/src/components/clipGallery/sections.tsx` ve `frontend/src/components/clipGallery/useClipGalleryController.ts` sadeleştirildi.
- **Üçüncü checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/ClipGallery.test.tsx src/test/components/AutoCutEditor.flow.test.tsx --reporter=dot`
- **Üçüncü checkpoint sonucu:** `0` error, `34` warning ve `16 passed`.
- **Dördüncü checkpoint:** `frontend/src/components/editor/helpers.ts`, `frontend/src/components/jobForm/sections.tsx` ve `frontend/src/components/jobForm/useJobFormController.ts` sadeleştirildi.
- **Dördüncü checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/editor.helpers.test.ts src/test/components/JobForm.submission.test.tsx src/test/components/JobForm.preferences.test.tsx src/test/components/JobForm.accessibility.test.tsx --reporter=dot`
- **Dördüncü checkpoint sonucu:** `0` error, `32` warning ve `19 passed`.
- **Beşinci checkpoint:** `frontend/src/components/jobForm/useJobFormController.ts` içindeki kalan küçük warning kapatıldı; ayrıca `frontend/src/components/subtitleEditor/sections.tsx` içinde ilk sadeleştirme dilimi atıldı.
- **Beşinci checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/editor.helpers.test.ts src/test/components/JobForm.submission.test.tsx src/test/components/JobForm.preferences.test.tsx src/test/components/JobForm.accessibility.test.tsx src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
- **Beşinci checkpoint sonucu:** `0` error, `30` warning ve `36 passed`.
- **Altıncı checkpoint:** `frontend/src/components/subtitleEditor/sections.tsx` içinde preview/transcript prop wiring kısaltıldı, render warning kuralları veri odaklı hale getirildi ve transcript durum kartları ayrı state çözümleyicisine taşındı.
- **Altıncı checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
- **Altıncı checkpoint sonucu:** `0` error, `26` warning ve `17 passed`.
- **Yedinci checkpoint:** `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde `selection` dependency kullanımı stabilize edildi, transcript loader yardımcı fonksiyonlara bölündü ve editor action/text updater wiring'i daraltıldı.
- **Yedinci checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
- **Yedinci checkpoint sonucu:** `0` error, `19` warning ve `17 passed`.
- **Sekizinci checkpoint:** `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` içinde job-tracking flag çözümleyicileri, recovery eligibility helper'ları ve controller state/handler builder'ları ayrıştırıldı.
- **Sekizinci checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/SubtitleEditor.project.test.tsx src/test/components/SubtitleEditor.auth.test.tsx src/test/components/SubtitleEditor.clip.test.tsx --reporter=dot`
- **Sekizinci checkpoint sonucu:** `0` error, `16` warning ve `17 passed`.
- **Dokuzuncu checkpoint:** `frontend/src/components/subtitlePreview/helpers.ts` içinde preview model üretimi ayrıştırıldı; `frontend/src/hooks/useWebSocket.helpers.ts` içinde parse/validation/source çözümleme akışları ayrı helper'lara bölündü.
- **Dokuzuncu checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- src/test/components/subtitlePreview.helpers.test.ts src/test/unit/useWebSocket.helpers.test.ts --reporter=dot`
- **Dokuzuncu checkpoint sonucu:** `0` error, `14` warning ve `10 passed`.
- **Onuncu checkpoint:** `frontend/src/config/subtitleStyles.ts`, `frontend/src/store/useJobStore.ts`, `frontend/src/api/client.ts`, `frontend/src/auth/useResilientAuth.ts`, `frontend/src/components/HoloTerminal.tsx`, `frontend/src/components/SubtitlePreview.tsx`, `frontend/src/components/VideoOverlay.tsx`, `frontend/src/hooks/useWebSocket.ts` ve kalan büyük test dosyaları lint/type-budget altında yeniden düzenlendi.
- **Onuncu checkpoint kanıtı:** `cd frontend && npm run lint`; `cd frontend && npm run test -- --reporter=dot`; `cd frontend && npm run build`
- **Onuncu checkpoint sonucu:** frontend lint temiz, `232 passed`, production build başarılı.
- **On birinci checkpoint:** `frontend/src/test/components/ClipGallery.test.tsx` içinde arka planda otomatik akan fake-timer davranışı kaldırıldı ve auth-blocked senaryosu lokal fake timer ile sınırlandı; böylece `act(...)` console-noise temizlendi. Aynı turda `scripts/test_subtitle_styles.py`, `README.md` ve `docs/refactor/workflow-failure-modes.md` aktif terminolojiyi `faster-whisper` etrafında tekilleştirecek şekilde güncellendi.
- **On birinci checkpoint kanıtı:** `cd frontend && npm run test -- src/test/components/ClipGallery.test.tsx --reporter=dot`; `cd frontend && npm run lint -- src/test/components/ClipGallery.test.tsx`; `python -m py_compile scripts/test_subtitle_styles.py`; `rg -n "WhisperX|whisperx|whisperx_json_path" backend frontend scripts docs README.md .agents .github --glob '!report/**' --glob '!docs/analysis/**' --glob '!legacy/**'`; `bash scripts/verify.sh`
- **On birinci checkpoint sonucu:** `ClipGallery` hedefli test paketi `11 passed`; aktif repo yüzeyinde tarihsel snapshot'lar dışında `WhisperX` terminolojisi kalmadı; `bash scripts/verify.sh` tamamı geçti.
- **On ikinci checkpoint:** `backend/services/job_state.py` ile kalıcı job repository katmanı eklendi ve `backend/api/websocket.py` içindeki singleton manager bu repository ile başlatıldı. Böylece job state artık sadece process içi sözlükte tutulmuyor; serializable alanlar `workspace/state/jobs.json` altında saklanıyor ve yarım kalan `queued/processing` işler restart sonrası `error` durumuna normalize ediliyor.
- **On ikinci checkpoint kanıtı:** `pytest backend/tests/test_job_state_repository.py backend/tests/test_job_fairness.py backend/tests/test_job_ownership.py backend/tests/test_jobs_api_serialization.py backend/tests/unit/test_job_lifecycle.py backend/tests/test_websocket_subject_isolation.py -q`; `pytest backend/tests/test_subject_purge.py backend/tests/test_jobs_cache_invalidation.py backend/tests/test_clip_ready_routing.py backend/tests/test_editor_batch_visibility.py backend/tests/test_clip_transcript_recovery.py backend/tests/test_clip_transcript_routes.py backend/tests/test_clips_cache.py -q`; `python -m py_compile backend/api/routes/jobs.py backend/api/routes/editor.py backend/api/routes/clips.py backend/api/websocket.py backend/services/job_state.py`; `bash scripts/verify.sh`
- **On ikinci checkpoint sonucu:** hedefli job/websocket testleri `15 passed`, route/recovery/purge paketi `22 passed`; tam verify sonucu frontend test `232 passed`, backend pytest `256 passed, 2 skipped`, build başarılı.
- **On üçüncü checkpoint:** `frontend/src/api/client.ts` içinde `/api/projects` çağrısı `good/degraded/unknown` durum modeliyle genişletildi; başarılı sonuçlar cache'leniyor, hata anında varsa son senkron proje listesi `degraded`, yoksa `unknown` dönüyor. `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` ve `frontend/src/components/subtitleEditor/sections.tsx` tarafında bu model UI'ye taşındı; böylece proje listeleme arızasında "Henüz proje yok" gibi sentetik sağlıklı boş durum gösterilmiyor.
- **On üçüncü checkpoint kanıtı:** `cd frontend && npm run test -- src/test/api/client.test.ts src/test/components/SubtitleEditor.project.test.tsx --reporter=dot`; `cd frontend && npx eslint src/api/client.ts src/components/subtitleEditor/useSubtitleEditorController.ts src/components/subtitleEditor/sections.tsx src/test/api/client.test.ts src/test/components/SubtitleEditor.project.test.tsx src/test/components/subtitleEditor.test-helpers.tsx`; `cd frontend && npm run build`; `bash scripts/verify.sh`
- **On üçüncü checkpoint sonucu:** hedefli frontend testleri `16 passed`; tam verify sonucu frontend test `237 passed`, backend pytest `256 passed, 2 skipped`, build başarılı.
- **On dördüncü checkpoint:** `scripts/check_coverage.sh` ile backend `pytest-cov` ve frontend Vitest coverage kapısı eklendi; `.github/workflows/verify.yml` bağımlılık kurulumu, coverage çalıştırma ve artifact yükleme adımlarıyla genişletildi. Coverage çıktı klasörlerinin lint yüzeyini kirletmemesi için `frontend/eslint.config.js` global ignore listesi `build`, `coverage`, `dist` olarak güncellendi.
- **On dördüncü checkpoint kanıtı:** `python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('.github/workflows/verify.yml').read_text())"`; `bash scripts/check_coverage.sh`; `cd frontend && npm run lint`; `bash scripts/verify.sh`
- **On dördüncü checkpoint sonucu:** backend coverage `73.48%`; frontend coverage `statements 78.1 / branches 69.15 / functions 79.8 / lines 78.47`; lint coverage çıktılarına rağmen temiz; tam verify geçti.
- **On beşinci checkpoint:** `frontend/README.md` şablon içerikten çıkarılıp proje özel komut/env/feature/test rehberine dönüştürüldü. Aynı turda `run.sh` Conda zorunluluğundan çıkarıldı; mevcut aktif env, `APP_ENV_NAME` ile seçilen Conda env, `.venv`, `venv` ve sistem fallback sırası eklendi, `SKIP_ENV_ACTIVATION=1` desteği getirildi ve aktif `base` ortamı yanlış pozitif env seçimi olmaktan çıkarıldı.
- **On beşinci checkpoint kanıtı:** `python scripts/check_markdown_links.py docs README.md frontend/README.md scripts/README.md`; `bash -n run.sh`; `timeout 35 ./run.sh`
- **On beşinci checkpoint sonucu:** frontend docs linkleri temiz; `run.sh` shell syntax temiz; startup smoke içinde backend ve frontend başarıyla ayağa kalktı.
- **On altıncı checkpoint:** `backend/services/social/crypto.py` ve `backend/services/social/service.py` içinde `POSTIZ_API_KEY` env fallback varsayılan olarak kapatıldı; yalnız explicit `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1` ile dev opt-in hale getirildi. `backend/runtime_validation.py`, `docs/api-key-setup.md`, `README.md` ve fresh-install rehberi bu yeni güvenlik sözleşmesine göre güncellendi.
- **On altıncı checkpoint kanıtı:** `pytest backend/tests/test_social_crypto.py backend/tests/test_runtime_validation.py backend/tests/test_social_routes.py -q`; `python scripts/check_markdown_links.py docs README.md frontend/README.md scripts/README.md`; `bash scripts/verify.sh`
- **On altıncı checkpoint sonucu:** sosyal güvenlik ve startup validation hedefli paket `31 passed`; tam verify sonucu frontend test `237 passed`, backend pytest `260 passed, 2 skipped`, build başarılı.
- **On yedinci checkpoint:** upload hard-limit guardrail repo içinde entegrasyon testiyle sabitlendi. `backend/tests/integration/test_api_upload_limits.py` ile `/api/upload` ve `/api/manual-cut-upload` üzerinde `Content-Length` tabanlı erken `413 REQUEST_TOO_LARGE` davranışı test altına alındı; mevcut `stream_upload_to_path` ve `prepare_uploaded_project` testleriyle birlikte uygulama içi upload sınırı iki katmanlı güvenceye kavuştu.
- **On yedinci checkpoint kanıtı:** `pytest backend/tests/integration/test_api_upload_limits.py backend/tests/unit/test_upload_validation.py backend/tests/unit/test_upload_prepare_project.py -q`; `python -m py_compile backend/api/server.py backend/api/routes/clips.py backend/api/routes/editor.py backend/tests/integration/test_api_upload_limits.py`; `bash scripts/verify.sh`
- **On yedinci checkpoint sonucu:** upload limit hedefli paket `10 passed`; tam verify sonucu frontend test `237 passed`, backend pytest `262 passed, 2 skipped`, build başarılı.
- **On sekizinci checkpoint:** sibling `/home/arch/postiz-docker-compose` repo'su yeniden denetlendi. `docker-compose.yaml` içinde düz metin `JWT_SECRET`, Postgres credential'ları, gerçek YouTube OAuth credential'ı ve host'a açık `4007/8969/7233/8080` port yayınları doğrulandı; eski `docker-compose.dev.yaml` içinde de DB/Redis/pgAdmin/RedisInsight/Temporal yüzeyleri daha da açık durumda. Dış repo kirli worktree taşıdığı için kullanıcı değişikliklerinin üstüne basmamak adına otomatik patch bu turda uygulanmadı.
- **On sekizinci checkpoint kanıtı:** `git -C /home/arch/postiz-docker-compose status --short`; `git -C /home/arch/postiz-docker-compose diff -- docker-compose.yaml`; `nl -ba /home/arch/postiz-docker-compose/docker-compose.yaml | sed -n '1,220p'`; `nl -ba /home/arch/postiz-docker-compose/docker-compose.dev.yaml | sed -n '1,220p'`
- **On sekizinci checkpoint sonucu:** `GTS-A01` hâlâ gerçek ve yüksek öncelikli operasyonel risk; remediation ayrı branch/commit disipliniyle sibling compose repo üzerinde yapılmalı.
- **On dokuzuncu checkpoint:** sibling compose repo içinde mevcut dosyayı kırmadan additive güvenlik overlay'i hazırlandı. `docker-compose.secure.yaml` ile `JWT_SECRET`, Postiz DB password ve Temporal DB password env dosyasına taşınabilir hale getirildi; `YOUTUBE_CLIENT_ID/SECRET` overlay altında boşlanıyor ve `postiz`, `spotlight`, `temporal`, `temporal-ui` portları `127.0.0.1` bind ile override ediliyor. Kullanım akışı `.env.secure.example` ve `HARDENING.md` ile dokümante edildi.
- **On dokuzuncu checkpoint kanıtı:** `docker compose --env-file .env --env-file .env.secure.example -f docker-compose.yaml -f docker-compose.secure.yaml config`; `git -C /home/arch/postiz-docker-compose status --short`
- **On dokuzuncu checkpoint sonucu:** güvenli migration için ilk adım hazır; mevcut stack bozulmadan secret externalization ve localhost bind geçişi render seviyesinde doğrulandı.
- **Yirminci checkpoint:** uygulama içi çok kullanıcılı Postiz izolasyonu sıkılaştırıldı. `backend/services/social/service.py` içinde subject-scope Postiz account çözümleme ve publish target doğrulaması eklendi; `/api/social/publish` ve `/api/social/publish/dry-run` artık yalnız kullanıcının kendi bağlı account'larını kabul ediyor. Aynı turda `frontend/src/components/shareComposer/helpers.ts` içindeki `social-share-buffer` anahtarı auth identity ile scope edildi; böylece aynı tarayıcıdaki kullanıcı değişiminde önceki kullanıcının paylaşım taslağı görünmüyor.
- **Yirminci checkpoint kanıtı:** `pytest backend/tests/test_social_routes.py -q`; `pytest backend/tests/test_social_crypto.py backend/tests/test_account_deletion_api.py backend/tests/test_subject_purge.py -q`; `cd frontend && npm run test -- src/test/App.test.tsx src/test/components/shareComposer.helpers.test.ts src/test/components/ShareComposerModal.connection.test.tsx src/test/components/ShareComposerModal.publish.test.tsx src/test/components/ShareComposerModal.drafts.test.tsx --reporter=dot`; `cd frontend && npx eslint src/components/shareComposer/helpers.ts src/components/shareComposer/useShareComposerController.ts src/test/components/shareComposer.helpers.test.ts src/test/App.test.tsx`; `bash scripts/verify.sh`
- **Yirminci checkpoint sonucu:** backend sosyal izolasyon paketleri `24 passed`; frontend ilgili paket `16 passed`; tam verify sonucu frontend test `237 passed`, backend pytest `263 passed, 2 skipped`, build başarılı.
- **Yirmi birinci checkpoint:** sibling Postiz compose yüzeyinde hazırlanan secure overlay canlı smoke ile uygulandı. `.env.secure` dosyası ilk geçişte mevcut çalışan JWT/DB/OAuth değerlerini taşıyacak şekilde üretildi; `docker-compose.secure.yaml` `spotlight` için `pull_policy: missing` ile güncellendi ve overlay ile `up -d` rollout yapıldı. Sonuçta `postiz`, `spotlight`, `temporal` ve `temporal-ui` artık `127.0.0.1` bind ile ayağa kalkıyor; Postiz kök endpoint'i `307 /auth` döndürerek uygulamanın nginx arkasında cevap verdiğini doğruluyor.
- **Yirmi birinci checkpoint kanıtı:** `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml config`; `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml up -d`; `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml ps`; `ss -ltn '( sport = :4007 or sport = :8969 or sport = :7233 or sport = :8080 )'`; `curl -I --max-time 10 http://127.0.0.1:4007`; `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml logs --tail=60 postiz`
- **Yirmi birinci checkpoint sonucu:** external compose secret ve port externalization rollout'u başarılı; açık kalan tek operasyonel güvenlik borcu secret rotation ve kalıcı credential yönetimi.
- **Yirmi ikinci checkpoint:** sibling Postiz stack için yerelde yönetilebilir secret rotation tamamlandı. Yeni `POSTIZ_JWT_SECRET`, yeni Postiz DB parolası ve yeni Temporal DB parolası üretildi; ilgili veritabanlarında roller `ALTER ROLE ... PASSWORD` ile güncellendi ve secure overlay ile restart alındı. Transient `postgres` client container'larıyla ağ içinden yapılan doğrulama sonucu yeni parolalarla bağlantı başarılı, eski parolalar ise `password authentication failed` ile reddedildi. Postiz restart sonrası tekrar `307 /auth` döndürerek ayağa kalktığını doğruladı.
- **Yirmi ikinci checkpoint kanıtı:** `docker exec postiz-postgres ... ALTER ROLE "postiz-user" ...`; `docker exec temporal-postgresql ... ALTER ROLE temporal ...`; `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml up -d`; `docker run --rm --network postiz-docker-compose_postiz-network -e PGPASSWORD=<new> postgres:17-alpine psql -h postiz-postgres -U postiz-user -d postiz-db-local -c 'select 1;'`; `docker run --rm --network postiz-docker-compose_postiz-network -e PGPASSWORD=<old> postgres:17-alpine psql -h postiz-postgres -U postiz-user -d postiz-db-local -c 'select 1;'`; `docker run --rm --network temporal-network -e PGPASSWORD=<new> postgres:16 psql -h temporal-postgresql -U temporal -d temporal -c 'select 1;'`; `docker run --rm --network temporal-network -e PGPASSWORD=<old> postgres:16 psql -h temporal-postgresql -U temporal -d temporal -c 'select 1;'`; `curl -I --max-time 10 http://127.0.0.1:4007`; `docker compose --env-file .env --env-file .env.secure -f docker-compose.yaml -f docker-compose.secure.yaml logs --tail=80 postiz`
- **Yirmi ikinci checkpoint sonucu:** JWT ve DB rotation kapandı; sibling compose tarafında kalan tek manuel güvenlik borcu YouTube OAuth app credential rotation.
- **Yirmi üçüncü checkpoint:** sibling Postiz stack için canlı browser tabanlı OAuth smoke yapıldı. `http://127.0.0.1:4007/auth` üzerinden açılan Postiz sayfasında `Google` butonu ilk isteği `http://localhost:4007/api/auth/oauth/GOOGLE` adresine attığı için host farkı kaynaklı CORS hatası verdi. Aynı akış `http://localhost:4007/auth` üzerinden tekrarlandığında Google giriş sayfasına başarılı yönlendirme gerçekleşti; URL içinde `redirect_uri=http://localhost:4007/integrations/social/youtube` ve aktif client id görüldü.
- **Yirmi üçüncü checkpoint kanıtı:** Playwright smoke `http://127.0.0.1:4007/auth -> Google`; Playwright smoke `http://localhost:4007/auth -> Google`; browser URL doğrulaması `https://accounts.google.com/...redirect_uri=http://localhost:4007/integrations/social/youtube...`
- **Yirmi üçüncü checkpoint sonucu:** OAuth env wiring çalışıyor ve Google başlangıç akışı sağlıklı; operasyonel kullanım notu olarak Postiz UI'nin `localhost` host adıyla açılması gerekiyor. Açık kalan son manuel iş YouTube OAuth app credential rotation ve ardından gerçek kullanıcı hesabıyla tam connect tamamlaması.
- **Yirmi dördüncü checkpoint:** kullanıcı tarafından canlı ortamda manuel multi-account validation yapıldı. İki farklı hesapla ayrı ayrı giriş sonrası her kullanıcının yalnız kendi bağlı hesabını kendi alanında gördüğü doğrulandı; hesaplar arası görünürlük sızıntısı gözlenmedi.
- **Yirmi dördüncü checkpoint kanıtı:** kullanıcı doğrulaması: hesap A -> kendi alanında yalnız kendi bağlı hesabı; hesap B -> kendi alanında yalnız kendi bağlı hesabı.
- **Yirmi dördüncü checkpoint sonucu:** `GTS-A01` için OAuth akışı ve hesap izolasyonu operasyonel kabul kriterini geçti. Kalan iş zorunlu remediation değil, yalnız istenirse ileride planlı YouTube OAuth client rotation.
- **Yirmi beşinci checkpoint:** ürün yüzeyinde `managed` bağlantı modu için ilk uyarlama yapıldı. Backend runtime config'e `SOCIAL_CONNECTION_MODE` eklendi; `GET /api/social/accounts` artık `connection_mode` dönüyor ve `managed` modda manuel `POST /api/social/credentials` isteği `403` ile kapatılıyor. Frontend `ShareComposer` bağlantı kartı da bu modda `Postiz API Key` alanını gizleyip yönetilen bağlantı açıklaması ve `Hesapları Yenile` butonuna geçiyor.
- **Yirmi beşinci checkpoint kanıtı:** `pytest backend/tests/test_runtime_validation.py backend/tests/test_social_routes.py -q`; `cd frontend && npm run test -- src/test/components/ShareComposerModal.connection.test.tsx --reporter=dot`; `cd frontend && npx eslint src/components/shareComposer/sections.tsx src/components/shareComposer/useShareComposerController.ts src/test/components/ShareComposerModal.connection.test.tsx src/test/components/shareComposer.test-helpers.tsx src/api/client.ts src/types/index.ts`; `python scripts/check_markdown_links.py README.md docs/api-key-setup.md docs/operations/fresh-install-checklist.md docs/operations/postiz-global-oauth-standard.md`
- **Yirmi beşinci checkpoint sonucu:** ürün artık paylaşımlı/global kurulumda kullanıcıya manuel Postiz API key istememeye hazır. Açık kalan sonraki iş, `managed` mod için gerçek subject-bazlı OAuth callback/storage akışının uygulama içine taşınması.
- **Sonraki odak:** `managed` modun gerçek uçtan uca OAuth callback/storage implementasyonu.

## Test, Static Analysis ve Dependency Review Özeti

| Kontrol | Durum | Not |
|---|---|---|
| `python scripts/check_toolchain.py` | geçti | araç sözleşmesi tutarlı |
| `python scripts/check_runtime_config.py` | geçti | runtime config validator aktif |
| `bash scripts/verify.sh` | kaldı | frontend lint aşamasında durdu |
| `pytest backend/tests -q` | kaldı | `3 failed`, `250 passed`, `2 skipped` |
| `cd frontend && npm run test -- --reporter=dot` | kaldı | `1 failed`, `228 passed` |
| `cd frontend && npm run build` | geçti | production build üretildi |
| `pyright` | çalıştırılamadı | CLI eksik |
| `pyre` | çalıştırılamadı | CLI eksik |
| `pip-audit` / `deptry` / `vulture` / `radon` / `madge` / `ts-prune` / `knip` | çalıştırılamadı | araçlar kurulu değil |

## Dead Code / Unused Import / Unreachable Code Özeti

- Repo-geneli dead code tespiti için kurulu araç yok; bu yüzden kapsamlı unreachable-code raporu üretilemedi.
- Doğrulanmış kullanılmayan/tekrar eden issue:
  `frontend/src/auth/useResilientAuth.ts:4-6` duplicate import warning.
- Doğrulanmış stale test contract:
  `frontend/src/test/components/videoOverlay.helpers.test.ts:24-35`.
- Kod okumasında ek repo-geneli “güvenle silinebilir” modül kümesi kanıtlanmadı; bu alan için otomatik dedektör entegrasyonu önerilir.

## References And Sources

Ana kaynaklar:

- `README.md`
- `docs/architecture/*`
- `docs/flows/*`
- `docs/pages/*`
- `scripts/README.md`
- `.github/workflows/verify.yml`
- `scripts/verify.sh`
- `requirements.txt`
- `frontend/package.json`
- `pyrightconfig.json`
- `pyre.toml`

Doğrudan incelenen yüksek riskli dosyalar:

- `backend/core/orchestrator.py`
- `backend/core/workflow_helpers.py`
- `backend/core/workflows_manual.py`
- `backend/api/routes/clips.py`
- `backend/api/routes/editor.py`
- `backend/api/routes/social.py`
- `backend/services/social/store.py`
- `backend/services/subtitle_renderer.py`
- `frontend/src/api/client.ts`
- `frontend/src/utils/subtitleTiming.ts`
- `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts`
- `frontend/src/auth/useResilientAuth.ts`

Ham komut çıktıları ve ek tablolar için:

- `report/TEKNIK_DENETIM_EK_2026-03-20.md`
