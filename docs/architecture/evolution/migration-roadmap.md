# FinShield AI — Migration Roadmap

Generated 2026-10-23 by `architecture-visualization:evolution-planner`.
Sequencing graph: [architecture-evolution.dot](./architecture-evolution.dot) · Capability gaps: [gap-map.dot](./gap-map.dot) · Current vs target: [current-vs-target.dsl](./current-vs-target.dsl)

**Framing.** The repo is a credible, working prototype — 68 real routes, 65 passing tests, real JWT/API-key auth on 64 of them, real case and SAR/STR persistence, and one genuinely well-designed piece (the rule-action precedence gate at `backend/app/compliance_engine.py:339-361`). It is **not** what `README.md` and `FinShield-AI-Wiki.md` claim it is. Three whole capabilities are built but unreachable, four are random-number stubs, and six documented production behaviours do not exist in the repo at all. The roadmap therefore front-loads *truth and safety* before feature work: shipping more features on top of an unversioned schema, a fake health endpoint and a committed `.env` multiplies the cost of every later slice.

Effort: **S** ≤ 1 day · **M** 2-5 days · **L** 1-3 weeks. Reversibility: **high** = delete and move on, **medium** = data migration needed, **low** = customer-visible or schema-locked.

---

## Phase 0 — Truth & safety (ship-blocking)

Nothing here adds a feature. Everything here prevents the next phase from being built on sand.

### S0.1 Reconcile documentation with code — **S**, risk low, reversibility high
- **Why:** `README.md:145-159` instructs `docker compose -f docker/docker-compose.yml up -d` (no `docker/` directory exists), promises "API + worker + Postgres/pgvector + Redis + dashboard" (no worker, no Redis) and a Prometheus URL (no Prometheus). `README.md:150` and `FinShield-AI-Wiki.md:979` instruct `alembic upgrade head` — Alembic is not installed and no migration exists. `FinShield-AI-Wiki.md:1129-1140` labels behavioral monitoring, circuit breakers, webhook DLQ, GDPR/DSAR and immutable audit "✅ fully implemented, tested, and production-ready"; the code shows the behavioral monitor is never called by `screen()`, the breaker protects nothing, webhook rows are never delivered, DSAR writes one log row, and the audit table has no append-only constraint. `FinShield-AI-Wiki.md:1181` states "Production Readiness Score: 8.5/10".
- **Do:** add a status column (Implemented & wired / Built but not wired / Stub / Absent) to Wiki §21; delete or mark every impossible command; state the real compose topology; move the "Resume Line" claims (§23) that are not true into a clearly-labelled *target* section.
- **Business path protected:** every sales, investor and hiring conversation. An evaluator who runs the README's own quickstart fails at step 3.
- **Validation:** a fresh clone following README verbatim reaches a running stack; `grep -rn "alembic\|docker/docker-compose\|Prometheus" README.md FinShield-AI-Wiki.md` returns only entries marked target-state.

### S0.2 Secrets & repo hygiene — **S**, risk medium (history rewrite), reversibility medium
- **Why:** `backend/.env` is tracked in git (`git ls-files` confirms) and has been since the first commit, even though `.gitignore:26` lists `.env` — it was never `git rm --cached`. It holds a placeholder-but-live `JWT_SECRET_KEY` and `DEBUG=true`. `docker-compose.yml:11,33,34` hardcodes `POSTGRES_PASSWORD=finshield_secret`, a full credential-bearing DB URL, and `JWT_SECRET_KEY=your-secret-key-change-in-production`; `docker-compose.yml:8` publishes Postgres on `5432:5432`. `README.md:143` tells users to `cp .env.example .env` — no `.env.example` exists anywhere in the repo.
- **Do:** untrack `.env`, add `.env.example` with every key the code actually reads (`APP_ENV`, `DEBUG`, `APP_PORT`, `DATABASE_URL`, `RAG_DATABASE_URL`, `RAG_USE_SENTENCE_TRANSFORMERS`, `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `RATE_LIMIT_PER_MINUTE`, `CORS_ORIGINS`, `DEFAULT_SIGNUP_CREDITS`), switch compose to `${VAR}` interpolation with a required-var check, stop publishing 5432 (or bind `127.0.0.1:`), and rotate the JWT secret. Decide explicitly whether to purge git history — it is a public-visibility question, not a technical one.
- **Business path protected:** customer security review. A tracked `.env` in an AML product ends a procurement security questionnaire.
- **Validation:** `git ls-files | grep -E "\.env$|\.db$"` is empty; `docker compose config` fails loudly when a required var is unset; CI secret scan passes.

### S0.3 Fix CI so it can gate anything — **M**, risk low, reversibility high
- **Why:** `.github/workflows/ci.yml:81,84` run `docker build -t finshield-backend ./backend` and `./platform-app`, but `backend/Dockerfile:12` does `COPY backend/requirements.txt .` and `platform-app/Dockerfile:7` does `COPY platform-app/package*.json ./` — both require repo-root context (as compose uses). Those builds **cannot succeed**; the job only runs on push to `main`, so it has never been a PR gate. `ci.yml:112` sets `continue-on-error: true` on the `safety` scan, making it advisory. CI uses Python 3.13 (`ci.yml:10,28`) while the image is `python:3.11-slim`. No coverage, no Python lint, no type check, no `tsc --noEmit`, no secret or image scanning. `backend/test_filing_e2e.py` sits outside `tests/` so `pytest tests/` never collects it.
- **Do:** correct both build contexts to `.` with `-f`, pin CI Python to 3.11, add `ruff` + `mypy`, add `pytest --cov` with a floor at the current level (ratchet, don't guess a target), add `tsc --noEmit`, make `safety`/`pip-audit` and `npm audit` blocking, add `trivy` image scan, add secret scanning, and either move `test_filing_e2e.py` into `tests/e2e/` behind a marker or delete it.
- **Business path protected:** every later slice — P1 onwards depends on a green CI to be mergeable.
- **Validation:** the `docker-build` job passes on a PR (not just on `main`); a deliberately broken import fails the pipeline.

### S0.4 Real health and readiness probes — **S**, risk low, reversibility high
- **Why:** `backend/app/main.py:2830-2845` returns a hardcoded map in which `database`, `behavioral_ml`, `rag_classifier` and `case_manager` are statically `"healthy"`. No dependency is probed. `DEPLOYMENT.md:386` points an uptime monitor at it, so monitoring will report green through a full outage. None of the three Dockerfiles declares a `HEALTHCHECK`; `backend` has no compose healthcheck, so `frontend: depends_on: backend` (`docker-compose.yml:57-58`) is start-order only.
- **Do:** probe the primary DB (`SELECT 1`), the RAG Postgres when configured, and worker/broker once S4.1 exists; return `503` with per-dependency detail when degraded; split `/health/live` from `/health/ready`; add `HEALTHCHECK` to each image and `condition: service_healthy` in compose.
- **Business path protected:** on-call. Without a truthful probe there is no alerting and no safe rolling deploy.
- **Validation:** stop the Postgres container → `/api/health` returns 503 within one probe interval and compose marks backend unhealthy.

### S0.5 Two latent production bugs — **S**, risk low, reversibility high
- **Why:** (1) `GET /api/v1/transactions/export` is registered at `main.py:666`, *after* `GET /api/v1/transactions/{tx_id}` at `main.py:606`, so FastAPI matches `tx_id="export"` first and the export endpoint is unreachable — yet `platform-app/src/app/transactions/page.tsx:98` calls it via `window.open`. (2) `import math` exists only as a function-local import inside `score_transaction_behavior` (`main.py:2177`), but `math.sqrt` is called at `main.py:2274` in a *different* function, so `POST /api/v1/behavioral/update-baseline` raises `NameError` → 500 for any account with more than one transaction. Neither is caught by tests because no test touches either path.
- **Do:** move `/export` above `/{tx_id}` (or namespace it under `/api/v1/transactions:export`), hoist `import math` to module level, and add a regression test for each.
- **Validation:** `pytest -k "export or baseline"` passes; manual `POST /api/v1/behavioral/update-baseline` with two transactions returns 200.

---

## Phase 1 — Data foundation

### S1.1 Make Postgres the primary database — **M**, risk medium, reversibility medium
- **Why:** `docker-compose.yml:32` sets the backend's `DATABASE_URL=sqlite:///./finshield.db` while `docker-compose.yml:5` runs `pgvector/pgvector:pg16` and `:33` points only the *RAG* store at it. All 14 primary tables live in a SQLite file inside a container volume. This blocks RLS/tenancy (S3.4), append-only triggers (S3.2), concurrent workers (S4.1) and pgvector joins in one query.
- **Do:** point `DATABASE_URL` at Postgres, keep SQLite only for `APP_ENV=test` (`database.py:12-13`), verify the pgvector-specific types still resolve, and add a one-off data-copy script for existing dev databases.
- **Validation:** compose stack starts with zero SQLite writes (`find . -name "*.db" -newer ...` empty); the full test suite still passes on SQLite.

### S1.2 Alembic versioned migrations — **M**, risk medium, reversibility low once baselined
- **Why:** schema is created by `Base.metadata.create_all` (`database.py:36-38`, `:44`, `rag_service.py:153`). `create_all` cannot alter an existing table, so any column addition silently no-ops on a live database. `alembic` is absent from `requirements.txt`. For a product whose selling point is a regulator-defensible audit trail, unversioned schema is a compliance blocker.
- **Do:** add Alembic, autogenerate a baseline from the current 14 tables + 3 RAG tables, wire `alembic upgrade head` into the container entrypoint, and make `create_all` test-only. Note the RAG tables use a **separate** `declarative_base()` (`rag_service.py:102-142`) — unify metadata or add a second migration target.
- **Validation:** `alembic upgrade head` on an empty DB then `alembic downgrade -1` both succeed; CI runs upgrade against Postgres.

### S1.3 Fix async/sync database access — **M**, risk medium, reversibility high
- **Why:** all 68 handlers are `async def` but execute blocking synchronous SQLAlchemy inside, so every request stalls the event loop. This caps throughput at roughly one query at a time and will not survive the load test in S6.5.
- **Do:** either convert handlers that only touch the DB to `def` (FastAPI runs them in a threadpool) or move to an async engine/session. Pick one convention and apply it repo-wide; do not mix.
- **Validation:** concurrent-load micro-benchmark (50 parallel screenings) shows near-linear scaling instead of serialization.

### S1.4 Runtime config service — **M**, risk low, reversibility high
- **Why:** the Wiki's central claim is "config-first operation … all runtime, no redeploy" (`README.md:228-242`). Reality: `THRESHOLD_WIRE`, `THRESHOLD_INTERNATIONAL`, `VELOCITY_WINDOW_TXS` are module constants (`compliance_engine.py:25-27`), risk weights are inline literals (`:317-325`), decision bands are inline (`:355-360`), credit prices are inline (`:116-118`), and `PLANS` is a hardcoded list (`main.py:874`). The one real override layer — per-user `rule_configs` (`db_models.py:184-209` → `main.py:476-479` → `compliance_engine.py:168-177`) — is genuinely wired and editable from the UI, and `RuleConfig.priority/version/effective_from/effective_to` are written but never read by the engine.
- **Do:** add `settings` and `feature_flags` tables with typed accessors and caching, migrate the constants above into them, honour `priority`/`effective_*` in rule execution, and audit-log every config change with before/after + actor (the Wiki already promises this).
- **Validation:** change a threshold from the admin UI → next screening uses it, no restart, and an audit row records old/new/actor.

### S1.5 Remove the unbounded in-memory idempotency cache — **S**, risk low, reversibility high
- **Why:** `compliance_engine.py:37` keeps a process-local `dict` written at `:161`. It never expires, is lost on restart, and duplicates the real DB-backed idempotency check at `main.py:454-473` (unique `idempotency_key` + `user_id`). It is also a memory leak and a multi-replica correctness bug.
- **Do:** delete the engine cache; keep the DB layer as the single source of truth.
- **Validation:** submitting the same `Idempotency-Key` twice returns the persisted first result; engine unit tests still pass after removal.

---

## Phase 2 — Make detection real (the product core)

### S2.1 Wire the behavioral monitor into screening — **M**, risk medium, reversibility high
- **Why:** a real z-score anomaly detector with cold-start handling exists at `main.py:2196-2220` (`z_score = abs(amount - avg)/std_dev`, `anomaly_score = min(1.0, z/3.0)`, 0.5 cold-start / 0.65 warm) backed by `account_baselines` (`db_models.py:318-352`) with a real recompute at `:2267-2310`. `screen()` never calls it — it uses `compliance_engine.py:281-294`, which is amount thresholds plus `score += random.uniform(0, 0.15)`. Separately, `main.py:2248` keys baselines off `sender_name` as an account proxy.
- **Do:** inject the baseline lookup into `screen()` stage 4, key baselines on a real `account_id`, delete the `random.uniform` term, and schedule baseline recomputation (S4.3).
- **Business path unlocked:** the headline claim "behavioral monitoring on 100% of transactions".
- **Validation:** an account with a stable history that suddenly sends a 20× amount flags as behavioral; the same transaction for a cold-start account does not.

### S2.2 Deterministic, explainable scoring — **M**, risk medium, reversibility high
- **Why:** `_ml_classify` (`compliance_engine.py:297-304`) is documented "Simulate ML classification via RAG + LoRA" and returns `random.uniform` confidences; `_behavioral_score` adds randomness at `:293`; the risk blend at `:307-327` uses literal weights. Two identical transactions can receive different decisions. In AML this is indefensible: an examiner asking "why was this flagged?" must get a reproducible answer.
- **Do:** remove all randomness, move weights into config (S1.4), emit a structured `reasons[]` array per decision (rule id, feature, contribution), and persist it with the transaction so the UI can show the trail.
- **Validation:** the same payload screened twice yields byte-identical decision, score and reasons.

### S2.3 Real sanctions and PEP data — **L**, risk medium, reversibility medium
- **Why:** `SANCTIONED_ENTITIES = {"globalremit","darkfund","terrorfin"}` and a 3-entry PEP set (`compliance_engine.py:22-23`) with exact lowercase membership at `:185,:198`; high-risk countries are a 5-element set (`:24`). No fuzzy matching, no external feed, no list versioning. A real sanctions screen needs OFAC SDN ingestion, alias and fuzzy matching, and a record of *which list version* produced a hit (needed for audit defence).
- **Do:** add `sanctions_entries`/`pep_entries` tables with source, list version and effective dates; write an OFAC SDN CSV importer as a scheduled job; implement normalised + fuzzy matching (token set / Jaro-Winkler) with a configurable threshold; record the matched list entry id and version on every hit.
- **Validation:** importing the real SDN file and screening a known alias produces a hit that names the list entry and version; the legacy 3-name behaviour is preserved as a test fixture, not as production data.

### S2.4 Enable RAG end-to-end — **M**, risk medium, reversibility high
- **Why:** retrieval is real pgvector cosine SQL (`rag_service.py:276-278,305-307,343-345`) but embeddings are MD5 feature-hashing into 384 buckets (`:52-73`, docstring admits it approximates "lexical overlap"). The real path (`SentenceTransformer("all-MiniLM-L6-v2")`, `:36-38`) is behind `RAG_USE_SENTENCE_TRANSFORMERS` defaulting to `"false"` **and `sentence-transformers` is not in `requirements.txt`**, so it can never activate. The service is constructed only when `RAG_DATABASE_URL` starts with `postgresql` (`main.py:139-150`): compose sets it (`:33`) so RAG is live in Docker, but local `.env` does not, so it is silently `None` in dev and all four `/api/v1/rag/*` routes return 503. `seed_rag_data.py` is `__main__`-only and is invoked by nothing. When enabled, RAG can flip `approved → flagged` and floor risk at 0.5 (`main.py:500-503`) but can never escalate to blocked and never lowers a decision.
- **Do:** decide D4 (local sentence-transformers vs embedding API), add the dependency, run seeding from app startup or a compose init job, log a single explicit WARN when RAG is disabled rather than silently 503-ing, and define whether retrieval may *lower* a decision (currently asymmetric).
- **Validation:** `POST /api/v1/rag/search-documents` returns ranked results with real embeddings; screening a transaction whose memo matches a seeded policy document shows `rag_context` persisted (`db_models.py:100`) and reflected in the decision.

### S2.5 Versioned scoring model behind an interface — **L**, risk high, reversibility medium
- **Why:** the Wiki and README promise a DSPy-compiled LoRA-tuned Llama classifier served by vLLM. There is no model, no inference client, and no `torch`/`transformers`/`dspy`/`vllm` anywhere in `requirements.txt`. This is decision **D1** — do not default to the LLM path.
- **Do:** define a `RiskModel` protocol (`score(features) -> (label, confidence, reasons)`), implement v1 as a deterministic gradient-boosted or logistic model with feature importances as reasons, add a `model_versions` table with status (shadow/active/retired) and a model card blob, run shadow mode (score alongside, persist, never affect the decision) before promotion, and keep the Llama/LoRA path as a later implementation of the same protocol.
- **Business path unlocked:** "ML-based classification" becomes a defensible claim with governance attached.
- **Validation:** shadow run over historical transactions produces a precision/recall report; promoting a version is a config change, not a deploy; decisions cite the model version that produced them.

### S2.6 Circuit breakers that protect real calls — **M**, risk low, reversibility high
- **Why:** the three-state machine and `CircuitBreaker` table are real (`main.py:2443-2445` opens on threshold, `:2510` half-open probe) but state changes are driven **only by client HTTP POSTs** (`/record-failure`, `/record-success`). No breaker wraps any call, and it monitors `model_server`, `pgvector`, `redis`, `notification_service` — none of which the code invokes. The Wiki's "degraded mode routes to human review, never silently auto-approves" (`FinShield-AI-Wiki.md:461-495`) is unimplemented.
- **Do:** implement a decorator/context-manager wrapping the RAG, embedding, model and notification calls; on open, route the transaction to human review with an explicit `degraded=true` reason; surface real breaker state to `/api/health` (S0.4) and the dashboard.
- **Validation:** kill the RAG Postgres → screening still succeeds, decision is `in_review` with `degraded` reason, breaker shows `open`, and no transaction is auto-approved.

### S2.7 Evaluation harness — **M**, risk low, reversibility high
- **Why:** `README.md:279-289` documents `tests/eval/eval_classifier.py`, `eval_behavioral.py`, `eval_rag.py` and locust load tests. None exist (zero hits for precision/recall/RAGAS/locust). Without an eval harness, S2.5 is unshippable and every future model or threshold change is unmeasured.
- **Do:** build a labelled fixture set (realistic transaction scenarios with expected dispositions), report precision/recall/false-positive-rate per stage, add retrieval quality metrics, and run it in CI on a schedule rather than per-PR (too slow).
- **Validation:** `make eval` produces a report; a deliberate threshold regression is caught.

---

## Phase 3 — Governance & regulatory

### S3.1 RBAC — **M**, risk medium, reversibility medium
- **Why:** there is no `role` column on `User` (`db_models.py:22`) and no `require_admin`-style dependency. Every authenticated user can call circuit-breaker admin (`main.py:2429-2510`), DSAR (`:2682`) and webhook dispatch (`:2589`). `UserProfile` in the frontend has no role field (`lib/api.ts:48-68`) and the Sidebar uses `user` for display only.
- **Do:** add roles (analyst, investigator, supervisor, admin), a `require_role` dependency, apply it to admin/privacy/breaker/webhook routes, return role in `/api/auth/me`, and gate the UI (S5.5).
- **Validation:** an analyst token receives 403 on breaker and DSAR routes; the UI hides those nav items.

### S3.2 Immutable, queryable audit trail — **M**, risk medium, reversibility low
- **Why:** 15 `AuditLog` write sites exist, but there is no DB constraint preventing UPDATE/DELETE, no hash chaining, and **no endpoint to read audit logs** — the data is written and never exposed. Screening *decisions* are not audited at all (only `logger.info` at `main.py:565`). The Wiki claims "immutable audit trail … chain-of-custody export ready" (`FinShield-AI-Wiki.md:1139`).
- **Do:** revoke UPDATE/DELETE at the DB level (or add a trigger), add a hash chain over sequential entries, audit every screening decision with inputs/reasons/model version/actor, add a filtered read API plus a signed chain-of-custody export, and define retention.
- **Business path unlocked:** the regulator-defensibility claim, and any SOC 2 / customer security review.
- **Validation:** an attempted `UPDATE audit_logs` fails; tampering with one row breaks the chain verification; an export can be independently verified.

### S3.3 Privacy: DSAR, erasure, PII masking — **M**, risk medium, reversibility medium
- **Why:** `POST /privacy/dsar` (`main.py:2682`) only writes an AuditLog row — the code comment at `:2689-2690` says "we just log it". `GET /privacy/pii-classification` (`:2708`) returns a hardcoded dict literal (`:2713-2724`). There is no PII masking or field-level redaction anywhere (zero hits), and no DSAR record entity.
- **Do:** add a `privacy_requests` table with type/status/deadline, implement subject-data collection across all tables, implement erasure that respects regulatory retention (filings and audit must survive — document the legal basis), add masking for non-privileged roles in API responses and UI, and expose the classification from config rather than a literal.
- **Validation:** a DSAR request produces a complete subject-data export within the tracked deadline; an erasure request removes personal data while preserving filings and audit rows, with the reason recorded.

### S3.4 Multi-tenancy — **L**, risk high, reversibility low
- **Why:** zero occurrences of "tenant" in the backend. Isolation is per-*user* row filtering (`filter(... user_id == current_user.id)`), which is not tenant isolation. `FinShield-AI-Wiki.md:823-833` describes per-tenant Postgres schemas; see decision **D3** — schema-per-tenant and shared-schema+RLS are materially different products.
- **Do:** pick D3, add `tenant_id` to every owned table via a migration, enforce with Postgres RLS plus an application-level guard, scope API keys and config per tenant, and add a cross-tenant access test that must fail.
- **Validation:** two tenants with identical data cannot see each other's rows even with a hand-crafted id; the RLS policy is exercised in CI.

### S3.5 Encryption at rest & secret management — **M**, risk medium, reversibility medium
- **Why:** zero hits for `encrypt`/`Fernet`/pgcrypto in the backend. Card data is stored as plaintext columns on `users` (`db_models.py:46-48`). `JWT_SECRET_KEY` falls back to a per-process random value when unset (`auth.py:22`), which silently invalidates every token on restart and breaks multi-replica deploys. No Vault despite the README claim.
- **Do:** adopt the platform's managed disk encryption plus column-level encryption for the few genuinely sensitive fields, remove card columns entirely in favour of the provider's tokens (S6.1), require `JWT_SECRET_KEY` (fail startup if unset) instead of a silent random fallback, and pull secrets from the deploy target's secret store (D9).
- **Validation:** starting the API without `JWT_SECRET_KEY` exits non-zero with a clear message; a DB dump contains no plaintext card or secret material.

---

## Phase 4 — Async platform & operations

### S4.1 Worker and broker — **M**, risk medium, reversibility medium
- **Why:** there is no background execution of any kind — zero hits for `BackgroundTasks`/`asyncio` in `backend/app/`. `celery` appears once, in a comment (`main.py:2606`); `redis` appears only as a string naming a nonexistent dependency (`main.py:2390,2555`, `db_models.py:280`). Everything the product promises asynchronously (webhooks, SLA sweeps, baselines, bulk screening) needs this.
- **Do:** decide D2, add the service to compose with a healthcheck, define task boundaries (never do screening-decision logic in the worker — keep decisions synchronous and auditable in the API), and add task-level retries with backoff.
- **Validation:** compose runs the worker healthy; a task failure retries and lands in a dead-letter state rather than vanishing.

### S4.2 Webhook delivery, retries, DLQ — **M**, risk low, reversibility high
- **Why:** `POST /webhooks/dispatch` (`main.py:2589`) inserts a row with `status="pending"` and returns; `/retry` (`:2646`) just resets fields (`:2664-2667`). Nothing ever transitions a row to `delivered`/`failed`/`dead_letter`, and there is no `httpx` client in `main.py`. There is also no webhook *subscription* table — only event deliveries. The Wiki claims exponential backoff and DLQ support (`FinShield-AI-Wiki.md:1137`).
- **Do:** add `webhook_subscriptions` (URL, secret, events, active), implement signed delivery (HMAC + timestamp), exponential backoff with jitter, a DLQ state with manual replay, and a delivery log the integrator can read.
- **Business path unlocked:** the "Platform/Integrating Engineer" user story (`FinShield-AI-Wiki.md:1102`).
- **Validation:** a subscriber endpoint that 500s is retried on schedule and eventually lands in the DLQ; a valid HMAC signature verifies with the subscription secret.

### S4.3 Scheduled jobs — **M**, risk low, reversibility high
- **Why:** `POST /api/v1/cases/check-sla` (`main.py:1749`) exists but nothing schedules it, so SLA escalation only happens if a client remembers to call it. Baseline recomputation (`:2238`) is likewise manual — and currently crashes (S0.5). Filing deadlines are computed (`:1943`) but nothing reminds anyone.
- **Do:** add periodic tasks for SLA sweep + escalation notifications, baseline recompute, filing deadline reminders, sanctions list refresh (S2.3), and audit-chain verification.
- **Business path protected:** the SLA-enforcement claim in case management.
- **Validation:** a case left past its SLA escalates and notifies without any client request.

### S4.4 Observability — **M**, risk low, reversibility high
- **Why:** zero hits for OpenTelemetry, Prometheus, structlog or Sentry. Logging is `logging.basicConfig` (`main.py:47-51`) plus a timing middleware setting `X-Process-Time-Ms` (`:119-126`). No `/metrics`. `README.md:121,157` and Wiki §13 claim all of it.
- **Do:** structured JSON logs with request/tenant/case correlation ids, OTel traces across API → engine → RAG → DB, `prometheus-fastapi-instrumentator` for `/metrics`, error tracking, and the four alerting rules the Wiki already specifies (`FinShield-AI-Wiki.md:676-689`).
- **Validation:** a single screening produces one trace with spans for rules/behavioral/RAG/gating; a Grafana dashboard shows p95 latency and flag rate.

### S4.5 Backup, restore, retention — **S**, risk low, reversibility high
- **Why:** no backup or restore script exists. `DOCKER.md:121-133` says `docker cp` the SQLite file; `DEPLOYMENT.md:391-399` says "Neon auto-backs up". SAR/STR records carry a 5-year retention obligation (FinCEN), and the audit chain is worthless if it can be lost.
- **Do:** scheduled `pg_dump` to object storage with retention, a *tested* restore runbook, and a documented retention matrix per data class.
- **Validation:** a restore into a clean environment reproduces the audit chain verification from S3.2.

---

## Phase 5 — Frontend product quality (design review track)

Design-review findings come from the `design-review` plugin lenses (design-debt, accessibility, component-library-alignment).

### S5.1 DESIGN.md + token completion — **S**, risk low, reversibility high
- **Why:** no `DESIGN.md` or token file exists. `tailwind.config.js:10-32` is genuinely semantic (`bg/surface/border/ink/accent/teal/navy` + `success/warning/danger/info` + shadow tokens) — a real foundation — but there is no typography or spacing scale, no `fontFamily` token (Inter is loaded by `<link>` at `layout.tsx:14-16`), and pages bypass the tokens with raw palette classes (`bg-emerald-500`, `text-red-600` at `reports/page.tsx:73-76`, `transactions/page.tsx:188,499`; `border-gray-300`/`focus:ring-blue-500` at `filings/page.tsx:88,101`).
- **Do:** author `DESIGN.md` (token table, component rules, do/don't), add type and spacing scales, and lint against raw palette usage.
- **Validation:** `grep -rE "(bg|text|border)-(emerald|red|gray|blue|amber)-[0-9]{3}" src/` returns zero hits outside the token definitions.

### S5.2 UI primitives — **M**, risk medium, reversibility medium
- **Why:** there are no reusable primitives — zero `Button`/`Input`/`Card`/`Badge`/`Modal`/`Table` components; only three layout components (`PlatformLayout`, `Sidebar`, `Topbar`). Status badges, modal shells and table markup are duplicated per page (e.g. `<thead>` repeated at `dashboard/page.tsx:200-206` and `transactions/page.tsx:231-235`). Debt counts in `src/`: 67 arbitrary Tailwind values (worst: `transactions/page.tsx` 16, `Topbar.tsx` 15, `cases/page.tsx` 8), 16 hardcoded hex, 8 inline `style={{}}` (`dashboard/page.tsx:114,158`, `settings/page.tsx:405,434`, `transactions/page.tsx:345,375`, `Sidebar.tsx:169`, `reports/page.tsx:84`), 79 raw px values.
- **Do:** decide D5, then extract the primitives and migrate pages one at a time; each primitive owns its focus, disabled, error and empty variants so a11y is fixed once rather than per page.
- **Validation:** no page contains a raw `<table>` or a hand-rolled modal; arbitrary-value count trends to zero.

### S5.3 Accessibility baseline — **M**, risk low, reversibility high
- **Why:** 12 `aria-*` occurrences in the whole app, all `aria-required="true"`; zero `role=`, zero `aria-label`, zero `sr-only`, zero `<caption>`. Icon-only buttons in `Topbar.tsx` have no accessible name. ~12 of 42 form controls lack an associated `<label>` (30 `htmlFor`). No `<th scope="col"` anywhere. Only 2 `focus:` styles in `src/` — custom-styled buttons have no visible focus ring. Risk bars (`transactions/page.tsx:375`) and the dashboard donut (`dashboard/page.tsx:114`) encode meaning by colour alone. Modals have no focus trap or Escape handling.
- **Do:** label every control, `scope="col"` + captions on tables, `aria-label`/`aria-hidden` on all icon buttons and decorative SVGs, `focus-visible` rings globally, focus trap + Escape on modals, and text/`aria-valuenow` alternatives for colour-only encodings. Target WCAG 2.1 AA.
- **Validation:** axe scan with zero serious/critical violations; keyboard-only walkthrough of screen → case → filing completes.

### S5.4 Data layer — **M**, risk medium, reversibility medium
- **Why:** dependencies are only `next`, `react`, `react-dom` (`package.json:11-15`) — no SWR/react-query. Every page hand-rolls `'use client'` + `useEffect` + `loading/error/data`. The client is well typed (~30 interfaces, no `any`) but: base URL is a hardcoded relative `'/api'` (`lib/api.ts:7`) relying on the rewrite in `next.config.js:7-13`; the JWT lives in `localStorage` (`api.ts:358-370`) which is XSS-readable; there is no 401 interceptor, so an expired token surfaces as a raw error string; `api.ts:396` contains dead code (`body.detail || body.detail?.message`); pagination is ignored in the UI (`transactions/page.tsx:37` fetches a flat 100) although the API supports limit/offset; and there are no optimistic updates.
- **Do:** adopt SWR or react-query, add pagination controls, add a 401 interceptor that clears the session and redirects, decide token storage (httpOnly cookie session vs localStorage + CSP — see D5/D10 notes), and remove the dead error branch.
- **Validation:** a 10 000-transaction list paginates; expiring a token mid-session redirects to `/login` instead of showing an error banner.

### S5.5 Route protection and role-gated navigation — **M**, risk medium, reversibility high
- **Why:** there is **no `middleware.ts`** in the repo. `isAuthenticated` is checked only in the root redirect (`page.tsx:12`); `/dashboard`, `/transactions`, `/cases`, `/filings`, `/rules`, `/settings` and `/api-keys` all render for logged-out users and fail at the API layer. `PlatformLayout.tsx:7-18` performs no gating. Authentication is real; authorization in the UI is cosmetic.
- **Do:** add `middleware.ts` guarding the platform segment, gate nav items on the role from S3.1, and show a proper unauthenticated state rather than a cascade of 401 errors.
- **Validation:** loading `/cases` while logged out redirects to `/login` with a return path; an analyst never sees admin nav.

### S5.6 Surface the built-but-unused backend + real API docs — **M**, risk low, reversibility high
- **Why:** eight working backend capabilities have no UI: `/api/v1/rules/simulate` (`main.py:1454`), `/rules/{id}/stats` (`:1512`), `/cases/{id}/notes` (`:1699`), `/cases/check-sla` (`:1749`), `/cases/aggregate` (`:1801`), all three `/behavioral/*` (`:2170-2328`), `/health/circuit-breakers*` (`:2381+`) and `/webhooks/dispatch` (`:2589`). Meanwhile `platform-app/src/app/docs/page.tsx:6-40` is a hardcoded `ENDPOINTS` array that has already drifted (it omits filings, notifications, search and rules-simulate).
- **Do:** build the rule simulator, case notes, SLA/aggregation views, a behavioral-baseline panel, an ops/circuit-breaker health page and a webhook management page; generate the docs route from the backend's OpenAPI schema instead of a literal array.
- **Business path unlocked:** the Risk Officer and Admin user stories (`FinShield-AI-Wiki.md:1081,1088`) which currently have no screens.
- **Validation:** the docs route lists exactly the routes FastAPI exposes; each new screen round-trips against a live backend.

### S5.7 Live updates — or drop the claim — **M**, risk low, reversibility high
- **Why:** zero WebSocket/EventSource usage. The "real-time dashboard" claim (`README.md:44`, `dashboard/page.tsx:67`) is backed by one 30s `setInterval` poll for unread notifications (`Topbar.tsx:240-245`); the dashboard itself never refreshes.
- **Do:** either add SSE/WebSocket push for case and transaction events (worker emits, S4.1) or change the copy to "auto-refreshing" and add honest polling with a visible last-updated timestamp.
- **Validation:** a new flagged transaction appears in the open dashboard without a manual reload — or the UI no longer claims it will.

### S5.8 Retire dead frontends — **S**, risk low, reversibility high
- **Why:** `website/platform/{api-keys,cases,dashboard,transactions}.html` (169/182/378/134 lines) contain **zero** `fetch`/`XMLHttpRequest`/`localStorage` calls — hardcoded mockups ("42,180 credits", "Welcome back, John" at `website/platform/dashboard.html:110,127`) that duplicate platform-app screens. Nothing links to them, and they are not in compose. `website/pages/login.html` and `signup.html` are 13-line stubs — broken entry points on a live marketing site. `website/css/` is a third design system (3278 + 835 + 824 lines of hand-written BEM) unrelated to the Tailwind tokens, though `tailwind.config.js:11,17` notes the palette was copied from it.
- **Do:** delete `website/platform/*`, either implement or remove the login/signup stubs (link to platform-app), and decide whether the marketing site shares tokens with the app (D7).
- **Validation:** `website/` contains no non-functional console; marketing CTAs reach a working login.

---

## Phase 6 — Market readiness

### S6.1 Payments — **M**, risk medium, reversibility medium
- **Why:** billing is DB-persisted with no provider: `PLANS` is a hardcoded list (`main.py:874`), subscribe/checkout/purchase endpoints (`:962,:1044,:1151`) move credits without charging anyone, and card data is stored as plaintext last4/expiry/holder columns (`db_models.py:46-48`). `DEPLOYMENT.md` references a PayMongo key for code that does not exist. This is both a revenue gap and a PCI-scope problem.
- **Do:** decide D8, integrate hosted checkout (keeps you in SAQ-A), replace card columns with provider customer/payment-method ids, add webhook-driven entitlement updates, and write dunning/refund handling.
- **Validation:** a test-mode checkout grants credits; no card number or expiry exists in the database.

### S6.2 Deployment target, TLS and security headers — **M**, risk medium, reversibility medium
- **Why:** `website/nginx.conf` listens on port 80 only (`:2`) with `X-Frame-Options`/`nosniff`/`X-XSS-Protection` (`:13-15`) but **no HSTS, no CSP, no Referrer-Policy** — and the `add_header` inside the static-asset `location` (`:20`) drops the parent-level headers for those paths (nginx inheritance quirk). `platform-app/next.config.js:1-17` has only `output: 'standalone'` and API rewrites: the authenticated compliance dashboard is served with **zero** security headers. No Kubernetes manifests, Helm charts or Terraform exist despite `README.md:301-311`.
- **Do:** choose the deploy target (D9 notes), terminate TLS at the edge, add `headers()` to `next.config.js` (CSP, HSTS, Referrer-Policy, X-Content-Type-Options, frame-ancestors), fix the nginx inheritance, and add a backend security-headers middleware.
- **Validation:** an A+ SSL Labs grade and a passing security-header scan on all three surfaces; a CSP violation report shows no inline-script breakage.

### S6.3 Container hardening — **M**, risk low, reversibility high
- **Why:** `platform-app/Dockerfile:2` uses `node:18-alpine` — Node 18 is EOL. All three images run as root with no `USER`, no `HEALTHCHECK`, no digest pinning, and no multi-stage builds; `backend/Dockerfile:7-9` installs `gcc` and never removes it, and ships `pytest`/`httpx` in the runtime image. `next.config.js:3` sets `output: 'standalone'` but `Dockerfile:28` runs `npm start`, so the slim standalone `server.js` is never used and the full toolchain plus `node_modules` ships. `platform-app/Dockerfile:15-16` bakes `NEXT_PUBLIC_API_URL=http://localhost:8091` at build time — `NEXT_PUBLIC_*` is inlined, so the runtime compose value (`docker-compose.yml:56`) cannot override it and any non-localhost deploy is broken.
- **Do:** move to Node 22 LTS, multi-stage builds, non-root users, digest-pinned bases, `HEALTHCHECK` in each image, drop build tooling from runtime stages, actually use the standalone output, and solve the `NEXT_PUBLIC` build-time problem (runtime config endpoint, relative `/api` rewrite only, or per-env builds).
- **Validation:** `docker inspect` shows a non-root user and a healthy status; image size drops materially; a deployed frontend reaches its API from a non-localhost origin.

### S6.4 Python SDK for integrators — **M**, risk low, reversibility high
- **Why:** `README.md:217` and Wiki §19 list `sdk/`; it does not exist. The "Platform/Integrating Engineer" story (`FinShield-AI-Wiki.md:1102`) currently means hand-rolling HTTP against 68 routes.
- **Do:** generate a typed client from the OpenAPI schema (avoid hand-maintenance drift), add retries with idempotency-key propagation, and publish it versioned alongside the API.
- **Validation:** the SDK's integration test screens a transaction and reads back the decision and reasons.

### S6.5 Load and performance testing — **M**, risk low, reversibility high
- **Why:** `README.md:288-289` documents `locust -f tests/load/test_throughput.py`; no load test exists. S1.3 (event-loop blocking) means current throughput is unmeasured and almost certainly poor under concurrency.
- **Do:** add locust or k6 scenarios for screening submit, case list and RAG search; set p95 targets; run nightly.
- **Validation:** a documented p95 screening latency that survives a 10× concurrency increase after S1.3.

### S6.6 Regulatory evidence pack — **M**, risk low, reversibility high
- **Why:** selling to compliance teams requires artefacts, not claims: model cards, retention matrix, audit export procedure, access-control matrix, incident runbook, and an honest control narrative. Today the Wiki asserts readiness (`FinShield-AI-Wiki.md:805-833,1181`) that the code does not support.
- **Do:** assemble the pack from S2.5 (model cards), S3.2 (audit export), S3.3 (retention/erasure), S3.1 (access matrix), S4.5 (backup/restore) and S0.4 (monitoring), and state clearly which controls are automated vs procedural.
- **Validation:** a security questionnaire can be answered from the pack with evidence links, and every "yes" traces to a passing test or a runbook.

### S6.7 Kubernetes / Helm — **L**, risk medium, reversibility medium — *conditional*
- **Why:** `README.md:301-311` documents `helm repo add finshield ./deploy/k8s`; no `deploy/` directory exists. Only build this when an enterprise deal requires it — a hardened compose or managed-platform deploy (S6.2) covers most of the market.
- **Validation:** a Helm install into a clean cluster passes the S6.5 load profile with HPA scaling.

---

## Critical path

`S0.2 + S0.3 → S1.1 → S1.2 → S2.5 → S2.7 → S3.2 → S6.6`

Secrets and CI must be fixed before anything merges safely; Postgres must be primary before schema can be versioned; versioned schema is required for `model_versions`, sanctions tables, tenant columns and audit constraints; a versioned model cannot be shipped without an eval harness; and none of it is sellable to a compliance buyer without an immutable, exportable audit trail and an evidence pack.

**Parallelisable now, independently:** S0.1, S0.4, S0.5, S1.5, S5.1, S5.3, S5.8, S6.3.
**Blocked until a decision is made:** S2.5 (D1), S2.4 (D4), S3.4 (D3), S4.1 (D2), S5.2 (D5), S6.1 (D8), S6.2/S3.5 (D9).

## Sequencing rules

1. Never start P2 feature work while `create_all` is the schema mechanism — every model change would need a manual DB delete.
2. Never expose a new admin surface before S3.1; today every authenticated user is effectively an admin.
3. Do not delete the Wiki's target-state content — relabel it. It is the best specification in the repo; the problem is the tense, not the content.
4. Each slice must land with its own validation signal in CI before the next one starts, or the gap map silently regrows.
