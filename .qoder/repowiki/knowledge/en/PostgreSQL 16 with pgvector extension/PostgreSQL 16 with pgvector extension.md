---
kind: external_dependency
name: PostgreSQL 16 with pgvector extension
slug: postgresql-pgvector
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
source_files:
    - docker-compose.yml
    - backend/requirements.txt
    - DEPLOYMENT.md
---

### Identity
- Dev: `pgvector/pgvector:pg16` image via Docker Compose (service `finshield-postgres`, port 5432).
- Production target: Neon serverless Postgres in Singapore (`ap-southeast-1`) — connection string passed as `DATABASE_URL`.

### Role in this repo
- Primary relational store (SQLAlchemy models under `backend/app/db_models.py`).

### Integration shape
- Local dev uses an embedded SQLite fallback (`sqlite:///./finshield.db`) when no `DATABASE_URL` is set; production must override it to the Neon DSN with `sslmode=require`.
- A separate `RAG_DATABASE_URL` env var is wired in `docker-compose.yml` pointing at the same Postgres instance for vector embeddings.

### Client constraint
- Region: Singapore (`ap-southeast-1`) per the deployment guide — keep latency/PIA considerations in mind if moving tenants elsewhere.