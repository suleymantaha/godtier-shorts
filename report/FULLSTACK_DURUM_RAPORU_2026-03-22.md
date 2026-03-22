# Full-Stack Durum Raporu

Tarih: 2026-03-22

Bu sürüm önceki genel notların üstüne Auto Cut akışını uçtan uca derinleştirir. Önceki auth, Clip Library ve Subtitle Editor bulguları geçerliliğini koruyor; burada öncelik Auto Cut'ın gerçek frontend -> API -> transcript -> orchestrator -> render -> clip-ready zinciri.

## Kapsam ve Kanıt

- Canlı uygulama: `http://127.0.0.1:5173`
- Canlı Auto Cut kanıtları:
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T21-59-03-303Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T21-59-57-740Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T22-00-28-735Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T22-01-04-727Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/network-2026-03-21T22-00-06-329Z.log`
- Dinamik backend job kanıtı:
  - `output/playwright/auto-cut-review/manualcut_live_job_response.json`
  - `output/playwright/auto-cut-review/manualcut_live_job_poll.json`
  - `output/playwright/auto-cut-review/backend-audit/manualcut_1774131572_1acf47.json`
  - `output/playwright/auto-cut-review/backend-audit/manualcut_1774131473_842a3e.txt`
  - `workspace/logs/api_server_2026-03-21.log` içindeki `2026-03-22 01:18:43` -> `01:19:01` aralığı
  - `workspace/logs/orchestrator_2026-03-21.log` içindeki `2026-03-22 01:18:43` -> `01:19:00` aralığı
- Kod yüzeyleri:
  - `frontend/src/components/autoCutEditor/*`
  - `frontend/src/store/useJobStore.ts`
  - `frontend/src/api/client.ts`
  - `backend/api/routes/editor.py`
  - `backend/core/workflows_manual.py`
  - ilgili workflow helper ve auth katmanları

## Doğrulanan Uçtan Uca Zincir

Gerçek bir Auto Cut upload job'ı canlı backend üzerinde çalıştırıldı:

- örnek video: `workspace/projects/a4069ffa93794396e1a7bf578c6a7b8b/up_a4069ffa93794396e1a7bf578c6a7b8b_1f063fc510c6/master.mp4`
- API job id: `manualcut_1774131523_6ea862`
- proje: `up_a4069ffa93794396e1a7bf578c6a7b8b_1f063fc510c6`
- sonuç: `manual_manualcut_1774131523_6ea862.mp4`

Route ve workflow zinciri doğrulandı:

1. Frontend submit akışı `editorApi.manualCutUpload(...)` çağırıyor: [useAutoCutEditorActions.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts#L127)
2. Backend `POST /api/manual-cut-upload` route'u upload, transcript ve render kararını aynı request içinde başlatıyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L388)
3. Route önce `prepare_uploaded_project(...)`, sonra `ensure_project_transcript(...)`, sonra orchestrator yaratıyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L430), [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L468), [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L477)
4. Tek klip yolunda `run_manual_clip_async(...)` çağrılıyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L546)
5. Orchestrator `ManualClipWorkflow.run(...)` içine iniyor; burada transcript slice, render plan, subtitle render ve clip-ready event yayınlanıyor: [workflows_manual.py](/home/arch/godtier-shorts/backend/core/workflows_manual.py#L28), [workflows_manual.py](/home/arch/godtier-shorts/backend/core/workflows_manual.py#L76), [workflows_manual.py](/home/arch/godtier-shorts/backend/core/workflows_manual.py#L183)

Dinamik job sırasında gözlenen evreler:

- `35%`: transcript cache hit
- `10%`: manuel klip evresine geri düşüyor
- `45%`: GPU slotu alınıyor
- `99%`: clip_ready event
- `100%`: route finalize ediyor

Bu akış, Auto Cut UI'nin gerçekten sadece görsel bir form değil, tek request ile upload + transcript + render zinciri başlatan bir orchestration yüzeyi olduğunu doğruluyor.

## Kritik Bulgular

### A. Auto Cut workflow, API job kimliğini korumuyor; `clip_ready` doğru karta fallback ile bağlanıyor

- Bulgu:
  - Route `manualcut_*` job kimliğini üretip workflow'a iletiyor, ancak workflow bu kimliği içte `manual_*` id ile eziyor.
  - `clip_ready` olayı explicit job bulunamazsa subject/project bazlı "en yeni aktif job" fallback'i ile hedef seçiyor.
- Dinamik bağlam:
  - Canlı job `manualcut_1774131523_6ea862` için `clip_ready` olayı doğru karta düştü, ama bu doğruluk kod sözleşmesinden değil fallback mekanizmasından geliyor.
- Kod/kanıt:
  - Route job kimliğini workflow'a geçiriyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L545)
  - Orchestrator job kimliğini forward ediyor: [orchestrator.py](/home/arch/godtier-shorts/backend/core/orchestrator.py#L239)
  - Workflow gelen kimliği ezip yeni `manual_*` id üretiyor: [workflows_manual.py](/home/arch/godtier-shorts/backend/core/workflows_manual.py#L57)
  - `clip_ready` helper'ı explicit job bulunamazsa fallback resolve yapıyor: [workflow_helpers.py](/home/arch/godtier-shorts/backend/core/workflow_helpers.py#L172), [clip_events.py](/home/arch/godtier-shorts/backend/api/clip_events.py#L14)
- Tutarsızlık niteliği:
  - İş kimliği route -> orchestrator -> workflow hattında sabit kalmıyor.
- Etkisi:
  - Aynı kullanıcı aynı anda birden fazla Auto Cut işi çalıştırırsa hazır klip olayı yanlış job kartına düşebilir.
- Önerilen çözüm yönü:
  - Workflow içinde ayrı bir temp/run id kullan, fakat dış job id'yi asla ezme.

### 1. Auto Cut job progress'i doğal kronolojiyi bozacak şekilde geri sarıyor

- Bulgu:
  - Canlı job trace'te ilerleme `35%` transcript cache-hit evresinden sonra `10%` manuel render evresine geri düşüyor.
- Dinamik bağlam:
  - `manualcut_1774131523_6ea862` poll kaydında `35 -> 10 -> 45 -> 99 -> 100` sıralaması görüldü.
  - Aynı regresyon backend logunda transcript cache-hit sonrası `Manuel klip: 3837.7 - 3840.7 sn` olarak doğrulanıyor.
- Kod/kanıt:
  - Transcript aşaması route içinden `ensure_project_transcript(...)` ile yayınlanıyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L468)
  - Ardından workflow yeni bir `10%` başlangıç status'u atıyor: [workflows_manual.py](/home/arch/godtier-shorts/backend/core/workflows_manual.py#L54)
  - UI bu değeri doğrudan progress bar'a basıyor, monotonic koruma yok: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L541)
- Tutarsızlık niteliği:
  - Tek bir iş akışında zaman ileri giderken yüzdesel zaman geri gidiyor.
- Etkisi:
  - Kullanıcı işin yeniden başladığını veya takıldığını düşünüyor.
  - Queue/progress güvenilirliği bozuluyor.
  - Job timeline analizi yanıltıcı hale geliyor.
- Önerilen çözüm yönü:
  - Transcript ve render fazları için ayrı stage modeli eklenmeli.
  - Tek progress alanı kalacaksa yayınlar monotonic normalize edilmeli.

### 2. AI çoklu klip modu seçili aralığı yok sayıp tüm videoya sıfırlıyor

- Bulgu:
  - Kullanıcı slider ile seçili bir range belirlese bile `numClips > 1` ve marker yoksa payload `start_time=0`, `end_time=duration` olarak gönderiliyor.
- Canlı bağlam:
  - UI metni kullanıcıya range seçtiğini düşündürüyor; fakat AI açıklaması aynı kart içinde "tüm videodan" davranışa dönüyor.
- Kod/kanıt:
  - Frontend payload builder açıkça full-video override yapıyor: [helpers.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/helpers.ts#L69)
  - Render kartı bu modu "AI ile toplu render" diye sunuyor: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L634)
  - Backend batch/manual-cut route'u kendisine gelen aralığı aynen çalıştırıyor; override frontend kaynaklı: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L513)
- Tutarsızlık niteliği:
  - Kullanıcının zaman seçimi ile gerçek istek parametreleri ayrışıyor.
- Etkisi:
  - Beklenenden uzun işler başlatılıyor.
  - Yanlış klipler üretiliyor.
  - GPU süresi ve maliyet artıyor.
- Önerilen çözüm yönü:
  - `numClips > 1` iken seçili aralığı koru.
  - Tüm video davranışı isteniyorsa ayrı bir explicit toggle kullan.

### 3. Tamamlanan Auto Cut sonucu refresh sonrası sürdürülemiyor

- Bulgu:
  - Session restore yalnız aktif iş sürerken yazılıyor; iş biter bitmez local state siliniyor.
- Kod/kanıt:
  - Persist sadece `processing && currentJobId` iken yazıyor: [useAutoCutEditorLifecycle.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorLifecycle.ts#L58)
  - Processing biter bitmez storage temizleniyor: [useAutoCutEditorLifecycle.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorLifecycle.ts#L79)
  - İlk yükleme yalnız bu session verisinden state kuruyor: [useAutoCutEditorController.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorController.ts#L123), [useAutoCutEditorState.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorState.ts#L43)
- Tutarsızlık niteliği:
  - İş tamamlandıktan hemen sonra en değerli bağlam kaybediliyor.
- Etkisi:
  - Sayfa yenilenirse kullanıcı sonucu, range'i ve bağlı job'ı kaybediyor.
  - Auto Cut tamamlanmış işi kendi ekranında tekrar açamıyor; kullanıcıyı Clip Library'ye zorunlu yönlendiriyor.
- Önerilen çözüm yönü:
  - Son tamamlanan job/result için ayrı kısa ömürlü restore state tut.
  - En azından `projectId`, `resultUrl`, `numClips`, `range` tamamlanma sonrası da saklansın.

### 4. Batch Auto Cut işi hata yayınladıktan sonra `completed` olarak kapanabiliyor

- Bulgu:
  - Gerçek bir `manual-cut-upload` batch denemesinde aynı job önce `HATA: İstenen süre aralığında uygun segment bulunamadı.` yayınladı, sonra `Toplu kesim tamamlandı ancak çıktı üretilemedi.` mesajıyla `completed` kapandı.
- Dinamik bağlam:
  - Job: `manualcut_1774131572_1acf47`
  - İstek: `start=10`, `end=20`, `num_clips=3`
  - Final durum: `status=completed`, `clip_name=null`, `output_url=null`, `output_paths=[]`
- Kod/kanıt:
  - Batch workflow uygun segment bulamazsa `-1/error` yayınlayıp `[]` dönüyor: [workflows_batch.py](/home/arch/godtier-shorts/backend/core/workflows_batch.py#L74)
  - Route bu `[]` sonucunu ayrıca "çıktı üretilemedi" tamamlanması gibi ele alıyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L529)
  - Dinamik job özeti: [manualcut_1774131572_1acf47.json](/home/arch/godtier-shorts/output/playwright/auto-cut-review/backend-audit/manualcut_1774131572_1acf47.json)
- Tutarsızlık niteliği:
  - Aynı iş hem terminal hata hem terminal başarı gibi temsil ediliyor.
- Etkisi:
  - UI hata göstermeyebilir veya sessiz boş sonuç durumuna düşebilir.
  - İzleme ve kullanıcı beklentisi yanlış pozitif alır.
- Önerilen çözüm yönü:
  - `error`, `empty`, `completed` kontratları tek anlamlı hale getirilmeli.
  - Error yayınlanmış iş route seviyesinde `completed`e çevrilmemeli.

## Yüksek Bulgular

### B. Upload kontratı, gerçek MP4 doğrulaması yapmasına rağmen MIME başlığına aşırı duyarlı

- Bulgu:
  - Aynı oturumdan gelen gerçek MP4 upload'ı ilk denemede `HTTP_415 / INVALID_UPLOAD / Desteklenmeyen dosya türü` ile reddedildi.
  - Aynı dosya `multipart` parçasına açık `type=video/mp4` verildiğinde kabul edilip job başlattı.
- Kod/kanıt:
  - MIME allowlist: [upload_validation.py](/home/arch/godtier-shorts/backend/api/upload_validation.py#L11)
  - Route yine de arka tarafta `ffprobe` ile gerçek konteyner/video doğrulaması yapıyor: [clips.py](/home/arch/godtier-shorts/backend/api/routes/clips.py#L299)
  - Canlı 415 logları: [api_server_2026-03-21.log](/home/arch/godtier-shorts/workspace/logs/api_server_2026-03-21.log#L559), [api_server_2026-03-21.log](/home/arch/godtier-shorts/workspace/logs/api_server_2026-03-21.log#L583)
- Tutarsızlık niteliği:
  - Gerçek medya doğrulaması yerine istemci header yorumu belirleyici olabiliyor.
- Etkisi:
  - Tarayıcı/proxy/otomasyon varyasyonları aynı videoyu sebepsiz reddedebilir.
- Önerilen çözüm yönü:
  - Boş veya generic MIME değerlerinde extension + `ffprobe` doğrulamasına izin ver.

### 5. Çoklu klip sonucu clip-ready geçmişi kaybolunca tek klibe çöküyor

- Bulgu:
  - Backend çoklu işlerde `output_paths` ve `num_clips` saklıyor; fakat frontend bunları okumuyor. `clipReadyByJob` yoksa fallback yalnız `currentJob.clip_name` ile tek bir klip üretiyor.
- Kod/kanıt:
  - Backend çoklu çıktıları saklıyor: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L507), [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L538)
  - Frontend fallback yalnız `clip_name` kullanıyor: [useAutoCutEditorController.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorController.ts#L39)
  - Result kartı da ilk klibi gösterdiğini açıkça söylüyor: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L588)
  - Job history TTL sonunda `jobs` ve `clipReadyByJob` tamamen temizleniyor: [useJobStore.ts](/home/arch/godtier-shorts/frontend/src/store/useJobStore.ts#L511)
- Tutarsızlık niteliği:
  - Backend çoklu çıktı üretiyor, frontend bu bilgiyi yalnızca clip_ready history yaşadığı sürece koruyor.
- Etkisi:
  - Reload veya TTL sonrası çoklu sonuçlar "tek klip üretildi" gibi görünmeye başlıyor.
  - Çoklu job sonucu deterministik şekilde geri açılamıyor.
- Önerilen çözüm yönü:
  - Auto Cut controller `output_paths` veya backend'in serialize ettiği hazır klip listesini kullanmalı.
  - Result kartı ilk klip fallback'ına değil gerçek çıktı listesine dayanmalı.

### 6. Marker ekleme akışı başlangıç ve kısa aralıklar için gereksiz biçimde kilitli

- Bulgu:
  - Marker, `currentTime > startTime + 0.1` değilse reddediliyor.
  - `Sonu izle` de gerçek sona değil `endTime - 3` saniyeye gidiyor.
- Kod/kanıt:
  - Marker guard: [helpers.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/helpers.ts#L98)
  - Jump-to-end davranışı: [useAutoCutEditorActions.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts#L204)
  - Butonların kullanıcıya sunduğu dil: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L223)
- Tutarsızlık niteliği:
  - "Başı izle / Sonu izle / Kes" üçlüsü gerçek zaman mantığıyla hizalı değil.
- Etkisi:
  - Kullanıcı başlangıçta marker ekleyemiyor.
  - Kısa range'lerde "Sonu izle" fiilen sona gitmiyor, bazen başlangıca snap ediyor.
- Önerilen çözüm yönü:
  - `>= startTime` sınırına izin ver.
  - Son butonu `endTime - epsilon` gibi gerçek sona yakın davranmalı.

### 7. Yeni dosya seçimi önceki üretim modunu ve riskli varsayılanları taşıyor

- Bulgu:
  - Auto Cut ilk yüklemede `numClips=3`.
  - Yeni dosya seçilince `numClips`, `skipSubtitles`, `cutAsShort`, `style`, `layout`, `animationType` resetlenmiyor.
- Kod/kanıt:
  - Varsayılan çoklu klip: [useAutoCutEditorState.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorState.ts#L61)
  - File select reset'i sınırlı: [useAutoCutEditorActions.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts#L242)
- Tutarsızlık niteliği:
  - Yeni video "temiz başlangıç" değil, önceki oturumun üretim moduyla açılıyor.
- Etkisi:
  - Kullanıcı fark etmeden AI çoklu üretime veya altyazısız moda geçebiliyor.
  - Hata tekrar üretimi zorlaşıyor çünkü ekran görünürde yeni ama state eski.
- Önerilen çözüm yönü:
  - Yeni dosya seçiminde açık bir "session reset" uygulanmalı.
  - `numClips` varsayılanı 1 olmalı; AI batch kullanıcı aksiyonu ile açılmalı.

### 8. Aynı dosyayı yeniden seçme edge-case'i kırılgan

- Bulgu:
  - Hidden file input'un değeri hiç sıfırlanmıyor; aynı dosya tekrar seçildiğinde `change` event'i tetiklenmeyebilir.
- Kod/kanıt:
  - Hidden input ve picker: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L99)
  - File picker yalnız `.click()` yapıyor: [useAutoCutEditorActions.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts#L197)
  - `handleFileSelect` input değerini temizlemiyor: [useAutoCutEditorActions.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts#L253)
- Tutarsızlık niteliği:
  - "Videoyu değiştir" butonu aynı dosya için her zaman deterministik değil.
- Etkisi:
  - Aynı videoyla yeniden deneme, state reset veya hata sonrası retry akışı takılabilir.
- Önerilen çözüm yönü:
  - `event.target.value = ''` veya picker öncesi input reset eklenmeli.

## Orta Bulgular

### 9. Auto Cut sonucu daha iş tamamlanmadan tahmini output URL taşıyor

- Bulgu:
  - Backend route `clip_name` ve `output_url` değerini iş başlamadan üretip response'a koyuyor.
- Kod/kanıt:
  - Response öncesi tahmini URL üretimi: [editor.py](/home/arch/godtier-shorts/backend/api/routes/editor.py#L432)
  - Frontend bunu `pendingOutputUrl` olarak saklıyor: [useAutoCutEditorActions.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts#L178)
  - Job kaybolursa bu URL result fallback'ı oluyor: [helpers.ts](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/helpers.ts#L146)
- Tutarsızlık niteliği:
  - "Üretildi" ile "üretilecek" adresi aynı alan içinde taşınıyor.
- Etkisi:
  - Job senkronizasyonu bozulursa UI ölmüş veya hiç oluşmamış bir output'a bağlanabilir.
- Önerilen çözüm yönü:
  - Pending ve completed output alanlarını ayır.
  - Fallback yalnız server terminal state'i doğrulanınca devreye girsin.

### 10. UI dili hâlâ kendi içinde çelişkili

- Bulgu:
  - Sayfa başlığı `Otomatik Manual Cut`.
  - Subtitle switch etiketi `Stil`, ama aslında `skipSubtitles` toggle'ı.
- Kod/kanıt:
  - Başlık: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L92)
  - Yanlış etiketli switch: [sections.tsx](/home/arch/godtier-shorts/frontend/src/components/autoCutEditor/sections.tsx#L377)
- Tutarsızlık niteliği:
  - Kavram, kontrol ve davranış isimleri farklı şeyler anlatıyor.
- Etkisi:
  - Kullanıcı yanlış ayarı değiştiriyor.
  - Teknik olmayan kullanıcı için feature modeli belirsizleşiyor.
- Önerilen çözüm yönü:
  - `Stil` etiketi preset select'e ait olmalı.
  - Toggle etiketi `Altyazıları kapat` gibi davranış adı taşımalı.

## Ek Gözlemler

- `manual-cut-upload` canlıda gerçekten çalışıyor; auth, transcript ve render zincirinde yapısal bir kopukluk yok.
- Buna rağmen Auto Cut güven problemi esas olarak state taşıma, progress semantiği ve range/result sözleşmesi tarafında yoğunlaşıyor.
- Önceki rapordaki auth/runtime ve Subtitle Editor tutarsızlıkları bu yüzeyin çevresel riskleri olmaya devam ediyor.

## Hızlı Öncelik Sırası

1. Progress regresyonunu düzelt.
2. `numClips > 1` için range override'ı kaldır.
3. Tamamlanan Auto Cut sonucu refresh sonrası restore edilebilir hale getir.
4. Multi-clip sonuçlarını `output_paths` tabanlı modelle.
5. Marker/jump davranışını kısa aralıklarla tutarlı yap.
