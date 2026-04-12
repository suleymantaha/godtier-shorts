# Marketing App

This directory contains the public marketing site for God-Tier Shorts.

It is intentionally separate from the product UI in [`../frontend`](../frontend), which remains the authenticated Vite application.

## Why this exists

- SEO needs indexable, route-based public pages.
- The product app should stay focused on authenticated workflows.
- Keeping them separate avoids routing and deploy conflicts.

## Commands

```bash
cd marketing
npm install
npm run dev
npm run build
```

## Environment

- `NEXT_PUBLIC_SITE_URL`: canonical origin for the marketing site
- `NEXT_PUBLIC_APP_URL`: product app URL used by CTA buttons

## Release Gate

- `npm run build` release-oncesi zorunlu kontroldur.
- Compare sayfalari dahil tum app routes build sirasinda type-check ve prerender dogrulamasindan gecmelidir.
- `2026-04-01` itibariyla marketing build tekrar gecti.

## Route Health

- CTA button hedefleri `NEXT_PUBLIC_APP_URL` ile tutarli olmali.
- Compare ve feature pages build-time smoke kapsaminda tutulmali.
