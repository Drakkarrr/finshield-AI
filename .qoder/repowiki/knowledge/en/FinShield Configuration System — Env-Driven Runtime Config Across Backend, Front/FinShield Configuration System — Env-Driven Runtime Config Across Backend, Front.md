---
kind: configuration_system
name: FinShield Configuration System — Env-Driven Runtime Config Across Backend, Frontend, and Nginx
category: configuration_system
scope:
    - '**'
source_files:
    - backend/.env
    - docker-compose.yml
    - backend/app/main.py
    - backend/app/database.py
    - backend/app/auth.py
    - backend/app/rag_service.py
    - backend/app/seed_rag_data.py
    - platform-app/next.config.js
    - website/nginx.conf
---

## Approach

FinShield uses a flat, environment-variable-driven configuration model with no dedicated config library or schema validator. Each deployable reads its own subset of `os.environ` / `process.env`, loaded from `.env` files (via `python-dotenv`) or injected by Docker Compose.

There is no centralized config object, no YAML/TOML/JSON config files, and no feature-flag framework. Secrets are treated as environment variables and documented inline in the sample `.env`.

## Key Files

- `backend/.env` — canonical sample env for the FastAPI backend (APP_ENV, DEBUG, APP_PORT, DATABASE_URL, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, RATE_LIMIT_PER_MINUTE, CORS_ORIGINS, DEFAULT_SIGNUP_CREDITS).
- `docker-compose.yml` — injects runtime env per service: `DATABASE_URL`, `RAG_DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DEBUG`, `API_URL`, `NEXT_PUBLIC_API_URL`; also defines Postgres credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`).
- `backend/app/main.py` — calls `load_dotenv()` at module top-level; reads `DEBUG`, `CORS_ORIGINS`, `APP_ENV`, `RAG_DATABASE_URL`, `APP_PORT`.
- `backend/app/database.py` — selects SQLite test DB vs. main DB based on `APP_ENV`; derives SQLAlchemy engine URL from `DATABASE_URL`.
- `backend/app/auth.py` — reads `JWT_SECRET_KEY` (falls back to `secrets.token_urlsafe(32)` if missing).
- `backend/app/rag_service.py` — reads `RAG_USE_SENTENCE_TRANSFORMERS`.
- `backend/app/seed_rag_data.py` — reads `RAG_DATABASE_URL`.
- `platform-app/next.config.js` — resolves API target via `process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8091'`.
- `website/nginx.conf` — static site server config (gzip, security headers, SPA fallback, `/health` endpoint); no runtime env.

## Architecture and Conventions

### Backend (FastAPI)

- **Loading**: `python-dotenv.load_dotenv()` is invoked unconditionally at the top of `app/main.py`. All other modules read env directly via `os.getenv(key, default)`.
- **Environment modes**: `APP_ENV=test` toggles two behaviors:
  - Logging level stays at INFO (not DEBUG) — see `main.py` line 48.
  - Rate limiting is disabled — see `_is_test = os.getenv("APP_ENV") == "test"` then `enabled=not _is_test`.
  - Database switches to `sqlite:///./test_finshield.db` — see `database.py` lines 12–15.
- **Secrets**: `JWT_SECRET_KEY` is required; if absent, `auth.py` generates a random one at import time (not persisted). The sample `.env` explicitly instructs replacing it with `openssl rand -hex 32`.
- **Optional features**: RAG is opt-in — only initialized when `RAG_DATABASE_URL` starts with `postgresql` and optional pgvector deps are installed; otherwise `app.state.rag_service` is set to `None` and screening continues without enrichment.
- **Defaults**: Every `os.getenv` call supplies a sensible local-default (e.g. `CORS_ORIGINS="http://localhost:3000"`, `APP_PORT=8091`, `DATABASE_URL="sqlite:///./finshield.db"`).

### Frontend (Next.js)

- `next.config.js` rewrites `/api/*` to the backend using `API_URL` (for Docker internal networking) falling back to `NEXT_PUBLIC_API_URL` (for dev), then to `http://localhost:8091`.
- No client-side env loading beyond Next's built-in `NEXT_PUBLIC_*` prefix convention.

### Infrastructure

- `docker-compose.yml` is the single source of truth for production-like env across services. It pins Postgres image `pgvector/pgvector:pg16`, exposes ports 5432/8091/3000, and wires the `finshield-network` bridge network.
- `website/nginx.conf` configures gzip, security headers (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`), static asset caching (`expires 30d`, `Cache-Control: public, immutable`), SPA fallback, and a `/health` probe returning 200.

## Conventions and Constraints

- **All runtime configuration is passed through environment variables** — there are no `.yaml`, `.toml`, `.json`, or Python config modules. This is enforced by the absence of any such files and by every config read going through `os.getenv` / `process.env`.
- **Local development defaults are baked into code** — each `os.getenv(...)` provides a local-friendly default so the app runs out-of-the-box with just `backend/.env` copied.
- **Test isolation via `APP_ENV=test`** — three distinct behaviors gate on this value: logging level, rate limiter enabled flag, and database path. This is an observed invariant across `main.py` and `database.py`.
- **Secrets are not committed** — `backend/.env` contains placeholder values (`change-me-in-production-use-openssl-rand-hex-32`, `your-secret-key-change-in-production`) and is excluded from version control by `.gitignore`.
- **Docker Compose overrides `.env` for containerized runs** — the compose file hardcodes `DATABASE_URL=sqlite:///./finshield.db` and `DEBUG=false` for the backend service, overriding the local `.env` values inside containers.
- **Frontend API target is resolved at build/runtime via env precedence** — `API_URL` > `NEXT_PUBLIC_API_URL` > `'http://localhost:8091'` in `next.config.js`.
- **No validation or schema for env vars** — types are inferred by usage (e.g. `RATE_LIMIT_PER_MINUTE` is used as an int later, `CORS_ORIGINS` is split on commas). There is no pydantic settings model or env var validation layer.