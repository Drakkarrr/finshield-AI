# FinShield AI — Evidence Register

Every claim in [evolution-summary.md](./evolution-summary.md), [migration-roadmap.md](./migration-roadmap.md), [decision-map.md](./decision-map.md), [gap-map.dot](./gap-map.dot) and [current-vs-target.dsl](./current-vs-target.dsl) traces to a row here.

`✔ verified` = re-checked directly against source during this analysis (command output shown). `agent` = reported by a code-search subagent and not individually re-checked; treat as high-confidence but confirm before acting on it in isolation.

## Repo shape

| Fact | Evidence | Status |
|---|---|---|
| Three deployables: `backend/`, `platform-app/`, `website/` | directory listing at repo root | ✔ verified |
| README's "Project Structure" lists ~21 directories that do not exist (`api/`, `config/`, `worker/`, `scoring/`, `cases/`, `filings/`, `rules/`, `models/`, `rag/`, `events/`, `privacy/`, `security/`, `db/`, `dashboard/`, `audit/`, `observability/`, `sdk/`, `common/`, `docker/`, `deploy/k8s/`, `tests/`) | `README.md:199-222` vs root listing | ✔ verified |
| Backend is 8 modules, 5 452 LOC; `main.py` alone is 2 855 lines (52%) | `wc -l backend/app/*.py` | ✔ verified |
| 15 pinned dependencies; no ML, async, queue or observability library | `backend/requirements.txt:1-15` | ✔ verified |
| Frontend deps are only next, react, react-dom | `platform-app/package.json:11-15` | ✔ verified |
| Wiki is 1188 lines; README 347; DEPLOYMENT 488; DOCKER 173 | `wc -l` | ✔ verified |

## Detection pipeline

| Fact | Evidence | Status |
|---|---|---|
| Sanctions and PEP screening match against 3-element Python sets | `compliance_engine.py:22-23`, checked `:185`, `:198` | agent |
| High-risk geography is a 5-element set | `compliance_engine.py:24` | agent |
| Behavioral stage adds `random.uniform(0, 0.15)` | `compliance_engine.py:293` (comment at `:292` "Add some randomness to simulate ML inference") | ✔ verified |
| `_ml_classify` returns `random.uniform` confidences; docstring says "Simulate ML classification via RAG + LoRA" | `compliance_engine.py:297-304`, `:298` | ✔ verified |
| Risk blend uses literal weights; decision bands are inline literals | `compliance_engine.py:307-327`, `:355-360` | agent |
| Rule-action precedence gate (`RULE_ACTIONS`) is real and well designed | `compliance_engine.py:332-361` | agent |
| A real z-score behavioral monitor with cold-start thresholds exists but is never called by `screen()` | `main.py:2196-2220`; grep for `score_transaction_behavior` returns only its own definition at `main.py:2171` and `update_account_baseline` at `:2239` — no call sites | ✔ verified |
| Baselines are keyed on `sender_name` as an account proxy | `main.py:2248` | agent |
| `POST /api/v1/behavioral/update-baseline` raises `NameError` when >1 transaction: `import math` is function-local at `main.py:2177`, `math.sqrt` is called at `main.py:2274` in a different function | grep `import math\|math\.sqrt` → only those two lines | ✔ verified |
| Engine keeps an unbounded in-memory idempotency dict; a real DB-level idempotency check also exists | `compliance_engine.py:37`, written `:161`; DB check `main.py:454-473` | agent |
| Transaction ids are generated with `random.randint` then overwritten by the DB UUID | `compliance_engine.py:147`, `main.py:537` | agent |

## RAG

| Fact | Evidence | Status |
|---|---|---|
| Retrieval issues real pgvector `cosine_distance` SQL; no SQLite/in-memory fallback | `rag_service.py:276-278,305-307,343-345`; `Vector` type `:23,115,129,141`; `CREATE EXTENSION` `:152` | agent |
| Embeddings are MD5 feature-hashing into 384 buckets (unigram+bigram, sign bit, L2-normalised) | `rag_service.py:52-73`; docstring `:58-59` admits "lexical overlap" | agent |
| Real `SentenceTransformer("all-MiniLM-L6-v2")` path is behind `RAG_USE_SENTENCE_TRANSFORMERS` defaulting to `"false"` | `rag_service.py:36-38`; grep confirms the default | ✔ verified |
| `sentence-transformers` is absent from `requirements.txt`, so that path can never activate | `backend/requirements.txt` | ✔ verified |
| RAG service is built only when `RAG_DATABASE_URL` starts with `postgresql`; otherwise `app.state.rag_service = None` | `main.py:139-150` | ✔ verified |
| Compose sets `RAG_DATABASE_URL` (RAG live in Docker); local `backend/.env` does not (RAG silently off in dev) | `docker-compose.yml:33`; `.env` key list | ✔ verified |
| When enabled, RAG can flip `approved → flagged` and floor risk at 0.5, but cannot escalate to blocked or lower a decision | `main.py:500-503` | agent |
| Retrieval output is persisted to `transactions.rag_context` and echoed in the detail response | `main.py:530`, `:637`; column `db_models.py:100` | agent |
| Corpus = 5 policy documents, 6 sanctions entries, 5 precedents; `__main__`-only script invoked by nothing | `seed_rag_data.py:17-24,27-73,80-135,142-178,190-197` | agent |
| All four `/api/v1/rag/*` routes return 503 when the service is `None` | `main.py:2753,2771,2788,2805`; guards `:2760,2778,2795,2812` | agent |

## API surface and routing bugs

| Fact | Evidence | Status |
|---|---|---|
| 68 routes; auth on 5, keys 3, transactions 5, cases 10, filings 5, rules 6, billing 6, behavioral 3, breakers 5, webhooks 3, privacy 2, rag 4, notifications/search/stats 8, system 2 | `main.py` route decorators | agent |
| `GET /api/v1/transactions/export` (`main.py:666`) is registered **after** `GET /api/v1/transactions/{tx_id}` (`main.py:606`) with the same verb → unreachable; the frontend calls it | grep of `@app.get("/api/v1/transactions` → `:573`, `:606`, `:666`; caller `platform-app/src/app/transactions/page.tsx:98` | ✔ verified |
| No admin/user-management, audit-read, settings, reports, metrics or tenant routes exist | endpoint inventory | agent |
| `/api/health` returns a hardcoded services map — `database`, `behavioral_ml`, `rag_classifier`, `case_manager`, `api_gateway` all statically `"healthy"` | `main.py:2830-2845` | ✔ verified (full block quoted in analysis) |
| `GET /privacy/pii-classification` returns a literal dict | `main.py:2708-2724` | agent |
| `POST /privacy/dsar` only writes an AuditLog row; code comment says "we just log it" | `main.py:2682`, comment `:2689-2690` | agent |
| Webhook `dispatch` inserts `status="pending"` and returns; `retry` resets fields; no state ever reaches delivered/failed/dead_letter; no `httpx` client in `main.py` | `main.py:2589,2646,2664-2667` | agent |
| Circuit-breaker transitions are driven only by client POSTs; no call is wrapped; monitored dependencies (`model_server`, `pgvector`, `redis`, `notification_service`) are never invoked by the code | `main.py:2381-2546`, `:2443-2445`, `:2510` | agent |

## Data and schema

| Fact | Evidence | Status |
|---|---|---|
| 14 primary tables; 3 RAG tables on a **separate** `declarative_base()` | `db_models.py:22,59,75,108,141,154,169,184,212,225,240,275,296,318`; `rag_service.py:102-142` | agent |
| No tenants, roles/permissions, DSAR records, model_versions, feature_flags, settings, reports or webhook-subscription tables | model inventory | agent |
| `User` has no `role` column; card last4/expiry/holder are plaintext columns | `db_models.py:22`, `:46-48` | agent |
| Schema is created by `Base.metadata.create_all` — no Alembic anywhere; `alembic` not in requirements | `database.py:36-38`, `:44`; `rag_service.py:153`; `main.py:133-135`; `requirements.txt` | ✔ verified |
| `RuleConfig.priority/version/effective_from/effective_to` are written but never read by the engine | `db_models.py:195-198`; `compliance_engine.py:168-177` | agent |
| Per-user `rule_configs` overrides ARE wired end-to-end and editable from the admin UI | `db_models.py:184-209` → `main.py:476-479,1377` → `compliance_engine.py:168-177` | agent |

## Auth, security, tenancy

| Fact | Evidence | Status |
|---|---|---|
| bcrypt hashing, HS256 JWT, dual-mode `get_current_user` accepting JWT or `fsk_`-prefixed API key verified by bcrypt against `ApiKey.key_hash` | `auth.py:32-39,42-56,59-113,77-92,116-121` | agent |
| 64 of 68 routes declare `Depends(get_current_user)`; public: register, login, `/api/health`, `/` | `main.py:176,237,2830,2848` | agent |
| `JWT_SECRET_KEY` falls back to a per-process random value when unset | `auth.py:22` | agent |
| No RBAC: no role column, no `require_admin`; breaker/DSAR/webhook-admin routes are open to any authenticated user | `db_models.py:22`; `main.py:2429-2510,2589,2682` | agent |
| Zero occurrences of "tenant" in the backend; isolation is per-user row filtering | grep; e.g. `main.py:455,583,1934,2247,2624` | agent |
| Zero hits for `encrypt`/`Fernet`/pgcrypto; no PII masking; no prompt-injection defence | grep | agent |
| slowapi `Limiter` configured but disabled when `APP_ENV=test`; only 3 routes decorated (register 5/min, login 10/min, transactions 60/min); `RATE_LIMIT_PER_MINUTE` never read | `main.py:73-77,177,238,435` | agent |
| 15 `AuditLog` write sites; no append-only constraint, no hash chaining, no read endpoint; screening decisions themselves are not audited (only `logger.info`) | `main.py:204,248,344,1024,1098,1163,1407,1643,1973,2103,2147,2447,2490,2532,2692`; `:565` | agent |

## Async, resilience, observability

| Fact | Evidence | Status |
|---|---|---|
| No background execution: zero `BackgroundTasks`/`asyncio` in `backend/app/`; all 68 handlers are `async def` running blocking sync SQLAlchemy | grep | agent |
| `celery` appears once, in a comment; `redis` appears only as strings naming a nonexistent dependency | `main.py:2606`; `main.py:2390,2555`; `db_models.py:280` | agent |
| No OpenTelemetry, Prometheus, structlog or Sentry; logging is `basicConfig` plus a timing middleware setting `X-Process-Time-Ms` | `main.py:47-51,119-126`; grep 0 hits | agent |

## Tests and CI

| Fact | Evidence | Status |
|---|---|---|
| 43 async API tests over 9 classes; 22 engine unit tests; 65 total passing | `backend/tests/test_api.py` (559 LOC), `backend/tests/test_compliance_engine.py` (223 LOC) | agent |
| `backend/test_filing_e2e.py` (1 test, needs a live server at `localhost:8091`) sits outside `tests/`, so `pytest tests/` never collects it | `backend/test_filing_e2e.py:11`; `ci.yml:38` | agent |
| No test touches filings, behavioral, breakers, webhooks, privacy, RAG, notifications, search, export, rule stats, case aggregate or check-sla | test inventory | agent |
| CI runs pytest (Python 3.13 vs image 3.11), frontend build + lint, docker build, and a `safety` scan with `continue-on-error: true` | `.github/workflows/ci.yml:10,28,36-41,61-68,81-90,112` | ✔ verified |
| `docker build ./backend` and `./platform-app` cannot succeed: both Dockerfiles COPY root-relative paths | `ci.yml:81,84` vs `backend/Dockerfile:12,16` (`COPY backend/requirements.txt .`, `COPY backend/ ./`) and `platform-app/Dockerfile:7,11` | ✔ verified |
| No coverage measurement, no Python lint or typecheck, no `tsc --noEmit`, no secret or image scanning, no eval harness, no load tests | grep for ruff/black/mypy/pytest-cov/locust/RAGAS → 0 | agent |

## Secrets, containers, deployment

| Fact | Evidence | Status |
|---|---|---|
| `backend/.env` is tracked in git (has been since the first commit) even though `.gitignore:26` lists `.env`; it was never `git rm --cached` | `git ls-files \| grep -iE "\.env$\|\.db$"` → `backend/.env` only | ✔ verified |
| `.env` keys: `APP_ENV`, `DEBUG`, `APP_PORT`, `DATABASE_URL`, `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `RATE_LIMIT_PER_MINUTE`, `CORS_ORIGINS`, `DEFAULT_SIGNUP_CREDITS`; all values are placeholders (no third-party credentials), but `JWT_SECRET_KEY` is a readable signing key and `DEBUG=true` | `.env:2,10,13` | agent |
| `backend/test_finshield.db` is now untracked but present on disk (commit `91e4de8` removed it) | `git ls-files backend \| grep "\.db"` → empty | ✔ verified |
| Compose hardcodes `POSTGRES_PASSWORD=finshield_secret`, a credential-bearing `RAG_DATABASE_URL`, and `JWT_SECRET_KEY=your-secret-key-change-in-production`; publishes `5432:5432` | `docker-compose.yml:8,11,33,34` | ✔ verified |
| Backend container uses SQLite as its primary DB while pgvector Postgres runs beside it | `docker-compose.yml:32` vs `:5` | ✔ verified |
| No resource limits, no `read_only`, no `user:`, no `security_opt`; backend has no healthcheck so `frontend: depends_on: backend` is start-order only | `docker-compose.yml:15,43,57-59` | agent |
| All three images run as root, none has a `HEALTHCHECK`, none is digest-pinned or multi-stage; `backend/Dockerfile` installs `gcc` and ships pytest/httpx | `backend/Dockerfile:2,7-9,19`; `platform-app/Dockerfile:2,28`; `website/Dockerfile:2` | ✔ verified (grep of COPY/FROM/USER/HEALTHCHECK/CMD) |
| `node:18-alpine` (EOL) is the frontend base; `output: 'standalone'` is set but `npm start` is used, so the standalone server is never run | `platform-app/Dockerfile:2,28`; `next.config.js:3` | ✔ verified |
| `NEXT_PUBLIC_API_URL=http://localhost:8091` is baked at build time, so the compose runtime value cannot override it | `platform-app/Dockerfile:15-16` vs `docker-compose.yml:56` | agent |
| No `.env.example` anywhere, though `README.md:143` instructs `cp .env.example .env` | repo-wide find | agent |
| No Alembic, no `deploy/`, no Helm chart, no k8s manifests, no Terraform, no Prometheus/Grafana config | repo-wide find; `README.md:301-311` documents `./deploy/k8s` | ✔ verified |
| `README.md:147-159` documents a `docker/docker-compose.yml` with worker + Redis + Prometheus; the path does not exist and those services do not exist | root listing; `docker-compose.yml` | ✔ verified |
| `website/nginx.conf` listens on 80 only; has X-Frame-Options/nosniff/XSS-Protection but no HSTS, CSP or Referrer-Policy; the `add_header` inside the static-asset location drops the parent headers | `nginx.conf:2,13-15,20` | agent |
| `platform-app/next.config.js` has no `headers()` — the authenticated dashboard ships zero security headers | `next.config.js:1-17` | agent |
| `DEPLOYMENT.md:60-388` describes Railway/Vercel/Neon/PayMongo/Resend/Sentry/UptimeRobot and `:159` says "Create `backend/app/payment.py`"; none exists. `:314-334` uses the wrong env name `SECRET_KEY` (code reads `JWT_SECRET_KEY`). Backup strategy is "Neon auto-backs up" / manual `docker cp` | `DEPLOYMENT.md:159,314-334,391-399`; `DOCKER.md:121-133` | agent |

## Frontend

| Fact | Evidence | Status |
|---|---|---|
| 11 routes; 8 fully backed by real CRUD (transactions, cases, filings, rules, settings, api-keys, login, signup); dashboard and reports are real-data but read-only with zero `onClick`; `docs` is a hardcoded array | `platform-app/src/app/*/page.tsx`; `dashboard/page.tsx:29-31`; `reports/page.tsx:13,31`; `docs/page.tsx:6-40` | agent |
| API client base URL is a hardcoded relative `'/api'`; `NEXT_PUBLIC_API_URL` is only used by the rewrite proxy | `lib/api.ts:7`; `next.config.js:7-13` | agent |
| JWT stored in `localStorage` key `finshield_token`; no 401 interceptor; `api.ts:396` has a dead `body.detail || body.detail?.message` branch | `lib/api.ts:358-370,379-381,388-417` | agent |
| ~30 typed interfaces, no `any` in signatures; no orphan frontend calls (every endpoint it calls exists in the backend) | `lib/api.ts:10-355` | agent |
| No `middleware.ts`; `isAuthenticated` is checked only in the root redirect; `PlatformLayout.tsx:7-18` does no gating | `src/app/page.tsx:12`; repo-wide search | agent |
| No role field on `UserProfile`; Sidebar uses `user` for display only | `lib/api.ts:48-68`; `Sidebar.tsx:105` | agent |
| No data-fetching library; per-page `useEffect` + `loading/error/data`; no pagination UI (`listTransactions(100, 0)`); no optimistic updates | `transactions/page.tsx:37`; `dashboard/page.tsx:30`; `cases/page.tsx:294-310` | agent |
| No WebSocket/EventSource anywhere; "real-time" is one 30s `setInterval` notification poll | `Topbar.tsx:240-245`; `dashboard/page.tsx:67` | agent |
| No DESIGN.md, no token file, no `components/ui/`; `tailwind.config.js:10-32` does define a real semantic palette + shadow tokens; no type/spacing scale, no `fontFamily` token (Inter via `<link>`) | repo search; `tailwind.config.js:10-32`; `layout.tsx:14-16` | agent |
| Design debt: 67 arbitrary Tailwind values (worst `transactions/page.tsx` 16, `Topbar.tsx` 15, `cases/page.tsx` 8), 16 hardcoded hex, 8 inline `style={{}}`, 79 raw px; raw palette classes bypass tokens (`bg-emerald-500`, `text-red-600`, `border-gray-300`, `focus:ring-blue-500`) | `reports/page.tsx:73-76`; `transactions/page.tsx:188,499`; `filings/page.tsx:88,101`; `dashboard/page.tsx:114,158`; `settings/page.tsx:405,434`; `Sidebar.tsx:169` | agent |
| No component library and no primitives (zero Button/Input/Card/Badge/Modal/Table); table `<thead>` duplicated across pages | `package.json`; `dashboard/page.tsx:200-206`; `transactions/page.tsx:231-235` | agent |
| A11y: 12 `aria-*` total, all `aria-required`; 0 `role=`, 0 `aria-label`, 0 `sr-only`, 0 `<caption>`; no `<th scope>`; ~12 of 42 controls unlabeled (30 `htmlFor`); 2 `focus:` styles in all of `src/`; colour-only risk bar and donut; modals have no focus trap or Escape | `cases/page.tsx:142,151`; `signup/page.tsx:99-116`; `filings/page.tsx:88,101`; `transactions/page.tsx:375`; `dashboard/page.tsx:114,202-206` | agent |
| `website/platform/*.html` (169/182/378/134 lines) have zero `fetch`/`XMLHttpRequest`/`localStorage` calls; hardcoded mock data; unreferenced; not in compose | `website/platform/dashboard.html:110,127`; grep | agent |
| `website/js/main.js` (231 lines) is marketing-only; `website/css/` is a separate 4 937-line BEM system; `pages/login.html` and `signup.html` are 13-line stubs | `main.js:1-4`; `css/main.css`, `platform.css`, `admin.css` | agent |
| `DEPLOYMENT.md:473` references `cd website`, but compose's frontend builds `platform-app/Dockerfile` | `docker-compose.yml:48-50` | ✔ verified |

## Documentation overclaim register

| Document claim | Code reality | Evidence |
|---|---|---|
| "✅ Behavioral monitoring … fully implemented, tested, production-ready" | Real z-score logic exists but `screen()` never calls it; the screening path uses `random.uniform` | `main.py:2196-2220` vs `compliance_engine.py:281-294` — Wiki `:1135` |
| "✅ Circuit breaker & degraded mode … graceful degradation routing to human review" | Breaker state changes only via client POST; nothing is wrapped; no degraded routing | `main.py:2381-2546` — Wiki `:1136`, `:461-495` |
| "✅ Webhook events … retry logic (exponential backoff), dead letter queue" | Rows are inserted as pending and never delivered; no HTTP client, no DLQ transition | `main.py:2589-2667` — Wiki `:1137` |
| "✅ Data privacy (GDPR) — DSAR request handling, PII field classification" | DSAR writes one audit row ("we just log it"); classification is a literal dict; no masking | `main.py:2682-2724` — Wiki `:1138` |
| "✅ Audit logging enhancement — Immutable audit trail … chain-of-custody export ready" | No append-only constraint, no hash chain, no read or export endpoint | 15 write sites, no reader — Wiki `:1139` |
| "✅ Docker deployment … multi-stage builds, production-ready configuration" | Single-stage, root, no HEALTHCHECK, plaintext secrets, SQLite primary | Dockerfiles + `docker-compose.yml:11,32-34` — Wiki `:1140` |
| "Production Readiness Score: 8.5/10", "56 API Endpoints", "E2E Tests 8/8", "Docker Services: 2" | 68 routes; 1 e2e file that CI never collects; 3 compose services; blockers listed above | Wiki `:1172-1181` |
| README quickstart: `docker/docker-compose.yml`, `alembic upgrade head`, Prometheus at `:9090`, Redis, worker | Path absent; Alembic not installed; no Prometheus/Redis/worker | `README.md:147-159` |
| "LoRA fine-tuned classifier — DSPy-compiled", "vLLM", "LangChain agentic RAG", "RAGAS", "Celery + Redis", "HashiCorp Vault", "OpenTelemetry + Prometheus + structlog", "Kubernetes + Helm" | None present in `requirements.txt` or the repo | `README.md:107-123`; `requirements.txt` |
