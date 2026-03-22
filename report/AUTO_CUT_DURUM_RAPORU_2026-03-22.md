# Auto Cut Durum Raporu

Tarih: 2026-03-22

## Ozet

- Auto Cut editoru canli olarak acildi ve gercek oturumla incelendi.
- Bu turda yalniz UI degil, gercek `manual-cut-upload` job zinciri de calistirildi.
- Dogrulanan zincir:
  - frontend form
  - `POST /api/manual-cut-upload`
  - upload proje hazirlama
  - transcript uretimi / reuse
  - orchestrator
  - manual clip veya batch clip workflow
  - `clip_ready`
  - job finalize
- Sonuc:
  - Auto Cut'in ana sorunu erisim degil.
  - Ana sorunlar state machine, zaman semantigi, sonuc tasima ve UI/backend sozlesmesi tarafinda.

## Kullanilan Kanitlar

- Canli UI snapshot ve ekran goruntuleri:
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T21-59-03-303Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T21-59-57-740Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T22-00-28-735Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/page-2026-03-21T22-01-04-727Z.yml`
  - `output/playwright/auto-cut-review/.playwright-cli/network-2026-03-21T22-00-06-329Z.log`
  - `output/playwright/auto-cut-review/.playwright-cli/console-2026-03-21T22-00-05-565Z.log`
- Canli backend job artefaktlari:
  - `output/playwright/auto-cut-review/manualcut_job_trace_2026-03-22.json`
  - `output/playwright/auto-cut-review/backend-audit/manualcut_1774131572_1acf47.json`
  - `output/playwright/auto-cut-review/backend-audit/manualcut_1774131473_842a3e.txt`
- Canli log kaniti:
  - `workspace/logs/api_server_2026-03-21.log`
  - `workspace/logs/video_processor_2026-03-21.log`
  - `workspace/logs/renderer_2026-03-21.log`
- Kod yuzeyleri:
  - `frontend/src/components/autoCutEditor/*`
  - `frontend/src/api/client.ts`
  - `frontend/src/store/useJobStore.ts`
  - `backend/api/routes/editor.py`
  - `backend/api/routes/clips.py`
  - `backend/core/workflows_manual.py`
  - `backend/core/workflows_batch.py`
  - `backend/api/websocket.py`

## Dogrulanan Uctan Uca Aksam

### Tek klip akisi

- Canli job: `manualcut_1774131473_842a3e`
- Proje: `up_a4069ffa93794396e1a7bf578c6a7b8b_2efdba3ca75c`
- Sonuc klibi: `manual_manualcut_1774131473_842a3e.mp4`
- Dogrulanan asamalar:
  - upload kabul edildi
  - WAV cikarildi
  - transcript olustu
  - manual render basladi
  - `clip_ready` yayildi
  - final MP4 ve metadata yazildi
- Metadata ozeti:
  - `render_mode=manual_auto`
  - `crop_mode=auto`
  - `layout=auto`
  - `resolved_layout=split`
  - `style_name=TIKTOK`
  - `render_quality_score=81`

### Coklu klip batch akisi

- Canli job: `manualcut_1774131572_1acf47`
- Proje: `up_a4069ffa93794396e1a7bf578c6a7b8b_4afa3ee53060`
- Istek:
  - `start_time=10`
  - `end_time=20`
  - `num_clips=3`
- Gozlenen final durum:
  - timeline icinde `error` olayi yayinlandi
  - ayni job daha sonra `completed` olarak kapandi
  - `output_paths=[]`
  - `clip_name=null`
  - `output_url=null`
  - proje klasorunde hic `shorts/*.mp4` olusmadi

Bu ikinci calisma, Auto Cut'in batch dalinda gercek bir durum paradoksu oldugunu kanitladi.

## Oncelikli Bulgular

### 1. Kritik: Batch Auto Cut isi ayni akista once hata verip sonra basariyla tamamlanmis gibi kapanabiliyor

- Oncelik: `Kritik`
- Baglam:
  - Gercek `manual-cut-upload` batch denemesinde backend timeline su sirayi uretti:
    - `AI Toplu Analiz basliyor`
    - `HATA: Istenen sure araliginda uygun segment bulunamadi.`
    - `Toplu kesim tamamlandi ancak cikti uretilemedi.`
  - Son job durumu `completed`, ama gercek cikti yok.
- Tutarsizligin niteligi:
  - Ayni is hem `error` hem `completed` olarak temsil ediliyor.
  - Nedensellik kiriliyor; basarisizlik terminal olay olmaktan cikiyor.
- Etki:
  - UI hata gostermeyebilir veya eksik gosterebilir.
  - Kullanici "is tamamlandi" gorurken hic klip alamaz.
  - Otomasyon ve operasyon izleme yanlis pozitif uretir.
- Kanit:
  - `output/playwright/auto-cut-review/backend-audit/manualcut_1774131572_1acf47.json`
  - `workspace/logs/api_server_2026-03-21.log` icindeki `2026-03-22 01:19:47`
  - `backend/core/workflows_batch.py:53-83`
  - `backend/api/routes/editor.py:513-536`
  - `backend/api/websocket.py:151-160`
- Onerilen cozum yaklasimi:
  - Batch workflow segment bulamazsa `[]` donmek yerine istisna veya acik `empty` sonuc turu donmeli.
  - Route, `error` yayinlanmis bir isi `completed`e cevirmemeli.
  - UI icin `empty`, `error`, `completed` net ayri terminal durumlarmis gibi tasinmali.

### 2. Kritik: Progress zamani geri akiyor; transcript bittikten sonra is tekrar `%10`a donuyor

- Oncelik: `Kritik`
- Baglam:
  - Canli single Auto Cut job trace'inde ilerleme `41 -> 10 -> 45 -> 99 -> 100`.
  - Transcript fazi bittikten sonra manual render fazi yeni bir baslangic gibi `%10`dan yeniden aciliyor.
- Tutarsizligin niteligi:
  - Tek bir is cizgisinde ilerleme zamani geri sariliyor.
  - Kullanici icin "is yeniden mi basladi?" paradoksu olusuyor.
- Etki:
  - Progress bar guvenilmez hale gelir.
  - Uzun islerde kullanici gereksiz iptal veya tekrar denemesine yonelebilir.
- Kanit:
  - `output/playwright/auto-cut-review/manualcut_job_trace_2026-03-22.json`
  - `backend/api/routes/editor.py:468-483`
  - `backend/core/workflows_manual.py:52-66`
  - `frontend/src/components/autoCutEditor/sections.tsx:541-556`
- Onerilen cozum yaklasimi:
  - Tek bir yuzdelik yerine faz bazli ilerleme modeli kullanin.
  - Ya da transcript ve render yuzdelerini tek monotonic skalaya map edin.

### 3. Yuksek: AI coklu klip modu secili araligi yok sayip tum videoya sifirliyor

- Oncelik: `Yuksek`
- Baglam:
  - Kullanici slider ile bir aralik secse bile `numClips > 1` ve marker yoksa frontend istegi tum videoya ceviriyor.
  - UI ise ayni anda hem aralik secimini hem de AI uretimi ayni baglamda sunuyor.
- Tutarsizligin niteligi:
  - Kullanici zamani ile gercek API zamani ayrisiyor.
  - Aralik yerel, istek global hale geliyor.
- Etki:
  - Beklenmeyen klipler uretilir.
  - Is sureleri ve GPU maliyeti artar.
  - Auto Cut'a duyulan guven azalir.
- Kanit:
  - `frontend/src/components/autoCutEditor/helpers.ts:69-95`
  - `frontend/src/components/autoCutEditor/sections.tsx:634-673`
  - `backend/api/routes/editor.py:513-528`
- Onerilen cozum yaklasimi:
  - Varsayilan davranis secili araligi korumali.
  - Tum videodan analiz ayri bir explicit secim olmali.

### 4. Yuksek: Auto Cut sonucu refresh sonrasi restore edilmiyor

- Oncelik: `Yuksek`
- Baglam:
  - Session persist yalniz is hala processing iken tutuluyor.
  - Is tamamlaninca state temizleniyor.
- Tutarsizligin niteligi:
  - En degerli durum, is tamamlandigi anda kayboluyor.
- Etki:
  - Sayfa yenilenirse result, range ve ilgili job baglami kayboluyor.
  - Kullanici sonucu tekrar Auto Cut icinde goremez; Clip Library'ye itilir.
- Kanit:
  - `frontend/src/components/autoCutEditor/useAutoCutEditorLifecycle.ts`
  - `frontend/src/components/autoCutEditor/useAutoCutEditorController.ts:115-158`
- Onerilen cozum yaklasimi:
  - Son tamamlanan job icin ayri restore state tutulmali.
  - En azindan `projectId`, `resultUrl`, `numClips`, `startTime`, `endTime` saklanmali.

### 5. Yuksek: Coklu klip sonucu `clip_ready` gecmisi dusunce tek klibe cokuyor

- Oncelik: `Yuksek`
- Baglam:
  - Backend batch islerde `output_paths` listesi sakliyor.
  - Frontend fallback ise sadece `clip_name` ve `clip_readyByJob` uzerinden calisiyor.
- Tutarsizligin niteligi:
  - Backend'in coklu sonuc modeli frontend'te tam karsilik bulmuyor.
- Etki:
  - Reload veya TTL sonrasi coklu is sonucu tek klipmis gibi gorunebilir.
  - Result karti gercek uretim sayisini deterministik tasiyamaz.
- Kanit:
  - `backend/api/routes/editor.py:507-543`
  - `frontend/src/components/autoCutEditor/useAutoCutEditorController.ts:39-66`
  - `frontend/src/components/autoCutEditor/sections.tsx:576-590`
  - `frontend/src/store/useJobStore.ts`
- Onerilen cozum yaklasimi:
  - Frontend `output_paths` tabanli sonuc modelini kullanmali.
  - `clip_ready` history yalniz yardimci sinyal olmali, tek kaynak olmamali.

### 6. Yuksek: `empty` is durumu frontend ve backend tarafinda terminal gibi tasinmiyor

- Oncelik: `Yuksek`
- Baglam:
  - Backend modelinde `empty` ayri bir job status.
  - Frontend `hasTerminalJob` hesabinda `empty` yok.
  - Error mesaji da yalniz `cancelled` ve `error` icin uretiliyor.
- Tutarsizligin niteligi:
  - "Cikti yok ama is bitti" durumu semantik olarak eksik modellenmis.
- Etki:
  - UI bos sonuclu isleri ya sonsuz processing gibi ya da sessiz basari gibi gosterebilir.
  - Batch empty durumunda kullaniciya net hata veya net empty mesaji ulasmayabilir.
- Kanit:
  - `frontend/src/types/index.ts:8`
  - `frontend/src/components/autoCutEditor/helpers.ts:55-65`
  - `frontend/src/components/autoCutEditor/helpers.ts:134-169`
  - `backend/api/routes/editor.py:499-505`
  - `backend/api/routes/editor.py:529-536`
- Onerilen cozum yaklasimi:
  - `empty` terminal durum olarak ele alinmali.
  - UI icin ayri `emptyResultMessage` veya benzeri acik durum sunulmali.

### 7. Yuksek: Marker ekleme baslangicta gereksiz kilitli, `Sonu izle` ise gercek sona gitmiyor

- Oncelik: `Yuksek`
- Baglam:
  - Marker ancak `currentTime > startTime + 0.1` ise kabul ediliyor.
  - `Sonu izle` videoyu `endTime - 3`e goturuyor.
- Tutarsizligin niteligi:
  - Baslangic ve son butonlari dogal zaman semantigi ile uyusmuyor.
- Etki:
  - Kullanici video yukledikten sonra "neden hemen kesemiyorum?" sorunu yasiyor.
  - Kisa araliklarda `Sonu izle` fiilen sona degil basa yakin noktaya donebiliyor.
- Kanit:
  - `frontend/src/components/autoCutEditor/helpers.ts:98-123`
  - `frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts:176-221`
- Onerilen cozum yaklasimi:
  - Marker baslangic sinirinda da eklenebilir olmali.
  - `Sonu izle` gercek `endTime - epsilon` davranisi vermeli.

## Orta Seviye Bulgular

### 8. Orta: Yeni dosya secimi eski uretim modunu tasiyor

- Baglam:
  - Yeni video secilince `numClips`, `skipSubtitles`, `style`, `layout`, `animationType` resetlenmiyor.
  - Sayfa gorunurde yeni ama state eski oturumdan geliyor.
- Kanit:
  - `frontend/src/components/autoCutEditor/useAutoCutEditorState.ts:59-79`
  - `frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts:229-257`
- Etki:
  - Kullanici fark etmeden eski AI veya altyazi ayarlariyla yeni is baslatabilir.
- Onerilen cozum:
  - Yeni dosya seciminde kontrollu bir session reset uygulanmali.

### 9. Orta: Ayni dosyayi yeniden secme akisi kirilgan

- Baglam:
  - Hidden input degeri temizlenmedigi icin ayni dosya tekrar secilince `change` tetiklenmeyebilir.
- Kanit:
  - `frontend/src/components/autoCutEditor/sections.tsx:99-104`
  - `frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts:197`
  - `frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts:229-257`
- Etki:
  - Retry ve state reset akislari takilabilir.
- Onerilen cozum:
  - File input degeri secimden once veya sonra sifirlanmali.

### 10. Orta: Dil ve etiketler hala kendi icinde carpismali

- Baglam:
  - Baslik `Otomatik Manual Cut`.
  - `Stil` etiketi aslinda `skipSubtitles` switch'ine bagli.
- Kanit:
  - `frontend/src/components/autoCutEditor/sections.tsx:90-96`
  - `frontend/src/components/autoCutEditor/sections.tsx:377-392`
- Etki:
  - Kullanici feature modelini ilk bakista dogru kuramiyor.
- Onerilen cozum:
  - Ust seviye urun dili ve kontrol etiketleri sadeleştirilmeli.

### 11. Orta: Canli backend erisimi var iken alt cubuk `AUTH:PAUSED` gostermeye devam ediyor

- Baglam:
  - `whoami` ve `clips` cagrilari basarili oldugu halde footer `AUTH:PAUSED`.
- Kanit:
  - `output/playwright/auto-cut-review/.playwright-cli/network-2026-03-21T22-00-06-329Z.log`
  - `frontend/src/components/ui/ConnectionChip.tsx`
- Etki:
  - Auto Cut dogrudan bozulmuyor ama guven ve tanilama kalitesi dusuyor.
- Onerilen cozum:
  - Auth runtime ile gercek korumali request basarisi ayni dogruluk kaynaginda birlestirilmeli.

## Sonuc

- Auto Cut yuzeyi artik yalniz UI anormallikleri degil, gercek backend davranisiyla birlikte de denetlendi.
- En ciddi problem, batch ve empty state'lerde durum makinesinin tek dogru zamani anlatamamasidir.
- En kritik duzeltme sirasi:
  1. batch `error/completed` paradoksunu kapat
  2. progress geriye sarma sorununu duzelt
  3. AI range override'ini kaldir
  4. completed result restore mekanizmasi ekle
  5. multi-clip sonuc modelini `output_paths` temelli hale getir
