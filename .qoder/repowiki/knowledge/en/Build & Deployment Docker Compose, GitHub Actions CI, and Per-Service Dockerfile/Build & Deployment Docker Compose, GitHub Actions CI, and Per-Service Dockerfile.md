---
kind: build_system
name: 'Build & Deployment: Docker Compose, GitHub Actions CI, and Per-Service Dockerfiles'
category: build_system
scope:
    - '**'
source_files:
    - docker-compose.yml
    - .github/workflows/ci.yml
    - backend/Dockerfile
    - platform-app/Dockerfile
    - website/Dockerfile
    - DEPLOYMENT.md
    - DOCKER.md
---

# Build System — FinShield AI

## Approach

FinShield is a **multi-service monorepo** (FastAPI backend, Next.js dashboard, static marketing site) built and deployed via:

- **Docker Compose** (`docker-compose.yml`) for local orchestration of three services plus PostgreSQL.
- **Per-service `Dockerfile`s** under each subproject (`backend/`, `platform-app/`, `website/`).
- **GitHub Actions** (`.github/workflows/ci.yml`) as the sole CI pipeline.
- **Platform-native toolchains**: `pip` + `uvicorn` for Python, `npm` + Next.js build for Node, `nginx:alpine` for the static site.

There is no Makefile, no shared build script, and no centralized build orchestrator — each service owns its own build definition.

## Key Files

| File | Role |
|---|---|
| `docker-compose.yml` | Declares `postgres`, `backend`, `frontend`, shared `finshield-network`, named volumes `backend-data` / `postgres-data` |
| `.github/workflows/ci.yml` | Four jobs: `backend-tests`, `frontend-build`, `docker-build`, `security-scan` |
| `backend/Dockerfile` | Python 3.11 slim image, installs `gcc`, copies `requirements.txt` then code, runs `uvicorn app.main:app --host 0.0.0.0 --port 8091` |
| `platform-app/Dockerfile` | Node 18 Alpine, `npm ci` then `npm run build`, exposes 3000, runs `npm start` with `NODE_ENV=production` |
| `website/Dockerfile` | `nginx:alpine`, replaces default config with `nginx.conf`, serves `/usr/share/nginx/html` on port 80 |
| `DEPLOYMENT.md` | Production guide targeting Railway (backend), Vercel (frontend), Neon (Postgres), PayMongo, Resend |
| `DOCKER.md` | Local Docker Compose quickstart and troubleshooting |

## Architecture & Conventions

### Service boundaries
Each deployable has its own directory, its own `Dockerfile`, and its own dependency manifest:

- **Backend** (`backend/`): FastAPI + Uvicorn, port `8091`, depends on PostgreSQL (via `RAG_DATABASE_URL`) and optionally SQLite (`DATABASE_URL=sqlite:///./finshield.db`).
- **Frontend** (`platform-app/`): Next.js App Router, port `3000`, communicates with backend through `API_URL=http://backend:8091` and `NEXT_PUBLIC_API_URL=http://localhost:8091`.
- **Website** (`website/`): Static HTML/CSS/JS served by nginx, port `80`.

### Compose topology
`docker-compose.yml` defines a single bridge network `finshield-network`. Services depend on each other in order: `backend` waits for `postgres` healthcheck (`pg_isready -U finshield`), `frontend` waits for `backend` to be up. Persistent data lives in two named volumes (`postgres-data`, `backend-data`).

### CI pipeline stages
The GitHub Actions workflow (`ci.yml`) runs four independent jobs:

1. **`backend-tests`** (runs on every push to `main`/`develop` and PRs to `main`):
   - Sets up Python 3.13, caches pip deps from `backend/requirements.txt`.
   - Runs `pytest tests/ -v --tb=short` with `APP_ENV=test`.
   - Verifies imports succeed via `python -c "from app.main import app"`.
2. **`frontend-build`** (same triggers):
   - Sets up Node 20, caches npm deps from `platform-app/package-lock.json`.
   - Runs `npm ci`, `npm run build`, `npm run lint --if-present`.
3. **`docker-build`** (only on push to `refs/heads/main`):
   - Builds all three images: `finshield-backend`, `finshield-platform`, `finshield-website`.
   - Validates compose with `docker-compose config`.
4. **`security-scan`** (only on pull requests):
   - Runs `safety check -r requirements.txt` in `backend/` with `continue-on-error: true`.

### Image layering convention
Both `backend/Dockerfile` and `platform-app/Dockerfile` follow the same cache-friendly pattern: copy only the dependency manifest first, install dependencies, then copy the rest of the source tree. This keeps rebuilds fast when only application code changes.

### Environment variable conventions
- Backend env vars are injected via `docker-compose.yml` environment block (`DATABASE_URL`, `RAG_DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DEBUG`).
- Frontend env vars are baked into the image via `ENV` directives (`API_URL`, `NEXT_PUBLIC_API_URL`) and overridden at runtime via compose.
- The production deployment guide (`DEPLOYMENT.md`) documents an expanded set of variables for Railway/Vercel/Neon/PayMongo/Resend/Sentry.

## Conventions & Constraints

- **One Dockerfile per service** — there is no multi-stage or shared base image; each `Dockerfile` starts from a fresh official base (`python:3.11-slim`, `node:18-alpine`, `nginx:alpine`).
- **Ports are fixed per service**: backend `8091`, frontend `3000`, website `80` — enforced by both `EXPOSE` in Dockerfiles and `ports:` mappings in `docker-compose.yml`.
- **CI versions are pinned via workflow-level `env` variables**: `PYTHON_VERSION: "3.13"`, `NODE_VERSION: "20"` — these drive `actions/setup-python` and `actions/setup-node`.
- **Dependency manifests are the cache keys**: `cache-dependency-path` points to `backend/requirements.txt` and `platform-app/package-lock.json` respectively.
- **Compose uses `depends_on` with `condition: service_healthy`** for postgres (healthcheck runs `pg_isready -U finshield`); frontend simply lists `backend` as a dependency without a health condition.
- **Docker builds are gated**: the `docker-build` job runs only on `push` to `refs/heads/main`; security scans run only on `pull_request` events.
- **Production deployment targets are documented but not automated**: `DEPLOYMENT.md` prescribes Railway for the backend, Vercel for the frontend, and Neon for Postgres — the repo contains no deployment scripts for those platforms beyond the Dockerfiles and `next.config.js` rewrite examples.
- **No versioning strategy is implemented in code**: release tagging is mentioned as `git tag v2.4.0 && git push --tags` in `DEPLOYMENT.md`, but there is no automated changelog, semantic versioning, or artifact registry step in CI.