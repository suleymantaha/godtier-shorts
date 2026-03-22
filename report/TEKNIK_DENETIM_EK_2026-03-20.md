# GodTier Shorts — Teknik Denetim Eki

**Üretim zamanı:** 20 Mart 2026, `2026-03-20T22:01:55+03:00`

## 1. Çalıştırılan Komutlar ve Özet Sonuçlar

### Toolchain ve runtime

```text
$ python --version
Python 3.13.11

$ node --version
v22.22.0

$ npm --version
10.9.4

$ python scripts/check_toolchain.py
toolchain ok

$ python scripts/check_runtime_config.py
runtime configuration ok
```

### Verify gate

```text
$ bash scripts/verify.sh
[verify] toolchain
toolchain ok
[verify] runtime config
runtime configuration ok
[verify] frontend lint
...
✖ 57 problems (3 errors, 54 warnings)
```

Frontend lint’i kıran hard error’lar:

```text
frontend/src/auth/useResilientAuth.ts:72:7 react-hooks/set-state-in-effect
frontend/src/components/HoloTerminal.tsx:116:13 react-hooks/set-state-in-effect
frontend/src/components/ui/protectedMedia.ts:16:7 react-hooks/set-state-in-effect
```

### Frontend test

```text
$ cd frontend && npm run test -- --reporter=dot
Test Files  1 failed | 48 passed (49)
Tests       1 failed | 228 passed (229)

FAIL src/test/components/videoOverlay.helpers.test.ts
AssertionError: expected undefined to be null
```

### Backend test

```text
$ pytest backend/tests -q
255 collected
3 failed, 250 passed, 2 skipped
```

Backend fail özeti:

```text
FAILED backend/tests/test_orchestrator_refactor_guardrails.py::test_orchestrator_file_line_budget
FAILED backend/tests/test_social_routes.py::test_approve_future_scheduled_job_creates_remote_schedule
FAILED backend/tests/test_workflows_refactor_guardrails.py::test_workflow_module_line_budgets
```

### Frontend build

```text
$ cd frontend && npm run build
✓ built in 7.31s
```

Öne çıkan bundle boyutları:

| Asset | Boyut | Gzip |
|---|---:|---:|
| `dist/assets/vendor-three-core-CuhjJYOO.js` | 724.27 kB | 187.30 kB |
| `dist/assets/index-CyQxZHWW.js` | 274.85 kB | 84.88 kB |
| `dist/assets/SubtitleEditor-6sdqZI8d.js` | 38.83 kB | 9.84 kB |
| `dist/assets/Editor-DCLDTOSZ.js` | 26.20 kB | 8.53 kB |
| `dist/assets/AutoCutEditor-BQ1aWmv4.js` | 25.05 kB | 7.36 kB |

## 2. Kurulu Olmayan Kalite Araçları

```text
pyright: missing
pyre: missing
pip-audit: missing
deptry: missing
vulture: missing
radon: missing
madge: missing
ts-prune: missing
knip: missing
```

Yorum:

- `pyrightconfig.json` ve `pyre.toml` repo’da var.
- `scripts/README.md` içinde `run_pyre.sh` belgelenmiş.
- Buna rağmen yerel ortamda type/dependency/dead-code araçları aktif kalite kapısı oluşturmuyor.

## 3. Repo Büyüklük ve Yoğunluk Envanteri

### Dizin bazında satır hacmi

| Yol | Dosya | Satır |
|---|---:|---:|
| `backend/api` | 42 | 4215 |
| `backend/core` | 55 | 4414 |
| `backend/services` | 55 | 6591 |
| `backend/models` | 6 | 235 |
| `frontend/src/components` | 44 | 10806 |
| `frontend/src/api` | 3 | 827 |
| `frontend/src/store` | 2 | 410 |
| `frontend/src/hooks` | 4 | 339 |
| `frontend/src/app` | 4 | 630 |
| `frontend/src/auth` | 6 | 789 |
| `frontend/src/utils` | 6 | 699 |
| `scripts` | 21 | 1206 |

### En büyük modüller

| Satır | Dosya |
|---:|---|
| 1857 | `backend/services/video_processor.py` |
| 1341 | `backend/core/workflow_helpers.py` |
| 1295 | `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` |
| 1191 | `backend/api/routes/clips.py` |
| 1130 | `frontend/src/components/subtitleEditor/sections.tsx` |
| 927 | `backend/api/routes/editor.py` |
| 852 | `backend/services/subtitle_renderer.py` |
| 777 | `frontend/src/components/editor/useEditorController.ts` |
| 714 | `backend/services/subtitle_styles.py` |
| 687 | `backend/services/social/service.py` |
| 685 | `frontend/src/api/client.ts` |

### Hotspot listesi

| Dosya | Satır |
|---|---:|
| `frontend/src/api/client.ts` | 685 |
| `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts` | 1295 |
| `frontend/src/components/subtitleEditor/sections.tsx` | 1130 |
| `frontend/src/components/editor/useEditorController.ts` | 777 |
| `backend/services/video_processor.py` | 1857 |
| `backend/services/subtitle_renderer.py` | 852 |
| `backend/core/workflow_helpers.py` | 1341 |
| `backend/api/routes/clips.py` | 1191 |
| `backend/api/routes/editor.py` | 927 |

## 4. Import Graph ve Katman Özeti

Backend cross-layer import sayıları:

| Kaynak | Hedef | Sayı |
|---|---|---:|
| `backend.api` | `backend.core` | 17 |
| `backend.api` | `backend.models` | 3 |
| `backend.api` | `backend.services` | 16 |
| `backend.core` | `backend.api` | 3 |
| `backend.core` | `backend.services` | 25 |
| `backend.models` | `backend.core` | 1 |
| `backend.models` | `backend.services` | 1 |
| `backend.services` | `backend.api` | 1 |
| `backend.services` | `backend.core` | 7 |

Mutual import tespiti:

```text
backend.core.workflow_helpers <-> backend.core.workflows_manual
```

Somut bağımlılık noktaları:

```text
backend/core/workflow_helpers.py:149  from backend.api.routes.clips import invalidate_clips_cache
backend/core/workflow_helpers.py:150  from backend.api.websocket import manager, thread_safe_broadcast
backend/core/workflow_helpers.py:574  from backend.api.routes.clips import invalidate_clips_cache
backend/core/workflow_helpers.py:1074 from backend.core.workflows_manual import ManualClipWorkflow
backend/core/workflows_manual.py:17-24 imports backend.core.workflow_helpers
```

## 5. Route ve API Yüzeyi Özeti

Backend route envanteri: `38` route

Öne çıkan route’lar:

```text
POST /process-batch
POST /manual-cut-upload
GET  /transcript
POST /transcript
POST /transcript/recover
POST /clip-transcript/recover
POST /process-manual
POST /reburn
POST /publish
POST /publish-jobs/{job_id}/approve
POST /publish-jobs/{job_id}/cancel
GET  /projects
GET  /clips
GET  /clip-transcript/{clip_name}
POST /upload
GET  /whoami
```

Frontend API client kullandığı başlıca endpoint’ler:

```text
/api/auth/whoami
/api/jobs
/api/cache-status
/api/start-job
/api/cancel-job/{jobId}
/api/styles
/api/clips
/api/clip-transcript/{clipName}
/api/projects/{projectId}/shorts/{clipName}
/api/upload
/api/projects
/api/transcript
/api/transcript/recover
/api/process-manual
/api/reburn
/api/clip-transcript/recover
/api/process-batch
/api/manual-cut-upload
/api/social/credentials
/api/social/accounts
/api/social/prefill
/api/social/drafts
/api/social/publish
/api/social/publish-jobs
/api/account/me/data
```

Not:

- İncelenen yüzeyde frontend’in kullandığı ana endpoint’ler backend route seti ile eşleşiyor.
- Kritik risk endpoint eksikliğinden değil, bu endpoint’lerin çevresindeki state/parity/mimari sıkılık kaynaklı.

## 6. Dokümantasyon Drift Kanıtları

Yerel markdown link validator sonucu:

```text
Missing local markdown targets: 54
```

Örnek kırık bağlantılar:

```text
docs/operations/youtube-pipeline/README.md -> ../logic/transcription/README.md
docs/operations/youtube-pipeline/README.md -> ../logic/viral-analyzer/README.md
docs/operations/youtube-pipeline/README.md -> ../logic/video-processor/README.md
docs/operations/manual-cut/README.md -> ../logic/video-processor/README.md
docs/operations/reburn/README.md -> ../logic/subtitle-renderer/README.md
docs/pages/clip-editor/README.md -> ../operations/manual-cut/README.md
docs/pages/auto-cut/README.md -> ../operations/upload-transcribe/README.md
docs/pages/subtitle-edit/README.md -> ../operations/transcript-save/README.md
docs/pages/config/README.md -> ../operations/youtube-pipeline/README.md
```

Satır bazlı örnekler:

```text
docs/pages/clip-editor/README.md:59-61
docs/pages/auto-cut/README.md:48-50
docs/pages/subtitle-edit/README.md:49-51
docs/pages/config/README.md:36-38
docs/operations/manual-cut/README.md:65-67
docs/operations/reburn/README.md:51-53
docs/operations/youtube-pipeline/README.md:45-48
```

## 7. Önceki Raporlarla Çelişen Güncel Gerçeklik

Eski rapor:

```text
report/TEKNIK_DENETIM_RAPORU_2026-03-12.md:10
"backend ve frontend testleri geçiyor, lint temiz, frontend bağımlılık audit temiz."

report/TEKNIK_DENETIM_RAPORU_2026-03-12.md:23-27
Backend test: 56 passed, 1 skipped
Frontend test: 16 passed files, 65 passed tests
Frontend lint: başarılı
Frontend npm audit: 0 vulnerability
```

20 Mart 2026 gerçekliği:

```text
verify.sh -> frontend lint fail
pytest backend/tests -q -> 3 failed, 250 passed, 2 skipped
vitest -> 1 failed, 228 passed
```

Çıkarım:

- Önceki raporlar tarihsel bağlam olarak yararlı, fakat doğrudan “mevcut durum” kaynağı olarak kullanılamaz.

## 8. Güçlü Kontroller ve Pozitif Gözlemler

İncelenen kod içinde faydalı korumalar:

- `backend/config.py:39-98`
  proje/clip adı sanitization ve güvenli path yardımcıları
- `backend/runtime_validation.py:9-28`
  runtime port/URL/bool/limit doğrulaması
- `backend/api/server.py:75-102`
  request body hard limit kontrolü ve `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- `backend/api/security.py:36-62`
  policy tabanlı rol matrisi
- `backend/api/server.py:123-146`
  websocket tarafında token doğrulaması ve subprotocol desteği

Not:

- İncelenen güvenlik yüzeyinde hemen doğrulanmış kritik injection/path traversal açığı yok.
- Riskler daha çok süreçsel kalite, parity ve maintainability yönünde yoğunlaşıyor.

## 9. Kullanılan Kaynak Dosyalar

Temel manifest ve kalite dosyaları:

- `README.md`
- `requirements.txt`
- `frontend/package.json`
- `pyproject.toml`
- `pyrightconfig.json`
- `pyre.toml`
- `.github/workflows/verify.yml`
- `scripts/verify.sh`
- `scripts/README.md`

Kritik kod yüzeyleri:

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
- `frontend/src/auth/useResilientAuth.ts`
- `frontend/src/components/HoloTerminal.tsx`
- `frontend/src/components/ui/protectedMedia.ts`
- `frontend/src/test/components/videoOverlay.helpers.test.ts`

