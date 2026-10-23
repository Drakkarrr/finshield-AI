---
kind: external_dependency
name: Neon serverless PostgreSQL
slug: neon
category: external_dependency
category_hints:
    - vendor_identity
    - migration_status
scope:
    - '**'
source_files:
    - DEPLOYMENT.md
    - backend/requirements.txt
---

### Identity
Neon (neon.tech) — serverless Postgres provider recommended for production.

### Migration status
- Development ships with SQLite (`sqlite:///./finshield.db`).
- Production deployment requires switching `DATABASE_URL` to a Neon DSN (`postgresql://user:pass@ep-xxx.neon.tech/finshield?sslmode=require`) and installing `psycopg2-binary`.

### Where it matters
- Only the `DATABASE_URL` env var changes; the rest of the app talks SQLAlchemy, so the migration is a config/env swap plus driver install.