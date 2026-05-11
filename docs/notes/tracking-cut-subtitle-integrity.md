## Tracking + Kesim + Altyazı Bütünlüğü (Repo Notu)

Bu not, oto-kesim (pipeline/batch) ve manual/cut-points akışlarında YOLO tabanlı takip (crop) kalitesi ile
“anlam/video bütünlüğü” sorunlarını aynı yerden çözmek için repo-içi teknik yapılacakları toplar.

### 1) Bug/eksik sınıfı: Akış parity’si (pipeline vs manual)

**Pipeline/Batch akışı** `backend/core/workflow_render_ops.py` içinde:
- Segment sınırları transcript’e göre **snap** edilir (`snap_segment_boundaries`).
- Açılışta subject görünmüyorsa **opening-shot doğrulama** çalışır (`analyze_opening_shot`) ve gerekirse başlangıç kaydırılır.
- Split layout için opening-shot’tan **initial_slot_centers** taşınır.
- Layout safety “enforce” modda unsafe ise **split → single** tek seferlik fallback yapılır ve/veya review_required’a düşer.

**Manual/Cut-points akışı** `backend/core/workflows_manual.py` (ve üstünden `run_cut_points_workflow`) içinde:
- Snap + opening doğrulama + initial_slot_centers parity’si yoksa şu UX problemleri sık görülür:
  - Klip başında subject görünmeden kadraj başlar (ilk 0.5–2s “boş/yanlış” hissi)
  - Kesim kelime ortasına denk gelir (anlam kopması)
  - Split bootstrap yanlış kişiye kilitlenirse tüm klipte “yanlış konuşan” etkisi

**Hedef**: Manual + cut-points akışına da aynı “segment window resolve” korumaları eklenmeli.

### 2) Takipte kullanıcıya kötü hissettiren tipik hatalar

- **ID switch / reacquire yanlış kişiye kilitlenme**: Özellikle kalabalık/yan yana kişiler.
- **Shot-cut reset**: Işık patlaması/flash gibi durumlarda hard-cut yanlış tetiklenebilir → gereksiz reset.
- **Jitter/zıplama**: Candidate cache stride + ani hareket/occlusion ile merkez anlık sıçrayabilir.
- **Split panel swap**: İki kişi yer değiştiriyor gibi algılanır; panel swap kullanıcı için “konuşan değişti” etkisi yaratır.

Repo’da bunların çoğu zaten `tracking_quality` altında ölçülüyor (fallback ratio, id switches, shot_cut_resets,
panel_swap_count, p95 jump, identity_confidence vb).

Ek olarak “tracking good ama yanlış kişi” sınıfı için `single` layout’ta aktif konuşan sinyali izlenir:
- Mevcut ID düşük ağız/üst-gövde hareketindeyken başka bir kişi birkaç ardışık frame belirgin konuşma hareketi gösterirse **active speaker switch** yapılır.
- Bu politika listener lock problemini hedefler; metadata’da `speaker_switch_count`, `listener_lock_suspected`,
  `listener_lock_suspected_frames` ve varsa `speaker_activity_confidence` alanları görünür.
- Eşikler env ile ayarlanabilir: `ACTIVE_SPEAKER_MIN_MOTION_SCORE`, `ACTIVE_SPEAKER_MOTION_MARGIN`,
  `ACTIVE_SPEAKER_CONFIRMATION_FRAMES`.
- Speaker switch sonrasında kısa süreli **fast catch-up** çalışır; normal takip yumuşak kalırken konuşan değişiminde
  kadraj daha hızlı yakalar. Ayarlar: `ACTIVE_SPEAKER_CATCHUP_FRAMES`, `ACTIVE_SPEAKER_MAX_STEP_RATIO`,
  `ACTIVE_SPEAKER_EMA_ALPHA`.

### 3) “Altyazı basarken kadrajda kullanıcıyı takip et” yorumu nasıl yorumlanmalı?

Bu repo’da altyazı burn-in, crop/render’dan sonra uygulanır (`backend/core/media_ops.cut_and_burn_clip`):
- Önce YOLO takip ile 9:16 crop üretilir.
- Sonra altyazı burn-in yapılır (gerekirse `_raw.mp4` backup yazılır).

Dolayısıyla altyazı “takibi bozmaz”, fakat **altyazının kapladığı safe-area** kadraj kararını etkileyebilir.
Bu yüzden hedef, crop kararını “safe-area” ile uyumlu yapmaktır:
- Alt yazı lower-third bölgede yoğun ise, konuşan yüzü/özneyi “daha yukarıda/ortada” tutacak güvenlik kuralları gerekir.
- Mevcut yatay crop modelinde, bu daha çok “öznenin yatayda kesilmemesi + split edge margin” ile sınırlıdır.

### 4) Uygulanabilir iyileştirme stratejileri (tekrarlı bakım maliyetini düşürmek)

#### A) Akış parity’si (en yüksek ROI)
- Manual + cut-points: `snap_segment_boundaries` + `apply_opening_validation` + `initial_slot_centers` taşı.
- Bu, anlam/bütünlük ve split bootstrap stabilitesini hemen iyileştirir.

#### B) Kalite metriklerini aksiyona bağlama
- Tracking “degraded/fallback” ise otomatik olarak:
  - “review_required” (enforce mod)
  - veya tek seferlik “stabilizasyon re-render” (örn. manual_center_x tahmini ile)

##### Enforce politika (uygulandı)
- **Koşul**: `LAYOUT_SAFETY_MODE=enforce`
- **Kural 1 (fallback → unsafe)**: `tracking_quality.status == "fallback"` ise `layout_safety_status` otomatik **unsafe** sayılır ve klip **review_required** akışına düşer.
  - Uygulama noktası: `backend/core/workflow_artifacts.py::_resolve_layout_safety_status`
- **Kural 2 (single stabilize re-render)**: `resolved_layout=="single"` ve takip sinyali **degraded/fallback** veya `identity_confidence` düşükse, tek seferlik `manual_center_x` tahmini ile **stabilize re-render** denenir.
  - Tahmin: `backend/services/video_processor.py::estimate_manual_center_x`
  - Render entegrasyonu: `backend/core/workflow_render_ops.py::_render_with_optional_single_fallback`
  - Metadata işareti: `layout_auto_fix_reason="tracking_stabilize_manual_center"`
- **Kural 3 (split → single)**: Split runtime’da unsafe ise mevcut politika ile **split → single** fallback sürer.

#### C) Senaryo kapsama checklist’i (her video senaryosuna hazırlık)
- Tek kişi konuşuyor, kamera hareketli
- 2 kişi karşılıklı (split uygun)
- 3+ kişi (split riskli → single)
- Occlusion / kadraja girip çıkma
- Sahne değişimi / B-roll
- Ekran kaydı / lower-third grafik/altyazı çakışması
- Dikey kaynak (9:16) / yatay kaynak (16:9) / letterbox

Her senaryoda ölç: `tracking_quality.status`, `layout_safety_status`, `layout_validation_status`,
`render_quality_score`, `transcript_quality.word_coverage_ratio`.

### 5) Log/Debug artefact önerisi

`DEBUG_RENDER_ARTIFACTS=1` ile clip başına:
- `tracking_timeline.json`
- `tracking_overlay.mp4`
- `boundary_snap.json`
- `timing_report.json`
üretimi zaten destekleniyor. Manual/cut-points parity sonrası bu paketler teşhis ve regression için yeterli olmalı.

