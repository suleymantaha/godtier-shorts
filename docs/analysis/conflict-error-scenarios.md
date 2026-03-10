# Çakışma ve Hata Senaryoları Analizi

## 1. Job ID Çakışması (Yüksek Risk)

**Konum:** `editor.py`, `clips.py`

**Sorun:** `job_id = f"batch_{int(time.time())}"` gibi timestamp tabanlı ID kullanılıyor. Aynı saniye içinde iki istek gelirse aynı `job_id` üretilir ve `manager.jobs[job_id]` üzerine yazılır.


| Endpoint          | job_id formatı          | Çakışma riski |
| ----------------- | ----------------------- | ------------- |
| start-job         | `uuid.uuid4()[:8]`      | Düşük         |
| process-batch     | `batch_{timestamp}`     | **Yüksek**    |
| manual-cut-upload | `manualcut_{timestamp}` | **Yüksek**    |
| process-manual    | `manual_{timestamp}`    | **Yüksek**    |
| reburn            | `reburn_{timestamp}`    | **Yüksek**    |
| upload            | `upload_{timestamp}`    | **Yüksek**    |


**Etki:** İkinci istek birincinin job kaydını siler; progress karışır, iptal yanlış job'u hedefler.

**Öneri:** `uuid.uuid4().hex[:12]` veya `f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"` kullan.

---

## 2. Geçici Dosya Sızıntısı (Orta Risk)

**Konum:** `orchestrator.py` — `run_pipeline`, `run_manual_clip`, `run_batch_manual_clips`

**Sorun:** `_cut_and_burn_clip` veya `video_processor.create_viral_short` hata fırlatırsa cleanup döngüsüne hiç girilmez. `shifted_json`, `ass_file`, `temp_cropped` diskte kalır.

**Örnek:** YOLO OOM, ffmpeg crash, disk dolu.

**Öneri:** `try/finally` ile cleanup garantile veya `atexit` / context manager kullan.

---

## 3. manager.jobs Eşzamanlı Erişim (Düşük Risk)

**Durum:** Asyncio tek thread olduğu için aynı anda sadece bir coroutine çalışır. `manager.jobs` güncellemeleri seri. `list_jobs` `list(manager.jobs.values())` ile snapshot alıyor; `RuntimeError: dict changed` riski yok.

**Not:** `thread_safe_broadcast` thread pool'dan çağrılıyor ama `run_coroutine_threadsafe` ile main loop'a schedule ediyor; job güncellemesi main loop'ta yapılıyor.

---

## 4. Cleanup Task vs Job Silme

**Konum:** `websocket.py` — `_cleanup_expired_jobs`

**Durum:** `for job_id in expired_jobs: del self.jobs[job_id]` — `expired_jobs` ayrı liste; iterasyon sırasında `self.jobs` değişmesi sorun değil. `CancelledError` yakalanıyor.

---

## 5. WebSocket Broadcast Timeout

**Konum:** `websocket.py` — `thread_safe_broadcast`

**Sorun:** `future.result(timeout=5)` — Yavaş veya kopuk WebSocket'lerde 5 sn timeout. Thread bloklanır, hata loglanır. İş devam eder.

**Etki:** Kullanıcı progress göremeyebilir; iş tamamlanır.

---

## 6. Event Loop Kapanırken Broadcast

**Konum:** `thread_safe_broadcast` — `loop.is_running()` kontrolü

**Durum:** Shutdown sırasında `loop` çalışmıyorsa broadcast atlanır, sadece log yazılır. Crash yok.

---

## 7. run_manual_clip — Hata Sonrası Eksik Cleanup

**Konum:** `orchestrator.py:452-493`

**Sorun:** `_cut_and_burn_clip` exception fırlatırsa `cleanup_files` döngüsü çalışmaz. `temp_json`, `shifted_json`, `temp_cropped`, `ass_file` kalır.

---

## 8. run_batch_manual_clips — Klip Döngüsü İçi Hata

**Konum:** `orchestrator.py:430-455`

**Sorun:** 3. klip işlenirken hata olursa önceki 2 klip üretilmiş olur; `temp_orig`, `shifted_json` vb. o iterasyonda temizlenmez. Önceki iterasyonların dosyaları zaten silinmiş olur (her iterasyon kendi cleanup'unu yapıyor).

---

## 9. TEMP_DIR Dosya Çakışması

**Konum:** `run_pipeline` — `shifted_{clip_num}.json`, `cropped_{clip_num}.mp4`

**Durum:** `clip_num` 1..N; aynı pipeline içinde çakışma yok. Farklı pipeline'lar aynı anda çalışırsa `gpu_lock` ile seri çalıştıkları için çakışma olmaz.

**Not:** `run_batch_manual_clips` — `batch_s_{clip_num}.json`; aynı lock altında.

---

## 10. Özet Öncelik


| Öncelik | Sorun                                          | Aksiyon              | Durum            |
| ------- | ---------------------------------------------- | -------------------- | ---------------- |
| P0      | job_id timestamp çakışması                     | uuid ekle            | **Düzeltildi**   |
| P1      | Orchestrator hata sonrası temp dosya sızıntısı | try/finally cleanup  | **Düzeltildi**   |
| P2      | WebSocket broadcast timeout                    | Mevcut (log yeterli) | Kabul edilebilir |


---

## Uygulanan Düzeltmeler (2025-03)

- **job_id:** `batch_{ts}`, `manual_{ts}` vb. → `batch_{ts}_{uuid.hex[:6]}` formatına geçirildi
- **orchestrator:** `run_pipeline`, `run_manual_clip`, `run_batch_manual_clips` — `try/finally` ile temp dosya cleanup garantilendi

