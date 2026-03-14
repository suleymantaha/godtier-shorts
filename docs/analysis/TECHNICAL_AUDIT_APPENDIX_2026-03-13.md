# Technical Audit Appendix — 13 March 2026

Bu ek doküman ana raporu destekleyen ham kanıtları, ölçümleri ve drift notlarını içerir.

## 1. İnceleme Ortamı

| Alan | Değer |
|---|---|
| Repo | `/home/arch/godtier-shorts` |
| Harici yüzey | `/home/arch/postiz-docker-compose/docker-compose.yaml` |
| Python | `3.13.11` |
| Node | `v22.22.0` |
| npm | `10.9.4` |
| CUDA | `true` |
| NVENC | `h264_nvenc`, `hevc_nvenc`, `av1_nvenc` |

## 2. Çalıştırılan Kontroller

### 2.1 Test ve Lint

| Komut | Sonuç |
|---|---|
| `pytest backend/tests -q` | `81 passed, 1 failed, 1 skipped` |
| `npm run test -- --reporter=dot` | `17 test file, 69 test passed` |
| `npm run lint` | `0 error, 35 warning` |

### 2.2 Ölçüm Komutları

| Komut tipi | Amaç |
|---|---|
| FastAPI `TestClient` zamanlamaları | `/api/clips`, `/api/projects`, `/api/jobs`, `/api/transcript` sıcak yol ölçümü |
| İç fonksiyon zamanlamaları | `_scan_clips_index`, `ensure_project_transcript` |
| Gerçek medya akışı zamanlamaları | cut-only, short render (YOLO off/on), reburn |
| İzole sosyal dry-run | Postiz fake client ile publish/dry-run maliyeti |

## 3. Ham Ölçümler

### 3.1 API Ölçümleri

```json
{
  "clips_page_1": {
    "path": "/api/clips?page=1&page_size=50",
    "runs_ms": [38.0, 1.64, 1.13, 1.29],
    "avg_ms": 10.52
  },
  "projects": {
    "path": "/api/projects",
    "runs_ms": [1.64, 1.29, 1.29, 1.23],
    "avg_ms": 1.37
  },
  "jobs": {
    "path": "/api/jobs",
    "runs_ms": [1.27, 1.27, 1.3, 1.06],
    "avg_ms": 1.22
  },
  "transcript": {
    "path": "/api/transcript?project_id=yt_ZPkqcNHz2BM",
    "runs_ms": [20.51, 17.03, 17.63, 16.8],
    "avg_ms": 17.99
  }
}
```

### 3.2 İç Fonksiyon Ölçümleri

```json
{
  "ensure_project_transcript_cache_hit_ms": 0.031,
  "scan_clips_index_ms": 35.362,
  "scan_clips_index_count": 45
}
```

### 3.3 Medya Akışı Ölçümleri

```json
{
  "cut_only": {
    "seconds": 1.57,
    "output": "/home/arch/godtier-shorts/workspace/projects/yt_ZPkqcNHz2BM/shorts/audit_cut_only.mp4"
  },
  "short_manual_center": {
    "seconds": 6.704,
    "output": "/home/arch/godtier-shorts/workspace/projects/yt_ZPkqcNHz2BM/shorts/audit_short_manual_center.mp4"
  },
  "short_yolo": {
    "seconds": 12.937,
    "output": "/home/arch/godtier-shorts/workspace/projects/yt_ZPkqcNHz2BM/shorts/audit_short_yolo.mp4"
  },
  "reburn_manual_center": {
    "seconds": 2.008,
    "output": "/home/arch/godtier-shorts/workspace/projects/yt_ZPkqcNHz2BM/shorts/audit_short_manual_center.mp4"
  }
}
```

### 3.4 Sosyal Dry-Run Ölçümü

```json
{
  "save_credentials_ms": 13.54,
  "social_dry_run_ms": 3.33,
  "status": "ok",
  "settings_type": "youtube",
  "media_probe_attempted": true,
  "fake_upload_triggered": true
}
```

## 4. Dizin ve Runtime Gözlemleri

| Ölçüm | Sonuç |
|---|---:|
| `workspace/projects` boyutu | `5.6G` |
| `workspace/metadata` boyutu | `984K` |
| `workspace/temp` boyutu | `434M` |
| `workspace/downloads` boyutu | `576M` |
| Proje sayısı | `4` |
| `shorts` altındaki toplam dosya | `88` |
| Taranan MP4 klip sayısı | `45` |

## 5. Public Interface Envanteri

### 5.1 HTTP/WS Uçları

| Method | Endpoint |
|---|---|
| `GET` | `/api/styles` |
| `POST` | `/api/start-job` |
| `GET` | `/api/jobs` |
| `POST` | `/api/cancel-job/{job_id}` |
| `GET` | `/api/projects` |
| `GET` | `/api/projects/{project_id}/master` |
| `GET` | `/api/projects/{project_id}/shorts/{clip_name}` |
| `GET` | `/api/clips` |
| `GET` | `/api/clip-transcript/{clip_name}` |
| `GET` | `/api/projects/{project_id}/files/{file_kind}` |
| `GET` | `/api/projects/{project_id}/files/{file_kind}/{clip_name}` |
| `POST` | `/api/upload` |
| `POST` | `/api/process-batch` |
| `POST` | `/api/manual-cut-upload` |
| `GET` | `/api/transcript` |
| `POST` | `/api/transcript` |
| `POST` | `/api/process-manual` |
| `POST` | `/api/reburn` |
| `POST` | `/api/social/credentials` |
| `DELETE` | `/api/social/credentials` |
| `GET` | `/api/social/accounts` |
| `GET` | `/api/social/prefill` |
| `PUT` | `/api/social/drafts` |
| `DELETE` | `/api/social/drafts` |
| `POST` | `/api/social/publish` |
| `POST` | `/api/social/publish/dry-run` |
| `GET` | `/api/social/publish-jobs` |
| `POST` | `/api/social/publish-jobs/{job_id}/approve` |
| `POST` | `/api/social/publish-jobs/{job_id}/cancel` |
| `WS` | `/ws/progress` |

### 5.2 Dosya Sözleşmeleri

| Yol | Amaç |
|---|---|
| `workspace/projects/<project_id>/master.mp4` | Kaynak video |
| `workspace/projects/<project_id>/master.wav` | Ayrıştırılmış ses |
| `workspace/projects/<project_id>/transcript.json` | Ana transkript |
| `workspace/projects/<project_id>/viral.json` | Viral analiz çıktısı |
| `workspace/projects/<project_id>/shorts/*.mp4` | Kısa klip |
| `workspace/projects/<project_id>/shorts/*.json` | Klip metadata/transkript |
| `workspace/metadata/social_publish.db` | Sosyal yayın store |

## 6. Drift ve Tutarsızlık Tablosu

| Alan | Gözlem | Kanıt |
|---|---|---|
| Transkript motoru terminolojisi | Gerçek motor faster-whisper; çok yerde WhisperX deniyor | `backend/core/workflows_pipeline.py:119-133`, `backend/core/orchestrator.py:327-344`, `frontend/src/components/AutoCutEditor.tsx:595-600`, `frontend/src/components/Editor.tsx:384-389` |
| Subtitle renderer isimlendirmesi | `generate_ass_file()` parametresi ve log hâlâ WhisperX referanslı | `backend/services/subtitle_renderer.py:277-285` |
| Test fixture açıklamaları | Backend ve frontend type/comment tarafında WhisperX ismi kalmış | `backend/tests/conftest.py:11`, `frontend/src/types/index.ts` |
| Frontend README | Vite template içeriyor | `frontend/README.md` |

## 7. Kalite Bütçesi Kanıtları

### 7.1 Büyük Dosyalar

| Dosya | Satır |
|---|---:|
| `backend/core/orchestrator.py` | 352 |
| `backend/api/routes/clips.py` | 675 |
| `frontend/src/components/AutoCutEditor.tsx` | 632 |
| `frontend/src/components/Editor.tsx` | 567 |
| `frontend/src/components/ShareComposerModal.tsx` | 556 |
| `frontend/src/components/SubtitleEditor.tsx` | 403 |

### 7.2 Lint Warning Özetleri

- `App.tsx`: function length ve complexity uyarısı
- `api/client.ts`: `apiFetch` complexity uyarısı
- `AutoCutEditor.tsx`: duplicate imports + 550 satır / complexity 80 uyarısı
- `Editor.tsx`: duplicate imports + 440 satır / complexity 28 uyarısı
- `JobForm.tsx`, `SubtitleEditor.tsx`, `ShareComposerModal.tsx`, `SubtitlePreview.tsx`, `LazyVideo.tsx`, `Select.tsx`, `useWebSocket.ts`: benzer yapısal uyarılar

## 8. Önceki Bulgulara Göre Durum Güncellemesi

| Önceki bulgu | 13 Mart 2026 durumu |
|---|---|
| Güvenlik header’ları eksikti | **Kısmen çözüldü.** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` eklenmiş |
| `API_HOST/API_PORT` env drift’i vardı | **Çözüldü.** `backend/config.py` env okuyor |
| WebSocket token query param ile taşınıyordu | **Kısmen iyileşti.** Frontend subprotocol kullanıyor; backend fallback olarak query param kabul etmeye devam ediyor |
| Frontend README şablondu | **Hâlâ açık** |
| WhisperX/faster-whisper terminoloji drift’i | **Hâlâ açık** |

## 9. Denetimde Özellikle Olumlu Bulunan Noktalar

- `backend/config.py` içindeki sanitize/path helper’ları temiz.
- `backend/services/social/postiz.py` base URL fallback mantığı, Postiz `/api/public/v1` ve `/public/v1` farklarını tolere ediyor.
- `backend/services/transcription.py` model cache + explicit VRAM release yaklaşımı makul.
- `backend/api/routes/clips.py` clip index cache’i küçük/orta veri setinde anlamlı kazanım sağlıyor.
- Secure file serving yüzeyi, eski static mount yaklaşımından daha güvenli.
