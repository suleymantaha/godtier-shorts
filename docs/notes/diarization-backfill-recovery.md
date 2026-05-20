## Diarization Backfill Recovery

- Sorun: `transcript.json` cache'ten reuse edilirken eski dosyalardaki `speaker: "Unknown"` segmentler aynen korunuyordu.
- Sonuc: `video_processor` diarization index olusturamadigi icin aktif konusmaci takibi pixel-motion fallback ile calisiyordu.
- Duzeltme: Var olan transkript bulunduğunda speaker etiketleri kontrol ediliyor; eksikse mevcut audio uzerinden diarization backfill otomatik tetikleniyor.
- Etki alanlari: `backend/core/workflows_pipeline.py`, `backend/core/workflow_pipeline_ops.py`, `backend/api/routes/clips.py`.
- Runtime guclendirme: `backend/services/diarization.py` artik `DIARIZATION_PYTHON` yoksa proje ici `.venv-diarization` / `.venv` ortamini ve Windows `py` launcher surumlerini deneyerek worker python yorumlayicisini daha guvenilir seciyor.
- Gozlemlenebilirlik: Transkripsiyon sirasinda diarization basarisiz olursa transcript yine yaziliyor ama durum mesajinda `Unknown fallback` acikca belirtiliyor.
