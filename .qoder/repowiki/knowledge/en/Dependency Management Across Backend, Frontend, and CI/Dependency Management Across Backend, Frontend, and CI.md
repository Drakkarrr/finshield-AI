---
kind: dependency_management
name: Dependency Management Across Backend, Frontend, and CI
category: dependency_management
scope:
    - '**'
source_files:
    - backend/requirements.txt
    - platform-app/package.json
    - platform-app/package-lock.json
    - .github/workflows/ci.yml
    - backend/Dockerfile
    - platform-app/Dockerfile
    - docker-compose.yml
---

## Approach

FinShield is a Python + Node.js monorepo with two independent dependency ecosystems:

- **Backend (FastAPI)**: `pip` via `backend/requirements.txt`, pinned to exact versions.
- **Frontend (Next.js)**: `npm` via `platform-app/package.json` plus the generated lockfile `platform-app/package-lock.json`, using caret ranges (`^`).
- **CI**: GitHub Actions installs both ecosystems in separate jobs and runs `safety check` against the backend requirements.
- **Containerization**: Each service has its own Dockerfile that re-installs dependencies from scratch; no vendored packages or private registries are used.

There is no shared dependency manifest at the repo root — each deployable owns its own dependency file.

## Key Files

- `backend/requirements.txt` — single flat list of pinned Python dependencies (16 lines).
- `platform-app/package.json` — declares runtime deps (`next`, `react`, `react-dom`) and dev deps (`typescript`, `tailwindcss`, `eslint`, etc.).
- `platform-app/package-lock.json` — npm lockfile for reproducible frontend builds.
- `.github/workflows/ci.yml` — pins `PYTHON_VERSION=3.13` and `NODE_VERSION=20`; caches pip/npm artifacts by dependency path.
- `backend/Dockerfile` — copies `requirements.txt` first, then `pip install --no-cache-dir -r requirements.txt` on `python:3.11-slim`.
- `platform-app/Dockerfile` — copies `package*.json`, runs `npm ci`, then `npm run build` on `node:18-alpine`.
- `docker-compose.yml` — references third-party images (`pgvector/pgvector:pg16`) but does not declare application dependencies.

## Architecture and Conventions

### Python backend

- All 16 entries in `backend/requirements.txt` use `==` pinning (e.g. `fastapi==0.115.0`, `pydantic==2.9.2`, `sqlalchemy==2.0.35`, `psycopg2-binary==2.9.9`, `pgvector==0.3.0`).
- No `setup.py`, `pyproject.toml`, `Pipfile`, `poetry.lock`, or `requirements.in` — `pip install -r requirements.txt` is the only declared installation surface.
- The Dockerfile uses `python:3.11-slim` as the base image, while CI sets `PYTHON_VERSION=3.13`; this means local development and CI may resolve different interpreter versions than what ships in production containers.
- No `PYPI_URL`, `--index-url`, `--extra-index-url`, or `PIP_INDEX_URL` configuration is present anywhere in the repo — public PyPI is the sole source.
- No vendored `vendor/` directory or bundled wheels.

### Next.js frontend

- Runtime dependencies use caret ranges (`^14.2.15`, `^18.3.1`, `^18.3.1`) so minor/patch updates are allowed automatically.
- Dev dependencies also use caret ranges (`^5.6.3` for TypeScript, `^3.4.13` for Tailwind, `^8.57.1` for ESLint).
- `package-lock.json` is committed alongside `package.json`, providing deterministic resolution for `npm ci` in CI and Docker builds.
- No `.npmrc`, no `registry=` override, no `@scope/` private packages — all packages come from the public npm registry.
- No vendored `node_modules` in version control (it is gitignored); the `platform-app/node_modules/` directory visible in the tree is a local artifact.

### CI-driven dependency lifecycle

The workflow defines four stages:

1. **Backend tests** — `actions/setup-python@v5` with `cache-dependency-path: backend/requirements.txt`, then `pip install -r requirements.txt`.
2. **Frontend build** — `actions/setup-node@v4` with `cache-dependency-path: platform-app/package-lock.json`, then `npm ci` followed by `npm run build` and `npm run lint`.
3. **Docker build** — builds all three Dockerfiles (`backend/Dockerfile`, `platform-app/Dockerfile`, `website/Dockerfile`) and validates compose with `docker-compose config`.
4. **Security scan** — runs `safety check -r requirements.txt` in the backend directory; marked `continue-on-error: true` so it does not block PRs.

### Container layering convention

Both Dockerfiles follow the same pattern: copy the dependency manifest first, install dependencies, then copy application code. This maximizes Docker layer caching when only source code changes.

## Conventions and Constraints

- **Python dependencies are pinned with `==`** in `backend/requirements.txt`. This is an observed convention enforced by the file's contents; there is no linter rule enforcing it.
- **Frontend dependencies use caret ranges** in `platform-app/package.json`; the lockfile pins the resolved versions.
- **No private registries or authentication** are configured anywhere in the repository — no `.npmrc`, no `PYPI_URL`, no `GOPRIVATE`, no `PIP_EXTRA_INDEX_URL`.
- **No vendoring** of Python or Node packages into the repository; `node_modules/`, `__pycache__/`, and `.pytest_cache/` are excluded from version control.
- **CI enforces reproducible installs**: pip cache key is tied to `backend/requirements.txt`, npm cache key is tied to `platform-app/package-lock.json`, and Docker builds re-install from those files rather than copying pre-built artifacts.
- **Vulnerability scanning** is performed by `safety` against `backend/requirements.txt` in the `security-scan` job, but it is non-blocking (`continue-on-error: true`).
- **Runtime vs. build-time dependency separation**: the frontend Dockerfile separates `npm ci` (install) from `npm run build` (build), while the backend Dockerfile installs everything in one step since FastAPI/uvicorn serve directly from source.