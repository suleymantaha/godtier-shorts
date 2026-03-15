# Frontend

God-Tier Shorts frontend'i React + TypeScript + Vite ile geliştirilir. Ana yüzeyler:

- `CONFIGURE`
- `AUTO CUT`
- `SUBTITLE EDIT`
- `Clip Editor`

## Komutlar

```bash
cd frontend
npm install
npm run dev
npm run test -- --reporter=dot
npm run lint
npm run build
```

## v2.1 Notları

- `SubtitleEditor` clip modunda artık `render_metadata` içinden kalite özeti gösterir.
- Clip listesi değişmedi; kalite alanları `/api/clips` listesine taşınmaz.
- Overlay preview, backend burn çıktısıyla aynı chunk/word zamanlama mantığını kullanır.
- Ortak zamanlama yardımcıları `src/utils/subtitleTiming.ts` içindedir.

## Tip Kaynakları

- API payload ve response tipleri: `src/types/index.ts`
- Subtitle stil ve preview parity: `src/config/subtitleStyles.ts`
- Clip kalite özeti: `src/components/subtitleEditor/`
