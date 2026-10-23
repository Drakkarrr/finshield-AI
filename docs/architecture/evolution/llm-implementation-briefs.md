# FinShield AI — LLM Implementation Briefs (copy-paste ready)

Everything below is derived from [migration-roadmap.md](./migration-roadmap.md) and cited in [evidence.md](./evidence.md). Each phase brief is **self-contained**: paste one into a fresh agent session and it has enough context to implement without re-discovering the repo.

**How to use**

1. Paste the **Global preamble** at the start of every session.
2. Paste **one phase brief** at a time (P0 first). Do not paste two phases — an agent that tries to do P0+P1 will half-finish both.
3. When a phase lands, run its Validation block yourself. Do not accept "done" without the command passing.
4. For a single slice instead of a phase, use the **Single-slice template** at the bottom.

Line numbers refer to the repo as of commit `91e4de8` (2026-10-23). If they have drifted, tell the agent to re-locate by symbol name rather than trusting the number.

---

## Global preamble (paste first, every session)

```
PROJECT: FinShield AI — an AML/transaction-screening compliance platform at
C:\Users\User\Desktop\upskilling\projects\finshield (Windows, Git Bash).

REAL LAYOUT (the README's "Project Structure" section is aspirational and does NOT exist):
  backend/       FastAPI. backend/app/{main.py (2855 lines, 68 routes), compliance_engine.py,
                 rag_service.py, auth.py, db_models.py, models.py, database.py, seed_rag_data.py}
                 backend/tests/{test_api.py, test_compliance_engine.py}, backend/test_filing_e2e.py
  platform-app/  Next.js 14 App Router + React 18 + TS + Tailwind 3 under src/
                 (app/, components/, contexts/AuthContext.tsx, lib/api.ts, lib/format.ts)
  website/       Static nginx marketing site + a DEAD legacy console at website/platform/*.html
  docker-compose.yml (root), .github/workflows/ci.yml, README.md, FinShield-AI-Wiki.md,
  DEPLOYMENT.md, DOCKER.md

STACK THAT ACTUALLY EXISTS: FastAPI 0.115, SQLAlchemy 2.0 (sync), Pydantic 2.9, psycopg2-binary,
pgvector, python-jose, bcrypt, slowapi, numpy, pytest. Frontend deps are ONLY next/react/react-dom.
There is NO celery, redis, langchain, dspy, torch, transformers, vllm, alembic, opentelemetry,
prometheus, structlog or sentry anywhere. Do not import a library without adding it to
backend/requirements.txt (pinned) or platform-app/package.json first.

HARD RULES FOR ALL WORK IN THIS REPO:
1. Compliance decisions must be DETERMINISTIC and REPRODUCIBLE. Never introduce random.uniform,
   random.randint, uuid-as-identifier-for-decisions, time-of-day or hash-order dependence into any
   scoring, gating or classification path. Existing randomness in compliance_engine.py is a known
   defect being removed, not a pattern to copy.
2. Every decision must carry machine-readable reasons. Any scoring change must emit a structured
   reasons[] (rule id / feature / contribution) that is persisted and returned to the client.
3. Never weaken auth. 64 of 68 routes use Depends(get_current_user) — keep it that way, and add
   auth to any new route unless it is explicitly public (register, login, health).
4. Schema changes go through Alembic migrations once S1.2 exists. Before S1.2, if you must add a
   column, say so explicitly in your summary and note that create_all will NOT apply it to an
   existing database.
5. Do not "fix" documentation by deleting the target-state content in FinShield-AI-Wiki.md.
   Relabel it (Implemented & wired / Built but not wired / Stub / Target). It is the spec.
6. Add or update tests for every behaviour change. The suite currently has 65 passing tests
   (backend/tests/); it must still pass, and your change must add coverage for what you touched.
7. No secrets in committed files. Never write a real credential into any tracked file, including
   .env, docker-compose.yml, tests or fixtures.
8. Style: minimal comments, only where the WHY is non-obvious. No backwards-compatibility shims,
   no feature flags unless the task asks for one, no speculative abstraction. Prefer editing
   existing files over creating new ones.
9. Before reporting done, run the Validation commands listed in the brief and paste real output.
   Never claim tests, lint or CI pass without running them.

DEFINITION OF DONE for any slice: code changed + tests added/updated + validation command run with
output shown + a 3-line summary of what changed and what is still open.
```

---

## P0 — Truth & safety (ship-blocking, no features)

```
PHASE 0 BRIEF — five independent slices. Do them in the order given; each is separately committable.

CONTEXT: This repo's documentation claims production readiness that the code does not support.
Phase 0 removes the four ship-blockers and two latent bugs so later phases can be merged safely.
No new features in this phase.

--- S0.5 (do this first — smallest, unblocks nothing but is trivially safe) ---
Two latent production bugs:
(a) backend/app/main.py: `GET /api/v1/transactions/export` is registered at line ~666, AFTER
    `GET /api/v1/transactions/{tx_id}` at line ~606. FastAPI matches routes in registration order,
    so /export is unreachable — it is captured as tx_id="export". The frontend calls it from
    platform-app/src/app/transactions/page.tsx:98 via window.open(api.exportTransactions(...)).
    FIX: move the /export route above the /{tx_id} route.
(b) backend/app/main.py: `import math` is a FUNCTION-LOCAL import inside score_transaction_behavior
    (line ~2177), but math.sqrt is called at line ~2274 inside a DIFFERENT function
    (update_account_baseline). Any call with >1 transaction raises NameError -> 500.
    FIX: hoist `import math` to module level and delete the local import.
TESTS: add a regression test for each in backend/tests/test_api.py —
  - GET /api/v1/transactions/export returns 200 and a CSV content-type (not a 404/422 tx_id lookup)
  - POST /api/v1/behavioral/update-baseline with two transactions for one account returns 200
VALIDATION: cd backend && APP_ENV=test python -m pytest tests/ -v -k "export or baseline"

--- S0.4 real health probes ---
backend/app/main.py:2830-2845 returns a HARDCODED services map where database, behavioral_ml,
rag_classifier, case_manager and api_gateway are all statically "healthy". Nothing is probed.
DEPLOYMENT.md:386 points an uptime monitor at this endpoint, so monitoring reports green during
a full outage.
DO:
  - Add GET /api/health/live  -> 200 if the process is up (no dependency checks).
  - Add GET /api/health/ready -> probes the primary DB (SELECT 1) and, when app.state.rag_service
    is not None, the RAG Postgres connection. Return 503 with a per-dependency body when any
    probe fails. Keep the existing /api/health shape for compatibility but make its `services`
    map reflect the actual probe results, including "degraded"/"unavailable" states and
    rag_service: "disabled" when app.state.rag_service is None.
  - Add HEALTHCHECK to backend/Dockerfile, platform-app/Dockerfile and website/Dockerfile.
  - In docker-compose.yml add a healthcheck for backend and change frontend's
    `depends_on: backend` to `condition: service_healthy`.
CONSTRAINT: do not make /api/health/live depend on the DB — liveness must not flap on DB blips.
TESTS: test that ready returns 503 when the DB is unreachable (monkeypatch the session to raise).
VALIDATION: cd backend && APP_ENV=test python -m pytest tests/ -v -k health
            docker compose config   (must still be valid)

--- S0.2 secrets hygiene ---
FACTS: `backend/.env` IS TRACKED IN GIT (git ls-files confirms) even though .gitignore:26 lists
.env — it was never git rm --cached. docker-compose.yml hardcodes POSTGRES_PASSWORD=finshield_secret
(:11), a credential-bearing RAG_DATABASE_URL (:33) and JWT_SECRET_KEY=your-secret-key-change-in-production
(:34), and publishes Postgres on 5432:5432 (:8). README.md:143 tells users to `cp .env.example .env`
but NO .env.example exists anywhere in the repo.
DO:
  1. git rm --cached backend/.env  (leave the file on disk; do NOT delete it — it is the user's
     local config). Then confirm `git ls-files | grep -E "\.env$"` is empty.
  2. Create .env.example at the REPO ROOT and backend/.env.example listing every key the code
     actually reads: APP_ENV, DEBUG, APP_PORT, DATABASE_URL, RAG_DATABASE_URL,
     RAG_USE_SENTENCE_TRANSFORMERS, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES,
     RATE_LIMIT_PER_MINUTE, CORS_ORIGINS, DEFAULT_SIGNUP_CREDITS, POSTGRES_USER,
     POSTGRES_PASSWORD, POSTGRES_DB. Use obvious placeholders only.
  3. Rewrite docker-compose.yml to use ${VAR} interpolation for POSTGRES_PASSWORD,
     POSTGRES_USER, POSTGRES_DB, DATABASE_URL, RAG_DATABASE_URL and JWT_SECRET_KEY, with
     ${VAR:?err} syntax for the ones that must be set so compose fails loudly instead of
     silently using a weak default. Change the postgres port mapping to "127.0.0.1:5432:5432".
  4. backend/app/auth.py:22 currently falls back to secrets.token_urlsafe(32) when
     JWT_SECRET_KEY is unset, which silently invalidates every token on restart and breaks
     multi-replica deploys. Change it to raise a clear RuntimeError at import/startup when
     JWT_SECRET_KEY is unset AND APP_ENV != "test". Tests must still work (they use APP_ENV=test).
  5. Do NOT rewrite git history. Report it as an open question for the user instead — it is a
     visibility decision, not a technical one.
VALIDATION: git ls-files | grep -E "\.env$|\.db$"        (must be empty)
            docker compose config                          (must succeed with a test .env)
            unset JWT_SECRET_KEY && python -c "import backend.app.auth" (must fail loudly, non-test env)

--- S0.3 fix CI ---
FACTS: .github/workflows/ci.yml:81 and :84 run `docker build -t finshield-backend ./backend` and
`docker build -t finshield-platform ./platform-app`, but backend/Dockerfile:12,16 do
`COPY backend/requirements.txt .` / `COPY backend/ ./` and platform-app/Dockerfile:7,11 do
`COPY platform-app/package*.json ./` / `COPY platform-app/ ./`. Those COPY paths are root-relative,
so building from a subdirectory context CANNOT succeed. The job only runs on push to main, so it
has never gated a PR. ci.yml:112 sets continue-on-error: true on the safety scan. CI uses
Python 3.13 (:10,:28) while the image is python:3.11-slim. backend/test_filing_e2e.py sits OUTSIDE
tests/ so `pytest tests/` (:38) never collects it, and it needs a live server at localhost:8091.
DO:
  1. Fix both docker build commands to use repo-root context with -f:
     docker build -f backend/Dockerfile -t finshield-backend .
     docker build -f platform-app/Dockerfile -t finshield-platform .
     Make the docker-build job run on pull_request too, not only on push to main.
  2. Pin CI Python to 3.11 to match backend/Dockerfile:2.
  3. Remove continue-on-error from the security scan; switch to `pip-audit -r requirements.txt`
     (or keep safety) and let it fail the build. Add `npm audit --audit-level=high` for
     platform-app and a secret-scanning step (gitleaks or trufflehog).
  4. Add backend lint + typecheck: add pinned `ruff` and `mypy` to a new
     backend/requirements-dev.txt, create minimal ruff.toml and mypy config (start permissive:
     ignore_missing_imports = true, no strict mode), and wire both into CI. Fix only the errors
     that are trivial; add per-file ignores for the rest and list them in your summary as debt.
  5. Add coverage: pytest-cov, run `pytest --cov=app --cov-report=term-missing`, and set
     --cov-fail-under to the CURRENT measured value rounded down (measure first, then set the
     floor — do not invent a number).
  6. Add `npx tsc --noEmit` to the frontend job.
  7. Move backend/test_filing_e2e.py to backend/tests/e2e/test_filing_e2e.py, mark it
     @pytest.mark.e2e, and configure pytest.ini so the default run excludes e2e
     (add `-m "not e2e"` to addopts or use markers). Add a separate optional CI job for it that
     starts the compose stack.
VALIDATION: locally run the exact commands CI runs, and paste output:
  cd backend && APP_ENV=test python -m pytest tests/ -v --cov=app -m "not e2e"
  cd backend && ruff check . && mypy app
  cd platform-app && npx tsc --noEmit && npm run lint && npm run build
  docker build -f backend/Dockerfile -t finshield-backend .
  docker build -f platform-app/Dockerfile -t finshield-platform .
  python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"

--- S0.1 reconcile documentation with code ---
FACTS (all verified): README.md:147-159 documents `docker compose -f docker/docker-compose.yml`
(no docker/ directory exists), "API + worker + Postgres/pgvector + Redis + dashboard" (there is no
worker and no Redis), `alembic upgrade head` (Alembic is not installed and no migration exists —
also repeated at FinShield-AI-Wiki.md:979), `python -m rag.ingest_policies --seed` (no rag package
at repo root; the real seeder is backend/app/seed_rag_data.py) and Prometheus at :9090 (none).
README.md:199-222 lists ~21 directories that do not exist. README.md:107-123 tech-stack table names
Celery, Redis, LangChain, DSPy, Llama/LoRA/PEFT, vLLM, RAGAS, OpenTelemetry, Prometheus, structlog,
Kubernetes+Helm and Vault — NONE are in backend/requirements.txt or the repo.
FinShield-AI-Wiki.md:1129-1140 marks behavioral monitoring, circuit breakers, webhook retry+DLQ,
GDPR/DSAR and immutable audit as "fully implemented, tested, production-ready"; the code shows the
behavioral monitor is never called by screen(), the breaker wraps no call, webhook rows are never
delivered, DSAR writes one audit row (main.py:2689-2690 comment: "we just log it"), and audit_logs
has no append-only constraint and no read endpoint. Wiki:1181 claims "Production Readiness Score:
8.5/10"; :1172 claims 56 endpoints (actual 68); :1175 claims 8/8 E2E tests (actual: one e2e file
CI never collects); :1177 claims 2 docker services (actual 3). Wiki:1187 is a resume line naming
Celery, LangChain, LoRA, DSPy, vLLM and Kubernetes.
DO:
  1. Fix README quickstart so a fresh clone following it VERBATIM reaches a running stack:
     correct compose path, remove alembic/migrations step until S1.2 lands (or replace with the
     real init step), correct the seeding command, remove the Prometheus line, remove Redis/worker
     from the service list.
  2. Replace README's "Project Structure" tree with the ACTUAL tree (backend/, platform-app/,
     website/, docs/, docker-compose.yml, .github/). Move the aspirational tree into a clearly
     labelled "Target structure (not yet built)" subsection, or delete it.
  3. Annotate the README tech-stack table with a Status column: Implemented / Target. Do not delete
     rows — the target stack is the roadmap.
  4. In FinShield-AI-Wiki.md §21, convert the "✅ Implemented" list into a table with a status
     column using exactly these labels: `Implemented & wired`, `Built but not wired`, `Stub`,
     `Absent`. Apply these corrections: behavioral monitoring = Built but not wired (real z-score
     at main.py:2196-2220, never called by screen()); circuit breaker = Built but not wired (state
     changes only via client POST, wraps no call); webhook events = Stub (rows inserted as pending,
     never delivered, no DLQ transition); GDPR/DSAR = Stub (writes one audit row; PII
     classification is a literal dict at main.py:2713-2724); audit logging = Built but not wired
     (15 write sites, no immutability constraint, no read/export API, decisions not audited);
     Docker = Implemented with blockers (single-stage, root user, no HEALTHCHECK, plaintext
     secrets, SQLite primary).
  5. Correct the §22 statistics table to measured values and REMOVE the "Production Readiness
     Score: 8.5/10" line, replacing it with a short honest readiness statement that points at
     docs/architecture/evolution/migration-roadmap.md.
  6. Move the §23 resume line into a clearly labelled "Target-state summary (aspirational)"
     heading, or rewrite it to describe only what exists.
  7. DEPLOYMENT.md: mark every section describing Railway/Vercel/Neon/PayMongo/Resend/Sentry/
     UptimeRobot as PROPOSED, fix `SECRET_KEY` -> `JWT_SECRET_KEY` (:314-334), and replace the
     "run migrations" step (:51-56) with the real init_db() call plus a note that Alembic is not
     yet adopted.
  8. Add a "Documentation status" note at the top of README.md and FinShield-AI-Wiki.md linking to
     docs/architecture/evolution/ (this folder) as the authoritative gap analysis.
CONSTRAINT: do NOT delete target-state content. Relabel it. Do not invent new claims.
VALIDATION: grep -rn "alembic\|docker/docker-compose\|localhost:9090\|8.5/10" README.md FinShield-AI-Wiki.md
            (every remaining hit must be inside a clearly-labelled target/proposed section)
            Then: create a fresh clone in a temp dir and follow the README quickstart literally.
            Report each step's result. Any step that fails must be fixed, not annotated away.

PHASE 0 OVERALL VALIDATION (run all, paste output):
  git ls-files | grep -E "\.env$|\.db$"                    -> empty
  cd backend && APP_ENV=test python -m pytest tests/ -v    -> all pass, including new tests
  docker compose config                                     -> valid
  docker build -f backend/Dockerfile -t fs-be .             -> succeeds
  docker build -f platform-app/Dockerfile -t fs-fe .        -> succeeds
```

---

## P1 — Data foundation

```
PHASE 1 BRIEF — prerequisite for every feature phase. Requires decisions D6 (Postgres primary: YES)
and, before S1.4, nothing else. Do NOT start P2 until P1 validation passes.

--- S1.5 remove the in-memory idempotency cache (do first, trivial) ---
backend/app/compliance_engine.py:37 keeps a process-local dict (written at :161) for idempotency.
It never expires (memory leak), is lost on restart, is wrong across replicas, and duplicates the
real DB-level check at backend/app/main.py:454-473 (unique idempotency_key + user_id lookup that
returns the persisted result).
DO: delete the engine-level cache and its lookup/write; keep the DB layer as the single source of
truth. Update the engine unit tests that assert on the cache
(backend/tests/test_compliance_engine.py has idempotency tests) so they assert the DB behaviour
instead, or remove them if they are now covered by test_api.py.
VALIDATION: cd backend && APP_ENV=test python -m pytest tests/ -v -k idempot

--- S1.1 Postgres as the primary database ---
FACTS: docker-compose.yml:32 sets DATABASE_URL=sqlite:///./finshield.db for the backend container,
while :5 runs pgvector/pgvector:pg16 and :33 points ONLY the RAG store at Postgres. So all 14
primary tables live in a SQLite file inside a container volume. backend/app/database.py:12-15
picks SQLite when APP_ENV=test, else DATABASE_URL, defaulting to sqlite:///./finshield.db.
This blocks RLS/tenancy, append-only triggers, concurrent workers and pgvector joins.
DO:
  1. Change docker-compose.yml so backend's DATABASE_URL points at the postgres service
     (postgresql://finshield:${POSTGRES_PASSWORD}@postgres:5432/finshield). RAG_DATABASE_URL may
     point at the same database.
  2. Keep SQLite ONLY for APP_ENV=test so the existing 65 tests stay fast. Add a separate CI job
     that runs the same suite against Postgres (services: postgres with pgvector image) to catch
     dialect drift — this is important because pgvector types and JSON handling differ.
  3. Write a one-off script backend/scripts/sqlite_to_postgres.py that copies rows from an existing
     dev SQLite file into Postgres (table-by-table, ordered by FK dependency). It is a dev
     convenience, not a migration framework.
  4. Verify database.py:19 connect_args logic still applies only to SQLite.
VALIDATION: docker compose up -d && docker compose exec backend python -c \
  "from app.database import engine; print(engine.url)"    -> postgresql
  cd backend && APP_ENV=test python -m pytest tests/ -v   -> SQLite suite still green
  CI Postgres job green.

--- S1.2 Alembic migrations ---
FACTS: schema is created by Base.metadata.create_all (backend/app/database.py:36-38 init_db,
:44 reset_db, backend/app/rag_service.py:153, and tests). create_all CANNOT alter an existing
table, so any new column silently no-ops on a live DB. `alembic` is not in requirements.txt.
The 3 RAG tables (compliance_documents, sanctions_entries, precedent_decisions) are declared on a
SEPARATE declarative_base() at rag_service.py:102-142 — this must be unified or handled as a
second metadata target, otherwise Alembic will not see them.
DO:
  1. Add pinned `alembic` to backend/requirements.txt.
  2. Unify metadata: have rag_service.py import the shared Base from database.py (preferred) so
     one Alembic env sees all 17 tables. If you cannot unify without breaking the RAG service's
     separate-DB capability, configure alembic/env.py with both metadata objects and document why.
  3. `alembic init` inside backend/, configure env.py to read DATABASE_URL from the same place
     database.py does, and autogenerate a baseline migration matching the current schema exactly.
  4. Make create_all TEST-ONLY: init_db() should run migrations (or be a no-op) in non-test envs.
     Add `alembic upgrade head` to the backend container entrypoint (create
     backend/entrypoint.sh, make it executable, set it as ENTRYPOINT before the uvicorn CMD).
  5. Add a CI step that runs `alembic upgrade head` against a fresh Postgres, then
     `alembic downgrade -1`, then `upgrade head` again.
CONSTRAINT: the baseline migration must be reproducible from an empty database. Do not hand-edit
autogenerated operations without checking they match db_models.py.
VALIDATION: docker compose up -d postgres && \
  docker compose run --rm backend alembic upgrade head && \
  docker compose run --rm backend alembic downgrade -1 && \
  docker compose run --rm backend alembic upgrade head
  cd backend && APP_ENV=test python -m pytest tests/ -v

--- S1.3 fix async/sync database access ---
FACTS: all 68 handlers in backend/app/main.py are `async def` but execute BLOCKING synchronous
SQLAlchemy inside them, so every request stalls the uvicorn event loop. Throughput is effectively
serialised and the worker phase (P4) will not fix it.
DO: pick ONE convention and apply it repo-wide — do not mix:
  Option A (lower risk, recommended): change handlers that ONLY do DB work from `async def` to
    `def`. FastAPI then runs them in a threadpool. Keep `async def` only for handlers that
    genuinely await (the RAG service if it is async, httpx calls).
  Option B: move to an async engine + AsyncSession throughout (asyncpg driver), which is a larger
    change touching every query and the test fixtures.
  State which you chose and why in your summary. Apply it consistently, including the auth
  dependency (backend/app/auth.py:59-113) which also does blocking DB reads.
  Raise the SQLAlchemy pool size / add pool_pre_ping for Postgres in database.py.
VALIDATION: write backend/tests/test_concurrency.py: fire 50 concurrent screening requests with
  httpx.AsyncClient + asyncio.gather against the ASGI app and assert (a) all succeed, (b) total
  wall time is materially better than serial. Print both timings. Run the full suite.

--- S1.4 runtime config service ---
FACTS: the product's core claim is "config-first, all runtime, no redeploy" (README.md:228-242).
Reality: THRESHOLD_WIRE=10000.0, THRESHOLD_INTERNATIONAL=50000.0, VELOCITY_WINDOW_TXS=5 are module
constants (compliance_engine.py:25-27); risk weights are inline literals (:317-325); decision bands
are inline (:355-360); credit prices are inline (main.py:116-118); PLANS is a hardcoded list
(main.py:874). The ONE real override layer is per-user rule_configs (db_models.py:184-209 ->
main.py:476-479 -> compliance_engine.py:168-177 is_enabled()/param()), which IS wired and editable
from the admin UI via PATCH /api/v1/rules/{rule_id} (main.py:1377). RuleConfig.priority, .version,
.effective_from and .effective_to are written but NEVER READ by the engine. VELOCITY_WINDOW_TXS is
declared and never used.
DO:
  1. Add an Alembic migration creating `settings` (key, value JSON, scope, updated_by, updated_at)
     and `feature_flags` (key, enabled, scope, updated_by, updated_at) tables.
  2. Add backend/app/config_service.py with typed accessors (get_threshold(name, default),
     get_flag(name, default)), an in-process TTL cache (30s) and explicit invalidation on write.
  3. Migrate these values into settings with their current literals as seed defaults: the two
     amount thresholds, the behavioral trigger thresholds (0.5 cold-start / 0.65 warm from
     main.py:2196-2220), the risk blend weights (compliance_engine.py:317-325), the decision bands
     (:355-360), credit prices (main.py:116-118) and PLANS (main.py:874).
  4. Make the engine honour RuleConfig.priority (execution order) and effective_from/effective_to
     (skip rules outside their window). Either implement version history properly or remove the
     column — do not leave a written-but-unread field.
  5. Add GET/PUT /api/v1/settings and GET/PUT /api/v1/flags endpoints, ADMIN-ONLY. NOTE: RBAC does
     not exist yet (S3.1) — gate them behind get_current_user for now and add a
     `# TODO(S3.1): require_role("admin")` marker plus an entry in your summary listing exactly
     which routes need role gating later.
  6. Audit-log every settings/flag change with before-value, after-value and actor id, using the
     existing AuditLog pattern (see the 15 write sites in main.py).
  7. Delete VELOCITY_WINDOW_TXS or implement the velocity rule it names. Say which.
VALIDATION: change a threshold via PUT /api/v1/settings, then screen a transaction that crosses the
  NEW threshold and assert the decision changed with no process restart, and that an audit_logs row
  records old/new/actor. Full suite green.

PHASE 1 OVERALL VALIDATION:
  cd backend && APP_ENV=test python -m pytest tests/ -v          -> all green
  docker compose up -d && docker compose exec backend alembic current  -> head
  docker compose exec backend python -c "from app.database import engine; print(engine.url)"
```

---

## P2 — Make detection real

```
PHASE 2 BRIEF — the product core. Requires P1 done and decisions D1 (classifier), D4 (embeddings)
and D12 (list data) ruled on. If they are not ruled on, implement the RECOMMENDED option from
docs/architecture/evolution/decision-map.md and say so explicitly in your summary.

Recommended defaults if unrulled: D1 = deterministic classical model behind a RiskModel protocol
(NO LLM, NO torch — CPU-only, explainable); D4 = local sentence-transformers all-MiniLM-L6-v2
(keeps the local-first promise) with the hash embedder retained only as an explicitly-labelled
degraded fallback; D12 = OFAC SDN import behind a ListProvider interface.

--- S2.1 wire the behavioral monitor into screening ---
FACTS: a real z-score anomaly detector with cold-start handling exists at backend/app/main.py:2196-2220
(z_score = abs(amount - avg)/std_dev; anomaly_score = min(1.0, z/3.0); thresholds 0.5 cold-start /
0.65 warm), backed by the account_baselines table (db_models.py:318-352) with a real recompute at
main.py:2267-2310. screen() NEVER calls it. Instead compliance_engine.py:281-294 does amount
thresholds plus `score += random.uniform(0, 0.15)` (:293). Baselines are keyed on `sender_name` as
an account proxy (main.py:2248).
DO:
  1. Extract the behavioral logic from main.py into backend/app/behavioral.py as a pure, testable
     function/class taking (account_id, amount, baseline stats) and returning (score, reasons,
     is_cold_start). Reuse it from BOTH main.py's endpoints and the engine — no duplicated logic.
  2. Inject a baseline lookup into ComplianceEngine.screen() stage 4, replacing the amount-
     threshold + random.uniform implementation. The engine must receive baselines via a
     repository/callback passed in from main.py (do not give the engine a DB session directly).
  3. Key baselines on the real account_id, not sender_name. Add a migration if the column or its
     uniqueness constraint needs to change.
  4. Emit reasons: e.g. {source: "behavioral", feature: "amount_z_score", value: 3.2,
     contribution: 0.42, cold_start: false}. Persist them with the transaction and return them in
     the response so the UI can show the trail.
  5. Delete random.uniform from compliance_engine.py:293 entirely.
VALIDATION: test that (a) an account with a stable low-amount history that suddenly sends 20x its
  mean flags as behavioral with a z-score reason, (b) the same amount for a cold-start account
  (< the configured history window) does NOT flag and the reason says cold_start: true,
  (c) screening the same payload twice yields identical output.

--- S2.2 deterministic, explainable scoring ---
FACTS: _ml_classify (compliance_engine.py:297-304) has the docstring "Simulate ML classification
via RAG + LoRA" and returns random.uniform confidences. Risk blend at :307-327 uses literal
weights. Decision bands at :355-360 are literals. compliance_engine.py:147 generates
transaction_id as f"TX-{random.randint(10000,99999)}" (later overwritten with the DB UUID at
main.py:537). Two identical transactions can get different decisions — indefensible in AML.
DO:
  1. Remove ALL randomness from the screening path (grep for random in compliance_engine.py and
     main.py and eliminate every hit that affects a decision or identifier).
  2. Move weights and bands into the config service (S1.4).
  3. Define a single structured decision object: {decision, risk_score, reasons[], rule_hits[],
     behavioral, rag_context, model_version, degraded, screened_at}. Persist it on the transaction
     and return it from GET /api/v1/transactions/{id}.
  4. Keep the rule-action precedence gate (compliance_engine.py:332-361) EXACTLY as designed — it
     is the best-designed piece in the repo. Only refactor around it, do not change its semantics.
     Add tests that pin its behaviour (rule action overrides score band).
VALIDATION: screen the same payload 20 times in a loop; assert all 20 responses are byte-identical
  apart from timestamps/ids. Assert every decision has a non-empty reasons[] when not auto-approved.

--- S2.3 real sanctions and PEP data ---
FACTS: SANCTIONED_ENTITIES = {"globalremit","darkfund","terrorfin"} and a 3-entry PEP set at
compliance_engine.py:22-23, matched by exact lowercase membership at :185 and :198. High-risk
countries are a 5-element set at :24. No aliases, no fuzzy matching, no list versioning.
DO:
  1. Migration: tables sanctions_entries and pep_entries with (id, source, list_version,
     primary_name, aliases JSON, entity_type, country, effective_from, effective_to, raw JSON)
     and a high_risk_countries table.
  2. backend/app/lists/ provider interface (ListProvider.load() -> entries with source+version)
     and an OFAC SDN CSV/JSON importer implemented as a callable task/script with a --dry-run
     mode. Include a small committed FIXTURE (a handful of real-format rows) for tests — do NOT
     commit the full SDN file.
  3. Matching: normalise (case, punctuation, transliteration-lite) then exact match, then fuzzy
     (token-set ratio or Jaro-Winkler) with a configurable threshold from the config service.
     Record on every hit: matched entry id, list source, list_version, match type and score.
  4. Replace the 3-element sets in compliance_engine.py with a lookup through the provider. Keep
     the old names as a TEST FIXTURE only, never as production data.
  5. Add an endpoint to report list freshness (last successful import per source) and surface it
     in /api/health/ready as a degraded signal when stale beyond a configurable window.
VALIDATION: load the fixture, screen a transaction naming a known ALIAS of a fixture entry, assert
  a hit that names the entry id, list_version and match score. Assert an unrelated name does not
  hit. Assert the legacy three names still hit via the fixture.

--- S2.4 enable RAG end-to-end ---
FACTS: retrieval is real pgvector cosine SQL (rag_service.py:276-278,305-307,343-345, Vector type
:23/:115/:129/:141, CREATE EXTENSION :152) with NO SQLite fallback. Embeddings are MD5
feature-hashing into 384 buckets (:52-73; docstring :58-59 admits "lexical overlap"). The real
SentenceTransformer("all-MiniLM-L6-v2") path (:36-38) is behind RAG_USE_SENTENCE_TRANSFORMERS
defaulting to "false" AND sentence-transformers is not in requirements.txt, so it can never
activate. The service is constructed only when RAG_DATABASE_URL starts with "postgresql"
(main.py:139-150): compose sets it (:33) so RAG is live in Docker; local .env does not, so all four
/api/v1/rag/* routes return 503 (:2760,:2778,:2795,:2812). seed_rag_data.py is __main__-only
(:190-197) and nothing invokes it. When enabled, RAG flips approved->flagged and floors risk at 0.5
(main.py:500-503) but can never escalate to blocked and never lowers a decision.
DO:
  1. Add pinned sentence-transformers (and its torch CPU wheel — use the CPU index URL so the image
     does not pull CUDA) to requirements.txt, OR implement D4 option B (a separate embedding
     service) if you prefer to keep the API image slim. State which.
  2. Make the embedder explicit and versioned: store embedding_model and embedding_dim on the RAG
     tables; refuse to search when the stored model/dim does not match the configured one, and
     return a clear error telling the operator to re-embed.
  3. Run seeding automatically: either from app startup when the RAG tables are empty, or as a
     compose one-shot init service. seed_rag_data.py must stay idempotent (it already checks
     counts at :17-24).
  4. Replace the silent 503s with an honest degraded signal: when app.state.rag_service is None,
     /api/health/ready reports rag: "disabled", screening continues with a
     {source:"rag", reason:"unavailable", degraded:true} entry in reasons[], and the response
     exposes rag_degraded so the UI can show it. Log ONE explicit WARN at startup, not per request.
  5. Keep the hash embedder ONLY as a labelled fallback that sets degraded=true. It must never be
     silently treated as semantic retrieval.
  6. Decide and document whether retrieval may LOWER a decision. Today it is asymmetric (can only
     escalate approved->flagged). Either keep that asymmetry deliberately with a comment explaining
     why, or make it symmetric. Do not leave it accidental.
  7. Add backend/tests/test_rag.py marked @pytest.mark.postgres (skipped without a Postgres URL)
     that seeds a fixture corpus and asserts ranked retrieval.
VALIDATION: with RAG_DATABASE_URL set, POST /api/v1/rag/search-documents returns ranked results;
  screening a transaction whose memo paraphrases a seeded policy document returns a persisted
  rag_context (db_models.py:100) and a rag entry in reasons[]. With RAG_DATABASE_URL unset,
  screening still succeeds and reports rag degraded.

--- S2.5 versioned scoring model behind an interface ---
FACTS: README.md:107-123 and Wiki §18 promise a DSPy-compiled LoRA-tuned Llama classifier served by
vLLM. There is no model, no inference client, and no torch/transformers/dspy/vllm in
requirements.txt. _ml_classify is random.uniform (see S2.2).
DO (implement D1 option A unless told otherwise):
  1. backend/app/models_registry/risk_model.py: a Protocol `RiskModel` with
     score(features: dict) -> ModelResult(label, confidence, reasons, model_version).
  2. Implement v1 as a deterministic classical model. If there is NO labelled dataset (the likely
     case), implement a transparent, hand-weighted logistic-style scorer over named features
     (amount, amount_z_score, rule_hit_count, country_risk, counterparty_risk, rag_signal,
     velocity) with weights loaded from the config service, and expose each feature's contribution
     as a reason. Design it so a trained sklearn model can replace it without touching callers.
     Do NOT train or ship a model you have no data to evaluate.
  3. Migration: model_versions table (id, name, version, kind, status[shadow|active|retired],
     params JSON, feature_list JSON, metrics JSON, model_card JSON, created_by, created_at,
     activated_at). Only ONE active version per kind.
  4. Shadow mode: when a version has status=shadow, score with it in parallel, persist its output
     on the transaction (shadow_result JSON), and DO NOT let it affect the decision. Promotion is
     a config/DB change, never a deploy.
  5. Persist model_version on every transaction decision so any historical decision can be
     reproduced and attributed.
  6. Model card content: intended use, training/derivation basis, feature list, known limitations,
     validation results, review/approval field. Even for the hand-weighted v1, fill it in honestly
     ("expert-defined weights, no training data").
VALIDATION: test that (a) exactly one version can be active, (b) a shadow version's output is
  persisted but does not change the decision, (c) promoting a version changes subsequent decisions,
  (d) every persisted decision names its model_version.

--- S2.6 circuit breakers that protect real calls ---
FACTS: the three-state machine and CircuitBreaker table are real (main.py:2443-2445 opens on
threshold, :2510 half-open probe, table db_models.py:275) but transitions are driven ONLY by client
HTTP POSTs (/record-failure :2429, /record-success :2469, /check-half-open :2510). No breaker wraps
any call. It monitors model_server, pgvector, redis, notification_service — none of which the code
invokes. Wiki §8 (:461-495) promises degraded-mode routing to human review and "never silently
auto-approves"; unimplemented.
DO:
  1. backend/app/resilience.py: a breaker decorator/context manager (failure_threshold,
     recovery_timeout, half_open_max_calls) persisting state in the existing circuit_breakers table.
  2. Wrap the REAL dependencies: RAG retrieval, the embedding call, the risk model call, and (from
     P4) webhook delivery. Delete the client-driven /record-failure and /record-success endpoints
     OR keep them admin-only for manual reset with a clear name (/reset) — do not leave state
     controllable by any authenticated caller.
  3. Degraded routing: when a breaker is open, screening must still succeed, must set
     degraded=true with a reason naming the open dependency, and must NOT auto-approve — route to
     in_review (human). This is the Wiki's central resilience promise; implement it literally.
  4. Expose real breaker state in /api/health/ready and add a GET endpoint the dashboard can use.
VALIDATION: kill the RAG Postgres (or point RAG_DATABASE_URL at a dead port), screen a transaction,
  assert: 200 response, decision is in_review (NOT approved), degraded=true with the dependency
  named, breaker state is open, and after recovery_timeout a half-open probe succeeds and closes it.

--- S2.7 evaluation harness ---
FACTS: README.md:279-289 documents tests/eval/eval_classifier.py, eval_behavioral.py, eval_rag.py
and locust load tests. NONE exist (zero hits for precision/recall/RAGAS/locust). Without this,
S2.5 is unshippable and every threshold change is unmeasured.
DO:
  1. backend/tests/eval/scenarios.json: a labelled fixture set of >=40 realistic transaction
     scenarios with expected dispositions (approve/flag/block) and the reason category that should
     drive each. Cover: obvious sanctions alias, PEP, threshold crossings just above/below,
     high-risk country, behavioral anomaly on a warm account, cold-start account, benign high-value
     with clean history, RAG policy match, and combinations where the precedence gate decides.
  2. backend/tests/eval/run_eval.py producing precision, recall, F1 and false-positive rate per
     stage (rules / behavioral / rag / model / final gate) plus a confusion matrix, printed as a
     table and written to a JSON report.
  3. Retrieval quality metrics for RAG (hit@k, MRR over the fixture corpus). Full RAGAS is optional
     — do not add a heavy dependency for it unless it earns its place.
  4. Wire into CI as a SCHEDULED job (nightly) and as a manual workflow_dispatch, NOT per-PR.
     Fail the job if any metric regresses beyond a recorded baseline stored in the repo.
VALIDATION: python -m tests.eval.run_eval  prints the table and exits non-zero if a metric drops
  below the committed baseline. Then deliberately break a threshold and confirm the harness catches it.

PHASE 2 OVERALL VALIDATION:
  cd backend && APP_ENV=test python -m pytest tests/ -v -m "not e2e and not postgres"
  python -m tests.eval.run_eval
  grep -rn "random\." backend/app/compliance_engine.py   -> no decision-affecting hits
  Screen one payload twice and diff the JSON (ignoring ids/timestamps) -> identical
```

---

## P3 — Governance & regulatory

```
PHASE 3 BRIEF — requires P1 (Alembic) done and decisions D3 (tenancy) and D9 (secrets) ruled on.
Recommended defaults if unrulled: D3 = shared schema + tenant_id + Postgres RLS; D9 = platform
secret store, NOT Vault.

--- S3.1 RBAC ---
FACTS: User has NO role column (db_models.py:22). There is no require_admin dependency. Every
authenticated user can call circuit-breaker admin (main.py:2429-2510), DSAR (:2682) and webhook
dispatch (:2589). The frontend UserProfile has no role field (platform-app/src/lib/api.ts:48-68) and
Sidebar uses `user` for display only (Sidebar.tsx:105).
DO:
  1. Migration: add `role` to users with an enum/check constraint: analyst, investigator,
     supervisor, admin. Default for existing rows: admin (single-user dev reality) — and note this
     in your summary as something to revisit before multi-user launch.
  2. backend/app/auth.py: add require_role(*roles) returning a FastAPI dependency that raises 403.
  3. Apply it: settings/flags (S1.4), circuit-breaker routes, webhook dispatch/management, DSAR,
     user management, rule creation/deletion, transaction DELETE, case DELETE, filing DELETE.
     Investigators/analysts keep read + case work; supervisors approve/override; admins configure.
     Write the matrix as a table in your summary AND as a test.
  4. Return role from GET /api/auth/me and add it to UserProfile in lib/api.ts.
  5. Add admin user-management routes (list users, change role, deactivate) — these do not exist
     today despite README.md:261 documenting /api/v1/admin/users.
VALIDATION: an analyst token gets 403 on breaker/DSAR/settings routes and 200 on case routes; a test
  asserts the full permission matrix; the existing 65 tests still pass (update fixtures for roles).

--- S3.2 immutable, queryable audit trail ---
FACTS: 15 AuditLog write sites exist (main.py:204,248,344,1024,1098,1163,1407,1643,1973,2103,2147,
2447,2490,2532,2692) but there is NO DB constraint preventing UPDATE/DELETE, no hash chaining, and
NO endpoint to read audit logs — the data is written and never exposed. Screening DECISIONS are not
audited at all (only logger.info at main.py:565). Wiki:1139 claims "Immutable audit trail ...
chain-of-custody export ready".
DO:
  1. Migration: add prev_hash and entry_hash columns to audit_logs; add DB triggers (or revoke
     UPDATE/DELETE from the app role) making the table append-only. Provide the SQL as a migration
     op.execute() so it is versioned.
  2. Hash chain: entry_hash = sha256(prev_hash || canonical_json(entry)). Write a verify_chain()
     utility and a scheduled verification task (P4.3) that alerts on a break.
  3. Audit every screening DECISION: inputs (redacted per S3.3), rule hits, behavioral result, RAG
     context summary, model version, final decision, degraded flag, actor/api-key id.
  4. Add GET /api/v1/audit (admin/supervisor only, filterable by actor/entity/type/date, paginated)
     and GET /api/v1/audit/export producing a signed chain-of-custody bundle (JSONL + signature +
     chain verification result).
  5. Document retention for audit_logs and align it with the SAR 5-year obligation.
VALIDATION: an attempted UPDATE or DELETE on audit_logs fails at the DB level; tampering with one
  row makes verify_chain() fail and the export reports it; a screening produces an audit entry
  naming the model_version; the export verifies independently.

--- S3.3 privacy: DSAR, erasure, PII masking ---
FACTS: POST /privacy/dsar (main.py:2682) only writes an AuditLog row — the comment at :2689-2690
says "we just log it". GET /privacy/pii-classification (:2708) returns a hardcoded dict literal
(:2713-2724). There is NO PII masking or field-level redaction anywhere (zero hits) and no DSAR
entity.
DO:
  1. Migration: privacy_requests table (id, subject_ref, type[access|erasure|rectification],
     status, received_at, due_at, completed_at, handled_by, outcome JSON, legal_basis_notes).
  2. Access request: collect the subject's data across ALL tables (users, transactions, cases,
     case_comments, case_notes, filings, notifications, api_keys, audit_logs) into a structured
     export. Mask/redact fields the requester is not entitled to.
  3. Erasure: delete or pseudonymise personal data WHILE PRESERVING what regulation requires —
     filings and audit entries must survive. Record exactly what was erased, what was retained and
     the legal basis for retention. This balancing is the whole point; do not implement a blanket
     delete.
  4. PII classification from config (S1.4), not a literal dict; apply masking in API responses for
     non-privileged roles (e.g. mask account numbers and names for analyst role per the matrix).
  5. Deadline tracking: due_at computed from the configured window, surfaced in the dashboard and
     picked up by the P4.3 scheduled sweep.
VALIDATION: an access request produces a complete export; an erasure request removes personal data
  while a filing and its audit entries survive, with the retention reason recorded; a masked role
  cannot read unmasked account numbers.

--- S3.4 multi-tenancy (only after D3 is ruled) ---
FACTS: zero occurrences of "tenant" in the backend. Isolation is per-USER row filtering
(e.g. main.py:455,583,1934,2247,2624). Wiki:823-833 specifies per-tenant Postgres SCHEMAS;
:981 mentions an unused rls_policies.sql placeholder. 14 tables need a tenant dimension.
DO (D3 option A unless told otherwise):
  1. Migration adding tenant_id (NOT NULL, FK to a new tenants table) to every owned table:
     users, api_keys, transactions, cases, case_comments, case_notes, filings, audit_logs,
     notifications, notification_preferences, rule_configs, circuit_breakers, webhook_events,
     account_baselines, settings, feature_flags, model_versions, sanctions/pep entries if
     tenant-scoped. Backfill existing rows to a default tenant.
  2. Postgres RLS: enable on each table with a policy keyed on current_setting('app.tenant_id').
     Set the session variable per request in a dependency/middleware. Ship the policies as a
     versioned migration (this is what rls_policies.sql was a placeholder for).
  3. Application-level guard as defence in depth: keep the existing filter(...) pattern but scope
     by tenant_id AND user_id.
  4. Scope API keys, settings, feature flags, rule configs and model versions per tenant.
  5. Update Wiki §17.3 to describe RLS rather than schema-per-tenant (D3 contradicts the current
     text — that is a documentation change, not a technical problem).
VALIDATION: a cross-tenant access test MUST FAIL — tenant A's token requesting tenant B's
  transaction/case/filing by id returns 404 (not 403, to avoid existence leaks); a test that
  deliberately forgets the app-level filter still returns no rows because RLS blocks it. Run the
  whole suite with two seeded tenants.

--- S3.5 encryption & secret management ---
FACTS: zero hits for encrypt/Fernet/pgcrypto in the backend. Card last4/expiry/holder are PLAINTEXT
columns on users (db_models.py:46-48). JWT_SECRET_KEY falls back to a per-process random value
(auth.py:22 — fixed in S0.2). No Vault despite README.md:123.
DO:
  1. Require JWT_SECRET_KEY (done in S0.2 — verify).
  2. Column-level encryption for genuinely sensitive fields using a key from the environment/secret
     store (cryptography.Fernet or pgcrypto). Candidates: webhook subscription secrets, any stored
     credentials, DSAR export contents. Do NOT encrypt fields you need to filter on without a plan.
  3. Card columns: do not encrypt them — DELETE them. They are replaced by provider tokens in S6.1.
     If S6.1 is not scheduled yet, delete them anyway and disable the saved-card endpoints with a
     clear 501, because storing card metadata with no provider is pure liability.
  4. Pull all secrets from the deploy target's secret store (D9); document the injection mechanism
     in DEPLOYMENT.md. Relabel the Wiki's Vault claim as target-state.
VALIDATION: starting the API without JWT_SECRET_KEY exits non-zero; a pg_dump of the database
  contains no plaintext card data or webhook secret; the encryption key is not in the repo.

PHASE 3 OVERALL VALIDATION: full suite green with two tenants seeded; permission-matrix test green;
  audit chain verifies; a cross-tenant read returns 404.
```

---

## P4 — Async platform & operations

```
PHASE 4 BRIEF — requires P1 and decision D2 (worker). Recommended default: Celery + Redis.
HARD RULE: no screening-DECISION logic moves into the worker. Decisions stay synchronous and
auditable in the API. The worker handles delivery, sweeps, refresh and recompute only.

--- S4.1 worker and broker ---
FACTS: no background execution of any kind — zero BackgroundTasks/asyncio in backend/app/. `celery`
appears once, in a comment (main.py:2606). `redis` appears only as strings naming a dependency that
does not exist (main.py:2390,2555; db_models.py:280). Compose has 3 services and no broker.
DO: add pinned celery + redis to requirements.txt; backend/app/worker/{celery_app.py,tasks/};
  a `worker` service in docker-compose.yml with a healthcheck (celery inspect ping) and
  depends_on backend+postgres healthy; task-level retries with exponential backoff + jitter and a
  dead-letter state; a task naming convention and a short README in backend/app/worker/.
VALIDATION: docker compose up -d -> worker reports healthy; a deliberately failing task retries the
  configured number of times then lands in a dead-letter state that an operator can inspect.

--- S4.2 webhook delivery, retries, DLQ ---
FACTS: POST /webhooks/dispatch (main.py:2589) inserts a row with status="pending" and returns;
POST /webhooks/{id}/retry (:2646) just resets fields (:2664-2667). Nothing ever transitions a row to
delivered/failed/dead_letter. There is NO httpx client in main.py and NO webhook SUBSCRIPTION table
(only event deliveries, db_models.py:296). Wiki:1137 claims exponential backoff and DLQ.
DO:
  1. Migration: webhook_subscriptions (id, tenant_id, url, secret, events JSON, active, created_by).
  2. Signed delivery: HMAC-SHA256 over timestamp + body, sent in headers; document verification.
  3. Celery task with exponential backoff + jitter, max attempts from config, then status=dead_letter.
  4. Emit events from the real lifecycle points: transaction.flagged, transaction.blocked,
     case.created, case.updated, case.resolved, filing.submitted, sla.breached.
  5. Replace /webhooks/dispatch (client-triggered) with internal emission; keep an admin-only
     manual replay for DLQ entries.
  6. Management endpoints + delivery log readable by the integrator (this is the Wiki's
     "Platform/Integrating Engineer" story at :1102).
VALIDATION: a subscriber that returns 500 is retried on schedule and ends in dead_letter; a healthy
  subscriber receives a payload whose HMAC verifies with its secret; a case resolution emits an event.

--- S4.3 scheduled jobs ---
FACTS: POST /api/v1/cases/check-sla (main.py:1749) exists but NOTHING schedules it, so SLA
escalation only happens if a client remembers to call it. Baseline recompute (:2238) is manual (and
crashed before S0.5). Filing deadlines are computed (:1943) but nothing reminds anyone. Sanctions
list refresh (S2.3) needs a schedule.
DO: Celery beat schedule for: SLA sweep + escalation notifications, account baseline recompute,
  filing deadline reminders (30-day FinCEN clock), sanctions/PEP list refresh, audit chain
  verification (S3.2), privacy-request deadline sweep (S3.3), RAG staleness check.
  Make each job idempotent and safe to re-run.
VALIDATION: a case left past its SLA escalates and notifies with NO client request; a filing
  approaching its deadline produces a reminder; the audit verifier runs and reports chain status.

--- S4.4 observability ---
FACTS: zero hits for OpenTelemetry, Prometheus, structlog or Sentry. Logging is
logging.basicConfig (main.py:47-51) plus a timing middleware setting X-Process-Time-Ms (:119-126).
No /metrics. README.md:121,157 and Wiki §13 (:635-689) claim all of it, including four specific
alerting rules at :676-689.
DO: structlog JSON logs with request_id, tenant_id, user_id, case_id correlation; OTel traces across
  API -> engine -> (rules / behavioral / RAG / model / gating) -> DB, one span per stage;
  prometheus-fastapi-instrumentator exposing /metrics (admin-network only); error tracking;
  implement the four alerting rules Wiki:676-689 already specifies as Prometheus rules committed to
  the repo.
VALIDATION: one screening produces one trace with a span per pipeline stage; /metrics returns
  request/latency/flag-rate series; a forced error appears in the error tracker.

--- S4.5 backup, restore, retention ---
FACTS: no backup or restore script exists. DOCKER.md:121-133 says `docker cp` the SQLite file;
DEPLOYMENT.md:391-399 says "Neon auto-backs up". SAR/STR records carry a 5-year retention
obligation and the audit chain is worthless if it can be lost.
DO: scripts/backup.sh (scheduled pg_dump to a configurable target, with retention),
  scripts/restore.sh, and a RUNBOOK section in DEPLOYMENT.md describing a tested restore plus the
  retention matrix per data class (transactions, cases, filings, audit, privacy requests,
  notifications) with the legal basis for each.
VALIDATION: back up, destroy the database, restore into a clean environment, and run the S3.2 audit
  chain verifier against the restored data. Paste the output.

PHASE 4 OVERALL VALIDATION: docker compose up -d shows 4+ healthy services; a flagged transaction
  produces a trace, a metric increment, an audit entry and a delivered webhook.
```

---

## P5 — Frontend product quality (design review track)

```
PHASE 5 BRIEF — requires decision D5 (UI kit) and D11 (token storage). Recommended defaults:
D5 = shadcn/ui (Radix) mapped onto the EXISTING Tailwind tokens; D11 = httpOnly cookie session for
the browser app, keeping the Bearer/API-key path for programmatic clients.
P5.1-P5.3 and P5.8 can start immediately with no backend dependency. P5.5 needs S3.1 (roles).
P5.6 needs the backend endpoints, which already exist. P5.7 needs S4.1.

DESIGN-REVIEW BASELINE (measured, from the design-review plugin lenses):
- tailwind.config.js:10-32 ALREADY defines a real semantic palette (bg/surface/border/ink/accent/
  teal/navy + success/warning/danger/info + shadow tokens). Preserve and extend it — do not replace it.
- No DESIGN.md, no components/ui/, ZERO primitives (no Button/Input/Card/Badge/Modal/Table). Only
  PlatformLayout.tsx, Sidebar.tsx, Topbar.tsx exist.
- Debt in src/: 67 arbitrary Tailwind values (transactions/page.tsx 16, Topbar.tsx 15,
  cases/page.tsx 8), 16 hardcoded hex, 8 inline style={{}} (dashboard/page.tsx:114,158;
  settings/page.tsx:405,434; transactions/page.tsx:345,375; Sidebar.tsx:169; reports/page.tsx:84),
  79 raw px values. Token leakage: bg-emerald-500 / text-red-600 (reports/page.tsx:73-76;
  transactions/page.tsx:188,499), border-gray-300 / focus:ring-blue-500 (filings/page.tsx:88,101).
- A11y: 12 aria-* total (all aria-required); 0 role=, 0 aria-label, 0 sr-only, 0 <caption>; no
  <th scope>; ~12 of 42 controls unlabeled (30 htmlFor); only 2 focus: styles in all of src/;
  colour-only risk bar (transactions/page.tsx:375) and donut (dashboard/page.tsx:114); modals have
  no focus trap or Escape handling.
- No middleware.ts. isAuthenticated checked ONLY in src/app/page.tsx:12. PlatformLayout.tsx:7-18
  does no gating. JWT in localStorage (lib/api.ts:358-370). No 401 interceptor. Dead code at
  lib/api.ts:396 (body.detail || body.detail?.message).
- No pagination UI: transactions/page.tsx:37 fetches a flat listTransactions(100, 0) although the
  API supports limit/offset (lib/api.ts:450-451).
- No WebSocket/EventSource. "Real-time" (dashboard/page.tsx:67) is one 30s setInterval poll for
  unread notifications (Topbar.tsx:240-245).

--- S5.8 first (cheapest, removes a whole design system) ---
website/platform/{api-keys,cases,dashboard,transactions}.html (169/182/378/134 lines) contain ZERO
fetch/XMLHttpRequest/localStorage calls — static mockups with hardcoded data
(website/platform/dashboard.html:110,127: "42,180 credits", "Welcome back, John"). Nothing links to
them; they are not in docker-compose.yml. website/pages/login.html and signup.html are 13-line
stubs — broken entry points on a live marketing site.
DO: delete website/platform/ entirely; either implement website/pages/login.html and signup.html as
  redirects to the platform app or delete them and fix the marketing CTAs to point at the app;
  remove the now-unused website/css/platform.css if nothing references it (verify with grep first).
  Do NOT touch the marketing pages' own styling beyond the CTA fix.
VALIDATION: grep -rn "platform/" website/ -> no dead console links; every CTA on website/index.html
  and website/pages/*.html reaches a working login.

--- S5.1 DESIGN.md + tokens ---
DO: author platform-app/DESIGN.md containing the token table (colour, spacing, type scale, radii,
  shadows, z-index), component rules, and do/don't guidance. Extend tailwind.config.js with a type
  scale (fontFamily: Inter as a token, not a <link> in layout.tsx:14-16; fontSize scale) and a
  spacing scale. Then eliminate token leakage: replace every raw palette class
  ((bg|text|border)-(emerald|red|gray|blue|amber)-[0-9]{3}) with the semantic token.
VALIDATION: grep -rE "(bg|text|border)-(emerald|red|gray|blue|amber)-[0-9]{3}" platform-app/src
  -> zero hits outside tailwind.config.js. npm run build passes.

--- S5.2 + S5.3 primitives and accessibility (do together) ---
DO: create platform-app/src/components/ui/ with Button, Input, Select, Textarea, Card, Badge,
  Table (+Th/Td with scope="col"), Modal (Radix Dialog: focus trap + Escape), Tabs, Skeleton,
  EmptyState, ErrorState, Pagination. Each primitive OWNS its focus-visible ring, disabled state,
  error state and aria attributes so a11y is fixed once, not per page.
  Then migrate pages one at a time (transactions -> cases -> filings -> rules -> settings ->
  api-keys -> reports -> dashboard), removing the duplicated markup (e.g. the repeated <thead> at
  dashboard/page.tsx:200-206 and transactions/page.tsx:231-235).
  Accessibility requirements per page: every control has an associated <label>; every icon-only
  button has aria-label; decorative SVGs have aria-hidden="true"; tables have <th scope="col"> and
  a caption or aria-label; global focus-visible ring; modals trap focus and close on Escape; the
  risk bar (transactions/page.tsx:375) and donut (dashboard/page.tsx:114) expose a text/numeric
  equivalent (aria-valuenow or an adjacent label) so meaning is not colour-only; status badges keep
  their text label alongside colour.
VALIDATION: run an axe scan (add @axe-core/react in dev, or use the design-review:accessibility-review
  skill) and report zero serious/critical violations. Then do a keyboard-only pass: log in, screen a
  transaction, open its detail modal, close it with Escape, create a case, add a comment, file a
  SAR — all without a mouse. Report what breaks and fix it.
  Also: grep -rE "\[[0-9]+(px|rem)\]" platform-app/src -> arbitrary values trend to zero.

--- S5.4 data layer ---
DO: add SWR (or @tanstack/react-query) to package.json and refactor pages off hand-rolled
  useEffect+useState. Add pagination controls to transactions, cases, filings and audit views using
  the existing limit/offset support. Add a 401 interceptor in lib/api.ts that clears the session and
  redirects to /login?next=<path>. Remove the dead branch at lib/api.ts:396. Implement D11 (cookie
  session) if ruled: add a Next.js route handler that exchanges the login response for an httpOnly
  cookie, keep the Bearer path for API-key clients, and add CSRF protection.
VALIDATION: a list with 10 000+ rows paginates without fetching everything; expiring the token
  mid-session redirects to /login with a working return path instead of showing a raw error banner.

--- S5.5 route protection + role gating (needs S3.1) ---
DO: add platform-app/src/middleware.ts guarding the whole platform segment, redirecting to
  /login?next=... when unauthenticated. Gate nav items in Sidebar.tsx on the role from
  GET /api/auth/me. Show a proper 403 state for routes the role cannot access. Remove the now-
  redundant ad-hoc check in src/app/page.tsx:12 or keep it as a fast path.
VALIDATION: loading /cases logged out redirects to /login and returns to /cases after login; an
  analyst never sees admin nav items and gets a 403 state if the URL is typed directly.

--- S5.6 surface the built-but-unused backend + real API docs ---
FACTS: eight working backend capabilities have NO UI: /api/v1/rules/simulate (main.py:1454),
  /rules/{id}/stats (:1512), /cases/{id}/notes (:1699), /cases/check-sla (:1749),
  /cases/aggregate (:1801), all three /behavioral/* (:2170-2328), /health/circuit-breakers*
  (:2381+), /webhooks/dispatch (:2589). Meanwhile platform-app/src/app/docs/page.tsx:6-40 is a
  HARDCODED ENDPOINTS array that has already drifted (omits filings, notifications, search,
  rules-simulate).
DO: build the rule simulator screen (pick a rule, date range, run against history, show hits),
  rule stats, case notes (distinct from comments — notes are investigator-private), an SLA/
  aggregation view on the cases page, a behavioral baseline panel on the transaction detail view,
  an ops health page showing real circuit-breaker state (S2.6), and a webhook subscription
  management page (S4.2). Replace docs/page.tsx's literal array with a page generated from the
  backend's /openapi.json (fetch at build time into a committed JSON, or at runtime through the
  existing /api rewrite).
VALIDATION: the docs route lists exactly the routes FastAPI exposes (diff the paths); each new
  screen round-trips against a live backend — demonstrate one create and one read per screen.

--- S5.7 live updates, or drop the claim ---
DO: either (a) add an SSE endpoint on the backend emitting case/transaction/filing events (fed by
  the S4.1 worker) and consume it with EventSource in the dashboard, with reconnect and a visible
  connection state; or (b) change the copy at dashboard/page.tsx:67 and README.md:44 from
  "real-time" to "auto-refreshing", add honest polling with a visible last-updated timestamp, and
  remove the implication of push. Do not leave the current state where the claim exists and only a
  30s notification poll backs it.
VALIDATION: (a) a new flagged transaction appears in an open dashboard without manual reload, and
  the connection state indicator reflects a server restart; or (b) no remaining "real-time" claim
  anywhere: grep -rn "real-time\|realtime\|Real-time" README.md FinShield-AI-Wiki.md platform-app/src

PHASE 5 OVERALL VALIDATION: npm run build && npm run lint && npx tsc --noEmit all pass; axe scan
  clean; keyboard-only walkthrough completes; grep for arbitrary values and raw palette classes
  returns zero; every page has loading, error and empty states.
```

---

## P6 — Market readiness

```
PHASE 6 BRIEF — requires decisions D8 (payments) and D9 (deploy target). Recommended defaults:
D8 = Stripe Checkout (hosted fields, PCI SAQ-A); D9 = managed PaaS + platform secret store.
S6.7 (Kubernetes/Helm) is CONDITIONAL — build it only when an enterprise deal requires it.

--- S6.1 payments ---
FACTS: no provider integration exists. PLANS is a hardcoded list (main.py:874);
  POST /billing/subscribe (:962), /credits/checkout (:1044) and /credits/purchase (:1151) adjust
  credits WITHOUT charging anyone. Card last4/expiry/holder are plaintext columns
  (db_models.py:46-48) — likely already deleted by S3.5. DEPLOYMENT.md:314-334 references a
  PAYMONGO_SECRET_KEY for code that does not exist. The frontend billing UI is fully wired
  (platform-app/src/app/settings/page.tsx:289-378).
DO: integrate Stripe Checkout for one-time credit purchases and Stripe Billing for subscriptions;
  store only stripe_customer_id / stripe_subscription_id / payment_method_id (never card data);
  add a Stripe webhook endpoint (signature-verified, admin-exempt but signature-authenticated) that
  drives entitlement updates; implement dunning (failed payment -> grace -> downgrade) and refunds;
  move PLANS into the config service (S1.4) so pricing is runtime-configurable; keep the existing
  credit accounting and trial gating, which already work.
CONSTRAINT: the Stripe webhook route must NOT use Depends(get_current_user) — it authenticates by
  signature. Document that exception explicitly.
VALIDATION: a test-mode checkout grants credits and the DB shows no card number/expiry anywhere;
  a failed payment moves the subscription to a grace state; an unsigned webhook request is rejected.

--- S6.2 deploy target, TLS, security headers ---
FACTS: website/nginx.conf listens on port 80 only (:2), has X-Frame-Options/nosniff/XSS-Protection
  (:13-15) but NO HSTS, NO CSP, NO Referrer-Policy — and the add_header inside the static-asset
  location block (:20) DROPS the parent-level headers for those paths (nginx inheritance quirk).
  platform-app/next.config.js:1-17 has only output:'standalone' and API rewrites: the authenticated
  compliance dashboard ships ZERO security headers. No k8s manifests, Helm charts or Terraform
  exist despite README.md:301-311.
DO: choose and document the deploy target (D9); terminate TLS at the edge; add a headers() function
  to next.config.js with CSP (start report-only, then enforce), Strict-Transport-Security,
  Referrer-Policy, X-Content-Type-Options, Permissions-Policy and frame-ancestors; fix the nginx
  add_header inheritance by repeating the headers inside the location block or using `include`;
  add a backend security-headers middleware; document the CSP allowlist rationale.
VALIDATION: an SSL Labs test grades A or better on every public surface; a security-header scan
  (securityheaders.com or curl -I) shows all headers on all three surfaces; the app still works
  under enforced CSP with zero violation reports.

--- S6.3 container hardening ---
FACTS: platform-app/Dockerfile:2 uses node:18-alpine (EOL). All three images run as root with no
  USER and no HEALTHCHECK, are not digest-pinned, and are single-stage. backend/Dockerfile:7-9
  installs gcc and never removes it, and ships pytest/httpx in the runtime image.
  next.config.js:3 sets output:'standalone' but platform-app/Dockerfile:28 runs `npm start`, so the
  slim standalone server.js is never used and the full toolchain + node_modules ship.
  platform-app/Dockerfile:15-16 bakes NEXT_PUBLIC_API_URL=http://localhost:8091 at BUILD time —
  NEXT_PUBLIC_* is inlined into the client bundle, so the compose runtime value
  (docker-compose.yml:56) cannot override it and any non-localhost deploy is broken.
DO: Node 22 LTS; multi-stage builds for all three images; non-root USER in each; digest-pinned
  bases; HEALTHCHECK in each (S0.4 added these — verify they survived); drop build tooling from
  runtime stages; move test deps to requirements-dev.txt so they are not in the runtime image;
  actually use the standalone output (node .next/standalone/server.js).
  For the NEXT_PUBLIC problem pick ONE and document it: (a) serve the frontend through a same-origin
  /api rewrite only, so no absolute URL is baked in (lib/api.ts:7 already uses a relative '/api' —
  this is the cheapest fix); (b) a runtime config endpoint the client fetches on boot; (c) per-env
  builds. Option (a) is recommended.
VALIDATION: docker inspect shows a non-root User and a healthy Status for each image; report image
  sizes before and after; deploy the frontend to a NON-localhost origin and confirm it reaches the
  API (this is the test that catches the NEXT_PUBLIC bug).

--- S6.4 Python SDK ---
FACTS: README.md:217 and Wiki §19 list an sdk/ directory; it does not exist. The
  "Platform/Integrating Engineer" story (Wiki:1102) currently means hand-rolling HTTP against 68
  routes.
DO: generate a typed client from the backend's OpenAPI schema (do not hand-maintain it — the
  in-app docs already drifted, which is the cautionary tale). Add retries with Idempotency-Key
  propagation (critical: a retry without the same idempotency key double-screens), API-key and JWT
  auth, typed errors mirroring lib/api.ts's ApiError, and a version pinned to the API version.
  Publish it as sdk/finshield/ with a pyproject.toml.
VALIDATION: the SDK's integration test screens a transaction, retries on a transient failure without
  creating a duplicate, and reads back the decision with its reasons[] and model_version.

--- S6.5 load and performance testing ---
FACTS: README.md:288-289 documents `locust -f tests/load/test_throughput.py`; no load test exists.
  S1.3 fixed event-loop blocking but throughput has never been measured.
DO: add locust or k6 scenarios for transaction screening (the hot path), case list, transaction
  detail and RAG search; record p50/p95/p99 and throughput; set targets in a committed config; run
  nightly in CI against a compose stack; fail on regression beyond a threshold.
VALIDATION: a documented p95 screening latency at 1x, then at 10x concurrency, showing the S1.3 fix
  holds. Paste both numbers.

--- S6.6 regulatory evidence pack ---
FACTS: selling to compliance teams requires artefacts, not claims. Wiki:805-833 and :1181 assert
  readiness the code does not support.
DO: assemble docs/compliance/ from the outputs of S2.5 (model cards), S3.2 (audit export procedure
  + chain verification), S3.3 (retention matrix + erasure legal basis), S3.1 (access-control
  matrix), S4.5 (backup/restore runbook + tested restore evidence), S0.4/S4.4 (monitoring and
  alerting), S6.2 (TLS/headers evidence). State for each control whether it is AUTOMATED
  (with a test) or PROCEDURAL (with a runbook and an owner). Include a short honest
  "limitations and target-state" page.
VALIDATION: answer a sample security questionnaire (SOC 2 style: access control, audit logging,
  encryption, retention, incident response, change management, vendor management) entirely from the
  pack, with every "yes" linking to a passing test or a runbook. List any question you cannot answer.

--- S6.7 Kubernetes / Helm (CONDITIONAL) ---
FACTS: README.md:301-311 documents `helm repo add finshield ./deploy/k8s`; no deploy/ directory
  exists. Only build this when an enterprise deal requires it.
DO: Helm chart with values-dev/values-prod, HPA, PDB, resource requests/limits, NetworkPolicies,
  secrets from the cluster secret store, ingress with TLS, and the S0.4 health probes wired to
  liveness/readiness. Remove or relabel the README section until it exists.
VALIDATION: helm lint && helm template render cleanly; an install into a clean cluster passes the
  S6.5 load profile while HPA scales.
```

---

## Single-slice template

Use this when you want one slice rather than a whole phase.

```
[ paste the Global preamble here ]

SLICE: <id and title, e.g. S2.1 — wire the behavioral monitor into screening>

CURRENT STATE (verified):
<paste the matching rows from docs/architecture/evolution/evidence.md>

TARGET STATE:
<paste the slice's DO list from the phase brief above>

ACCEPTANCE CRITERIA:
<paste the slice's TESTS + VALIDATION lines>

OUT OF SCOPE (do not touch): <list neighbouring slices so the agent does not sprawl>

Before writing code: list the files you will change and the migration (if any) you will add,
and confirm the acceptance criteria are testable. Then implement, then run the validation
commands and paste real output.
```

## Tracking

Copy this into your issue tracker. One row per slice; do not mark a row done without its validation command passing.

| Phase | Slice | Blocks | Decision needed | Effort |
|---|---|---|---|---|
| P0 | S0.1 docs reconcile | S6.6 | D10 | S |
| P0 | S0.2 secrets hygiene | S1.1, S3.5 | — | S |
| P0 | S0.3 CI fix | S1.2 | — | M |
| P0 | S0.4 real health probes | S4.4 | — | S |
| P0 | S0.5 latent bugs | S2.1 | — | S |
| P1 | S1.1 Postgres primary | S1.2 | D6 | M |
| P1 | S1.2 Alembic | S2.3, S2.5, S3.2, S3.4, S6.1 | — | M |
| P1 | S1.3 async/sync DB | S4.1, S6.5 | — | M |
| P1 | S1.4 config service | S2.2, S3.4 | — | M |
| P1 | S1.5 drop idempotency cache | — | — | S |
| P2 | S2.1 wire behavioral | — | — | M |
| P2 | S2.2 deterministic scoring | S2.5 | — | M |
| P2 | S2.3 sanctions/PEP data | — | D12 | L |
| P2 | S2.4 RAG end-to-end | S2.7 | D4 | M |
| P2 | S2.5 versioned risk model | S2.7, S6.6 | D1 | L |
| P2 | S2.6 real circuit breakers | S4.4 | — | M |
| P2 | S2.7 eval harness | S6.6 | — | M |
| P3 | S3.1 RBAC | S3.4, S5.5 | — | M |
| P3 | S3.2 immutable audit | S6.6 | — | M |
| P3 | S3.3 privacy/DSAR | — | — | M |
| P3 | S3.4 multi-tenancy | — | D3 | L |
| P3 | S3.5 encryption/secrets | — | D9 | M |
| P4 | S4.1 worker + broker | S4.2, S4.3, S5.7 | D2 | M |
| P4 | S4.2 webhook delivery/DLQ | — | — | M |
| P4 | S4.3 scheduled jobs | — | — | M |
| P4 | S4.4 observability | — | — | M |
| P4 | S4.5 backup/restore | S6.6 | — | S |
| P5 | S5.1 DESIGN.md + tokens | S5.2 | — | S |
| P5 | S5.2 UI primitives | S5.3 | D5 | M |
| P5 | S5.3 accessibility | — | — | M |
| P5 | S5.4 data layer | S5.7 | D11 | M |
| P5 | S5.5 route protection | — | D11 | M |
| P5 | S5.6 unused endpoints + OpenAPI docs | — | D10 | M |
| P5 | S5.7 live updates or drop claim | — | — | M |
| P5 | S5.8 retire dead frontends | S5.1 | D7 | S |
| P6 | S6.1 payments | — | D8 | M |
| P6 | S6.2 deploy + TLS + headers | — | D9 | M |
| P6 | S6.3 container hardening | S6.7 | — | M |
| P6 | S6.4 Python SDK | — | — | M |
| P6 | S6.5 load tests | — | — | M |
| P6 | S6.6 regulatory evidence pack | — | — | M |
| P6 | S6.7 Kubernetes/Helm | — | D9 | L |
