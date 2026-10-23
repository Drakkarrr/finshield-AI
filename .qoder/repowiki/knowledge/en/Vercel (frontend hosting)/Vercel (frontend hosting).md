---
kind: external_dependency
name: Vercel (frontend hosting)
slug: vercel
category: external_dependency
category_hints:
    - vendor_identity
scope:
    - '**'
source_files:
    - DEPLOYMENT.md
    - platform-app/next.config.js
---

### Identity
Vercel (vercel.com) — suggested host for the Next.js frontend (`platform-app/`).

### Role
- Build framework detected as Next.js with root directory `platform-app/`.
- Requires `NEXT_PUBLIC_API_URL` env var pointing at the Railway backend URL; `next.config.js` rewrites `/api/:path*` to that upstream.

### Not yet in-tree
- No Vercel-specific config file (e.g. `vercel.json`) is present; configuration is done through the Vercel dashboard.