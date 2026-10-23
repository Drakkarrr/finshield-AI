---
kind: external_dependency
name: Railway (backend hosting)
slug: railway
category: external_dependency
category_hints:
    - vendor_identity
scope:
    - '**'
source_files:
    - DEPLOYMENT.md
---

### Identity
Railway (railway.app) — suggested PaaS for deploying the FastAPI backend from GitHub.

### Role
- Environment variables (`DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `APP_PORT`, `DEBUG`) are configured in the Railway dashboard.

### Not yet in-tree
- No `Procfile` exists in `backend/`; the deployment guide instructs adding one if auto-detection fails.