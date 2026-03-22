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
