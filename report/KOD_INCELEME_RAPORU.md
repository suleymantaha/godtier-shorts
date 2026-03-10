# 🔍 GodTier Shorts - Kapsamlı Kod İnceleme Raporu

## 📊 Genel Özet

| Kategori  | Sorun Sayısı |
| --------- | ------------ |
| 🔴 Kritik | 4            |
| 🟠 Yüksek | 8            |
| 🟡 Orta   | 12           |
| 🟢 Düşük  | 6            |

---

## 🔴 KRİTİK SORUNLAR

### 1. WebSocket Mesaj Gönderimi - Future Beklenmiyor

**Dosya:** `backend/api/websocket.py:74-77`

```python
def thread_safe_broadcast(status: dict, job_id: Optional[str] = None) -> None:
    loop = get_main_loop()
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_progress(status["message"], status["progress"], job_id),
            loop,
        )  # ⚠️ Future döndürülüyor ama beklenmiyor!
```

**Sorun:** `asyncio.run_coroutine_threadsafe()` bir `Future` döndürür ancak bu beklenmez. Mesajlar gönderilmeyebilir veya yarış durumu oluşabilir.

**Önerilen Çözüm:**

```python
def thread_safe_broadcast(status: dict, job_id: Optional[str] = None) -> None:
    loop = get_main_loop()
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            manager.broadcast_progress(status["message"], status["progress"], job_id),
            loop,
        )
        try:
            future.result(timeout=5)  # 5 saniye timeout
        except Exception as e:
            logger.error(f"WebSocket mesaj gönderilemedi: {e}")
```

---

### 2. Dosya Yükleme - Boyut Limiti Yok

**Dosya:** `backend/api/routes/clips.py:116-117`

```python
@router.post("/upload")
async def upload_local_video(file: UploadFile = File(...)) -> dict:
```

**Sorun:** `UploadFile` için boyut limiti yok. Büyük dosyalar sunucuyu çökertebilir (DoS saldırısı riski).

**Önerilen Çözüm:**

```python
from fastapi import File, UploadFile

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

@router.post("/upload")
async def upload_local_video(file: UploadFile = File(...)) -> dict:
    # Boyut kontrolü
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Dosya boyutu çok büyük (max 500MB)")
```

---

### 3. VideoProcessor - Stdin Deadlock Riski

**Dosya:** `backend/services/video_processor.py:239`

```python
stdin.write(final_frame.tobytes())
# ...
stdin.close()
ffmpeg_proc.wait()
```

**Sorun:** FFmpeg stdin buffer dolduğunda `write()` sonsuza kadar bloklayabilir.

**Önerilen Çözüm:**

```python
# stdout ekle ve non-blocking yaklaşım kullan
ffmpeg_proc = subprocess.Popen(
    ["ffmpeg", "-y", ...],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,  # Eklendi
    stderr=subprocess.DEVNULL,
)

# write yerine communicate veya non-blocking I/O kullan
try:
    stdout, stderr = ffmpeg_proc.communicate(input=frame_bytes, timeout=10)
except subprocess.TimeoutExpired:
    ffmpeg_proc.kill()
    raise RuntimeError("FFmpeg timeout")
```

---

### 4. API Anahtarı Validation - Başlatma Hatası

**Dosya:** `backend/services/viral_analyzer.py:25-30`

**Düzeltildi ✓** - Önceki düzeltmede eklendi.

---

## 🟠 YÜKSEK ÖNCELİKLİ SORUNLAR

### 5. Kod Tekrarı (DRY İhlali)

**Dosya:** `backend/core/orchestrator.py`

| Metod                      | Tekrar Eden Kod               |
| -------------------------- | ----------------------------- |
| `run_pipeline()`           | `_shift_timestamps()` çağrısı |
| `run_manual_clip()`        | `_shift_timestamps()` çağrısı |
| `run_batch_manual_clips()` | `_shift_timestamps()` çağrısı |

**Sorun:** 3 kez tekrarlanan timestamp kaydırma mantığı.

**Önerilen Çözüm:** Helper metod olarak çıkar:

```python
def _process_clip(self, start_t, end_t, ...):
    # Ortak mantık
    pass
```

---

### 6. Bare Except Kullanımı

**Dosya:** `backend/core/orchestrator.py:272-276`

```python
for f in (shifted_json, ass_file, temp_cropped):
    try:
        os.remove(f)
    except FileNotFoundError:
        pass
    except Exception as e:  # ⚠️ Çok geniş yakalama
        logger.error(f"Dosya silinemedi: {e}")
```

---

### 7. Race Condition - Job Dictionary

**Dosya:** `backend/api/routes/jobs.py:97-99`

```python
task = asyncio.create_task(run_gpu_job(job_id, request))  # Task başlıyor
job_info["task_handle"] = task
manager.jobs[job_id] = job_info  # ⚠️ Job eklenmeden önce task çalışabilir
```

---

### 8. Frontend - Upload Yanıt Tipi Eksik

**Dosya:** `frontend/src/api/client.ts:70-74`

```typescript
upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`${API_BASE}/api/upload`, { method: 'POST', body: form }).then(r => r.json());
},
```

**Sorun:**

1. Return tipi belirtilmemiş
2. `response.ok` kontrolü yok
3. Hata durumunda JSON olmayabilir

---

### 9. TypeScript - Layout Field Eksik

**Dosya:** `frontend/src/types/index.ts:83-89`

```typescript
export interface BatchJobPayload {
  project_id?: string;
  start_time: number;
  end_time: number;
  num_clips: number;
  style_name: string;
  // ⚠️ layout alanı eksik!
}
```

Backend'de `layout` parametresi bekleniyor ama frontend types'da yok.

---

### 10. lang Attribute Yanlış

**Dosya:** `frontend/index.html:2`

```html
<html lang="en">
  <!-- ⚠️ UI Türkçe -->
</html>
```

---

### 11. Deprecated FastAPI Event Handler

**Dosya:** `backend/api/server.py`

**Düzeltildi ✓** - Önceki düzeltmede lifespan'a geçildi.

---

### 12. ViralAnalyzer Engine Tutarsızlığı

**Dosya:** `backend/core/orchestrator.py:45`

```python
self.analyzer = ViralAnalyzer(engine="local")  # local olarak başlatılıyor
```

**Sonra:**

```python
orchestrator.analyzer.engine = request.ai_engine  # Ama burada değiştiriliyor
```

**Sorun:** İlk başlatma sırasında gereksiz yere client oluşturuluyor.

---

## 🟡 ORTA ÖNCELİKLİ SORUNLAR

### 13. Input Validation Eksikliği

**Dosya:** `backend/models/schemas.py`

Pydantic validasyon var ama bazı alanlarda eksik:

- `start_time` ve `end_time` için mantıksal kontrol (end > start)
- `youtube_url` için regex validation

---

### 14. Hata Yönetimi - Yetersiz Geri Bildirim

**Dosya:** `backend/api/routes/jobs.py:62-67`

```python
except Exception as e:
    logger.error(f"❌ Hata ({job_id}): {e}")
    if job_id in manager.jobs:
        manager.jobs[job_id]["status"] = "error"
        manager.jobs[job_id]["error"] = str(e)
    await manager.broadcast_progress(f"HATA: {e}", -1, job_id)
```

Hata mesajı kullanıcıya gönderiliyor ama daha detaylı olmalı.

---

### 15. FFmpeg Hata Kontrolü Yetersiz

**Dosya:** `backend/services/video_processor.py:111-117`

```python
subprocess.run(
    ["ffmpeg", ...],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,  # ⚠️ Hata output'u görmezden geliniyor
)
```

---

### 16. Memory Leak - Jobs Dictionary Temizlenmiyor

**Dosya:** `backend/api/websocket.py:20`

```python
self.jobs: Dict[str, Dict[str, Any]] = {}  # ⚠️ Hiç temizlenmiyor
```

Uzun süreli çalışmanda bellek sızıntısı.

---

### 17. VideoProcessor - Model Unload Eksikliği

**Dosya:** `backend/services/video_processor.py`

YOLO modeli her klip sonrası VRAM'den temizlenmiyor. Birden fazla klip işlenirse VRAM dolabilir.

---

### 18. WebSocket Error Handler Eksik

**Dosya:** `frontend/src/hooks/useWebSocket.ts`

`ws.current.onerror` tanımlanmamış veya yetersiz.

---

### 19. Environment Değişkenleri - Eksik Yükleme

**Dosya:** Backend genelinde

`.env` dosyası yüklenmiyor (`load_dotenv()` çağrılmıyor).

---

### 20. Hardcoded Magic Numbers

**Dosya:** `backend/core/orchestrator.py`

```python
smoothness=0.1  # Magic number
render_pct = 60 + int((idx / total) * 35)  # 60, 35 magic numbers
```

---

### 21. Fallback Klasör Adı - Güvenlik Riski

**Dosya:** `backend/core/orchestrator.py:162`

```python
self.project = ProjectPaths(f"fallback_{int(time.time())}")
```

Predictable folder names - güvenlik açığı.

---

### 22. Transkript Filtreleme Mantığı

**Dosya:** `backend/core/orchestrator.py:382`

```python
sub_transcript = [s for s in transcript_data if s["start"] >= start_t and s["end"] <= end_t]
```

**Sorun:** `s["end"] <= end_t` yerine `s["end"] <= end_t and s["start"] >= start_t` olmalı - segmentler aralığın dışında başlayabilir.

---

### 23. Yerel Video Transkripsiyon - Unused

**Dosya:** `backend/core/orchestrator.py:525`

`transcribe_local_video()` metodu tanımlanmış ama hiçbir yerden çağrılmıyor.

---

### 24. ClipMetadata API Return Type Tutarsızlığı

**Dosya:** `backend/api/routes/clips.py:106-113`

```python
@router.get("/clip-transcript/{clip_name}")
async def get_clip_transcript(clip_name: str) -> dict:
    path = OUTPUTS_DIR / clip_name.replace(".mp4", ".json")
    if not path.exists():
        return {"transcript": []}  # Liste döndürüyor
    with open(path, "r", encoding="utf-8") as f:
        return {"transcript": json.load(f)}  # Farklı tip dönebilir
```

---

## 🟢 DÜŞÜK ÖNCELİKLİ SORUNLAR

### 25. Unused Import

**Dosya:** `frontend/src/components/Editor.tsx`

`Upload` import'u kaldırıldı ✓

---

### 26. Logging Seviyesi Tutarsızlığı

Farklı dosyalarda farklı logging seviyeleri kullanılıyor.

---

### 27. TypeScript - Any Kullanımı

**Dosya:** `frontend/src/api/client.ts:73`

`r.json()` any döndürüyor.

---

### 28. Missing Loading States

Bazı component'lerde loading state'ler eksik.

---

### 29. Missing Error Boundaries

React error boundary yok.

---

### 30. Missing Tests

Test coverage çok düşük.

---

## 📋 ÖNERİLEN EYLEM LİSTESİ

| Öncelik | Eylem                         | Dosya              |
| ------- | ----------------------------- | ------------------ |
| 🔴 1    | WebSocket Future await ekle   | websocket.py       |
| 🔴 2    | Upload boyut limiti ekle      | clips.py           |
| 🔴 3    | FFmpeg stdin deadlock önleme  | video_processor.py |
| 🟠 4    | BatchJobPayload'a layout ekle | types/index.ts     |
| 🟠 5    | Frontend upload tipini düzelt | client.ts          |
| 🟠 6    | index.html lang="tr" yap      | index.html         |
| 🟡 7    | .env yükleme ekle             | viral_analyzer.py  |
| 🟡 8    | Jobs expiration ekle          | websocket.py       |
| 🟡 9    | Kod tekrarını refactor et     | orchestrator.py    |
| 🟢 10   | Test coverage artır           | -                  |

---

_Bu rapor otomatik olarak oluşturulmuştur._
_Tarih: 2026-03-07_
