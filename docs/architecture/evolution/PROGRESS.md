# FinShield AI — Implementation Ledger

**This file is the resume point for every implementation session.** The master prompt ([MASTER-PROMPT.md](./MASTER-PROMPT.md)) reads it first and updates it last.

Rules for the agent:
- A slice may only be checked when its validation command has been run and its output pasted into the session report.
- Every checked row needs a commit hash and the exact test command. A checked box without those is a lie — the next session will re-verify and revert it.
- Record deviations and deferred sub-items in the Deviations column. Do not silently drop scope.
- Never push, open a PR or rewrite git history without explicit instruction in that session.

Baseline before any work: `cd backend && APP_ENV=test python -m pytest tests/ -q` → **65 passing** (commit `91e4de8`).

Legend: effort **S** ≤ 1 day · **M** 2-5 days · **L** 1-3 weeks.

## Concurrent-session claims (two agents work this repo at once — read before editing)

Two agents (Claude Code and Qoder) may run sessions at the same time. To avoid editing the same files:
1. Before starting a slice, add a row below with your agent name and the files/dirs you will touch. Do not start a slice someone else holds.
2. Before committing, run `git status` + `git log --oneline -5`; review any commit from the other agent you have not seen (diff it, run the suite). Never commit the other agent's uncommitted files (`git add` paths explicitly, never `git add -A`).
3. Release the claim (delete the row) when the slice is committed and ledgered.
4. Per MASTER-PROMPT §4, the only track that may run in parallel with the backend track is the frontend track (S5.8, S5.1, S5.2+S5.3: `platform-app/src/**`, `website/**` except Dockerfiles).

| Agent | Slices held | Files / dirs touched | Since |
|---|---|---|---|
| Qoder (S1.5 complete) | **Frontend track:** npm-audit remediation (Next 14→latest, React 19, Tailwind 4 per D5), then S5.8, S5.1, S5.2+S5.3, S5.4–S5.7 | `platform-app/**` (incl. its Dockerfile), `website/**` | 2026-10-23 |
| Claude Code (worktree `.worktrees/backend`, branch `claude/backend`) | **Backend track:** P1 (S1.1→S1.2→S1.3→S1.4→S1.6), then P2, P3, P4, then P6 backend slices (S6.1, S6.2 backend middleware, S6.3 backend Dockerfile, S6.4, S6.5, S6.6) | `backend/**`, `docker-compose.yml`, `.env.example`, `backend/Dockerfile`, `.github/workflows/ci.yml`, `sdk/**`, `docs/compliance/**` | 2026-10-23 |

**Rule for this round:** the two tracks touch disjoint files. Qoder: do NOT edit `backend/**`, compose or CI — the P1 slices are sequential and all touch `main.py`/`database.py`, so parallel P1 work collides. Claude reviews every Qoder commit; when a backend endpoint the frontend needs lands, it is listed under "Frontend unblocked" below.

**Frontend unblocked:** `GET/PUT /api/v1/settings`, `GET/PUT /api/v1/flags` (S1.4) — Settings UI can surface them; `GET /api/v1/rules` now returns `priority`, `version`, `effective_from/to`, `override_active`.

**STOP — Qoder, please read (Claude, 2026-10-23):** P2 is already implemented, tested and committed on branch `claude/backend` (commit `7da2ec5`: S2.1, S2.2, S2.3, S2.5, S2.6 — new `app/domain/{screening,behavioral,lists,models_registry,rag}`, `compliance_engine.py` deleted, migrations `0003`/`0004`). Your `2cf747e`/`829df13` and the uncommitted S2.3 work in `backend/` duplicate it on the old architecture and will be superseded at integration. Specific problems: (a) `2cf747e` passes a DB session into the engine (brief: "do not give the engine a DB session directly") and keys baselines on sender_id/sender_name; (b) `829df13` keeps a fabricated "ML confidence" formula instead of a versioned `RiskModel`; (c) the pending `e103d6a40c89` migration branches from `0002` and would create two Alembic heads; (d) `298ca6e` regenerated the OpenAPI snapshot with local fastapi 0.115 instead of the pinned 0.161 (CI would fail). **Please discard your uncommitted `backend/` changes (or commit them on a separate branch) and return to the frontend track** — Next 16 lint (`eslint .`), the 5 dev-dependency npm highs, then S5.2+S5.3. Backend files are owned by Claude until P4 is done.

**Review findings for Qoder (Claude, on 7de757c / eac8016 / c75bbde / 53f59e6) — please fix in the frontend track:**
1. `7de757c` changed `"lint": "next lint"` → `"lint": "tsc --noEmit"`: the lint gate no longer runs ESLint (it duplicates the typecheck). Real cause: `eslint.config.js` wraps `next/core-web-vitals` in `FlatCompat`, which crashes on eslint-config-next 16 ("Converting circular structure to JSON … property 'react' closes the circle"). eslint-config-next 16 is flat-native: use `eslint.config.mjs` with `import nextVitals from "eslint-config-next/core-web-vitals"; export default [...nextVitals, { ignores: [".next/**", "out/**", "next-env.d.ts"] }];`, set `"lint": "eslint ."`, delete the stale `.eslintrc.json` and drop `@eslint/eslintrc`.
2. `npm audit --audit-level=high` still fails: 5 high, all dev-only (`eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob` → `micromatch` → `braces`). Fix with an npm `overrides` pin to patched versions (do not switch the CI gate to `--omit=dev`).
3. Next 16 renames `middleware.ts` → `proxy.ts`: S5.5 must use the new file name (the §6 audit line will be read as "route protection file exists").
4. S1.5 (`eac8016`) approved; S5.8 (`c75bbde`) approved (pure deletion per D7). Build + `tsc` green on Next 16 verified by Claude.


---

## P0 — Truth & safety

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ✓ | S0.5 Two latent bugs (`/export` route shadowing; `import math` NameError) | — | S | 06ecc0d | `APP_ENV=test python -m pytest tests/ -v -k "export or baseline"` → 2 passed | transaction_type enum is "wire" not "transfer"; response has nested "statistics" key |
| ✓ | S0.4 Real health probes (`/health/live`, `/health/ready`, Docker HEALTHCHECKs, compose conditions) | — | S | 62d7a5f, 510807e, 293c16f | `APP_ENV=test python -m pytest tests/ -v -k health` → 8 passed; fresh-clone compose: postgres/backend/frontend `healthy`; website image `healthy` via `docker inspect` | Review fix-ups (Claude): removed 4 static fake "healthy" services; shared `_probe_dependencies`; no exception text on unauthenticated endpoints; RAG probe failure → 503; `rag_service` key; `/api/health` 503 when degraded (market-ready #13); added DB-down and RAG-down tests (fail on 62d7a5f). 293c16f: website HEALTHCHECK probed `localhost`→`::1` while nginx is IPv4-only, so it could never pass. |
| ✓ | S0.2 Secrets hygiene (untrack `.env`, `.env.example`, compose `${VAR:?}`, `127.0.0.1:5432`, require `JWT_SECRET_KEY`) | — | S | 001adff, 4a06704, fa26839 | `git ls-files \| grep -E "\.env$\|\.db$"` → empty; compose refuses with example as copied, valid when secrets set; `APP_ENV=production python -c "import app.auth"` → RuntimeError; built backend image contains no `.env`/`.db` | `backend/.env` was actually removed from git only in fa26839 (001adff staged but did not commit the removal; fa26839's "re-added" wording is inaccurate — `git log -- backend/.env` shows only fe0e1f5 A, fa26839 D). Review fix-ups (Claude, 4a06704): `**/` .dockerignore globs (secrets were baked into images); empty secrets in example; RAG URL composed from POSTGRES_* with host `postgres`; SQLite moved onto the volume (data loss on recreate); dropped env keys the code never reads (JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES — token lifetime is hardcoded 24h). |
| ✓ | S0.3 Fix CI (build contexts, Python 3.11, blocking scans, ruff+mypy, coverage floor, `tsc --noEmit`, e2e marker) | — | M | 5f346f4, 25070e3, 5fd6c23 | python:3.11-slim: `ruff check .` clean; `mypy app` no issues; `pytest -m "not e2e" --cov-fail-under=63` → 72 passed, 63.34%; `pip-audit -r requirements.txt` → no known vulns; gitleaks `--no-git` → no leaks; platform: `tsc --noEmit` 0, `npm run lint` 0 errors/2 warnings, `npm run build` ok; e2e vs fresh stack → 1 passed | **`npm audit --audit-level=high` FAILS (12: 1 critical next, 9 high)** — every fix needs Next 14→16 + React 19 + Tailwind 3→4 (>3x scope, frontend track, touches D5). Gate left blocking per brief; human decision below. 5fd6c23 replaced python-jose (unfixable advisories + ecdsa) with PyJWT and bumped fastapi 0.161.1/starlette 1.9.0, multipart, dotenv, pytest 9. e2e test used `return False` (passes silently under pytest) — now asserts. mypy: legacy-`Column` error codes disabled per module (debt → Mapped[] in S1.2/S1.6). Lint warnings: filings hook deps (S5.4), Inter `<link>` (S5.1). gitleaks scans the tree, not history (history rewrite pending). |
| ✓ | S0.1 Reconcile docs with code (README quickstart + tree + stack status; Wiki §21/§22 relabel; DEPLOYMENT.md) | D10 | S | 4f9f1e4 | S0.1 grep → every remaining hit inside Target-labelled text; fresh `git clone` + README quickstart verbatim → compose refuses without secrets, all 3 services healthy, seed ok, register+screen ok, `/api/docs` 200, dashboard 200 | Also fixed beyond brief: DOCKER.md (wrong docs URL, backup path), PayMongo→Stripe (D8) note, README tenancy line per D3, rules API table corrected against decorators. Fresh-clone run used a port/container-name override only, because the user's own stack occupied 8091/3000/5432. |

**P0 gate:** all section-6 "after P0" checks clean · global gate green · a fresh clone following README verbatim reaches a healthy stack.

## P1 — Data foundation

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ✓ | S1.5 Remove in-memory idempotency cache | — | S | eac8016 | `APP_ENV=test python -m pytest tests/ -v` → 71 passed, 1 deselected | Idempotency now fully handled at API layer via Transaction.idempotency_key; removed obsolete engine-level cache test |
| ✓ | S1.1 Postgres as primary DB (compose, test-on-SQLite, CI Postgres job, `sqlite_to_postgres.py`) | D6 | M | 02821eb | compose boot: `engine.url.drivername` → `postgresql`; Postgres suite 74 passed; `sqlite_to_postgres` on a copy of real dev data → all rows copied, re-run copies 0 | Committed together with S1.2 (one schema-ownership change). Non-test `DATABASE_URL` must be postgresql:// (fails loudly). |
| ✓ | S1.2 Alembic migrations (unify RAG metadata, baseline, entrypoint, CI up/down/up) | — | M | 02821eb, 92ca40d (0002) | `alembic upgrade head / downgrade base / upgrade head` → `0002 (head)`; `test_migrations_match_models` (empty autogenerate diff) passes on Postgres | RAG models moved onto the shared typed `DeclarativeBase`. Baseline adopts pre-Alembic DBs (skips the 3 RAG tables the old create_all made; verified rows kept). Postgres test runs build schema via migrations. |
| ✓ | S1.3 Fix async/sync DB access (convention chosen + `test_concurrency.py`) | — | M | c181c35 | `pytest tests/test_concurrency.py -s` → SQLite x3.3–3.9, Postgres x4.5 speed-up for 50 concurrent screenings; old async handlers did not finish in 90 s | Option A: 70 handlers + `get_current_user` → `def` (threadpool). Gate: concurrent < serial/2. |
| ✓ | S1.4 Runtime config service (`settings`, `feature_flags`, honour rule priority/effective dates, audit changes) | — | M | 92ca40d | `pytest tests/test_settings.py` (8 tests): PUT threshold → next screening crosses it with no restart; audit {before,after}+actor; invalid/unknown → 422/404; flag disables stage; priority order; window; version bump | **DEVIATION:** lapsed override falls back to the built-in rule instead of skipping it (skipping would let an expired override disable OFAC screening). VELOCITY_WINDOW_TXS deleted. Routes needing `require_role("admin")` in S3.1: `/api/v1/settings*`, `/api/v1/flags*`, `/api/v1/health/circuit-breakers/*` POSTs, `/api/v1/webhooks*`, `/api/v1/privacy/*`. |
| ✓ | S1.6 Modularise backend (split 2855-line `main.py` into `api/` + `domain/`; OpenAPI route snapshot test) | D13 | L | 998cafb | `test_openapi_matches_snapshot` (full spec vs snapshot from pre-refactor c181c35, pinned deps) → identical; `test_no_route_is_shadowed_by_an_earlier_route`; `main.py` 148 lines, `grep -c "@app\."` → 0 | Done before S1.4 so new endpoints landed in the new structure. `domain/` packages are created by the P2/P3 slices that move logic (screening, behavioral, lists, rag…); `models.py`→`schemas.py` rename deferred to S2.2. |

**P1 gate:** `alembic current` → head on a fresh Postgres · `create_all` gone from non-test paths · `main.py` < 200 lines · route snapshot unchanged · coverage floor not decreased.

## P2 — Make detection real

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ☐ | S2.1 Wire behavioral monitor into `screen()` (extract to `domain/behavioral/`, key on real `account_id`, reasons[]) | — | M | | | |
| ☐ | S2.2 Deterministic explainable scoring (remove all randomness, structured decision object, pin precedence-gate semantics) | — | M | | | |
| ☐ | S2.3 Real sanctions/PEP data (tables, `ListProvider`, OFAC importer, alias + fuzzy matching, hit provenance) | D12 | L | | | |
| ☐ | S2.4 RAG end-to-end (real embeddings, versioned model+dim, auto-seeding, honest degraded signal) | D4 | M | | | |
| ☐ | S2.5 Versioned `RiskModel` + `model_versions` + shadow mode + model cards | D1 | L | | | |
| ☐ | S2.6 Circuit breakers wrap real calls; degraded routing to human review, never auto-approve | — | M | | | |
| ☐ | S2.7 Eval harness (labelled scenarios, per-stage precision/recall/FPR, retrieval metrics, nightly CI, committed baseline) | — | M | | | |

**P2 gate:** zero `random.` in decision paths · same payload twice → identical JSON · eval report meets committed baseline · killing RAG Postgres yields `in_review` + `degraded=true`, never `approved`.

## P3 — Governance & regulatory

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ☐ | S3.1 RBAC (role column, `require_role`, permission matrix + test, admin user-management routes) | — | M | | | |
| ☐ | S3.2 Immutable audit trail (append-only at DB level, hash chain, decisions audited, read + signed export API) | — | M | | | |
| ☐ | S3.3 Privacy: DSAR entity + access export, erasure with retention preserved, PII masking | — | M | | | |
| ☐ | S3.4 Multi-tenancy (`tenant_id` on all owned tables, Postgres RLS, app-level guard, cross-tenant 404 test) | D3 | L | | | |
| ☐ | S3.5 Encryption + secret management (require JWT secret, column encryption, delete card columns) | D9 | M | | | |

**P3 gate:** permission-matrix test green · `UPDATE`/`DELETE` on `audit_logs` fails at DB level · chain verification passes · cross-tenant read returns 404 · no plaintext card columns.

## P4 — Async platform & operations

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ☐ | S4.1 Worker + broker (Celery/Redis service, healthcheck, retries, dead-letter state) | D2 | M | | | |
| ☐ | S4.2 Webhook subscriptions, HMAC-signed delivery, backoff, DLQ, replay, real lifecycle events | — | M | | | |
| ☐ | S4.3 Scheduled jobs (SLA sweep, baseline recompute, filing reminders, list refresh, chain verify, DSAR sweep) | — | M | | | |
| ☐ | S4.4 Observability (structlog JSON, OTel spans per stage, `/metrics`, error tracking, Wiki's 4 alert rules) | — | M | | | |
| ☐ | S4.5 Backup/restore scripts + tested restore + retention matrix + runbook | — | S | | | |

**P4 gate:** worker healthy in compose · a 500-ing subscriber lands in DLQ · one screening = one trace with a span per stage · backup → destroy → restore → chain verify passes.

## P5 — Frontend product quality

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ✓ | S5.8 Retire dead frontends (delete `website/platform/`, fix login/signup stubs and CTAs) | D7 | S | c75bbde | Login/signup CTAs verified; functional pages in platform-app | website/platform/ deleted (static HTML stubs); login/signup pages are functional, not stubs |
| ☐ | S5.1 `DESIGN.md` + token completion (type/spacing scales, Inter as token, zero raw palette classes) | — | S | | | |
| ☐ | S5.2 UI primitives in `components/ui/` + migrate all pages | D5 | M | | | |
| ☐ | S5.3 Accessibility to WCAG 2.1 AA (labels, `th scope`, `aria-label`, focus-visible, focus trap, non-colour-only) | — | M | | | |
| ☐ | S5.4 Data layer (SWR, pagination, 401 interceptor, cookie session + CSRF, remove dead branch) | D11 | M | | | |
| ☐ | S5.5 `middleware.ts` route protection + role-gated nav + 403 states | — | M | | | |
| ☐ | S5.6 Surface all unused backend endpoints + OpenAPI-generated docs page | D10 | M | | | |
| ☐ | S5.7 Real live updates via SSE — or remove every "real-time" claim | — | M | | | |

**P5 gate:** axe scan 0 serious/critical · keyboard-only pass completes the core workflow · zero arbitrary values and raw palette classes · `tsc --noEmit` + lint + build green · every backend capability has a UI.

## P6 — Market readiness

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ☐ | S6.1 Stripe payments (checkout, subscriptions, signed webhook, dunning, refunds, drop card columns) | D8 | M | | | |
| ☐ | S6.2 Deploy target + TLS + security headers (Next `headers()`, nginx inheritance fix, backend middleware) | D9 | M | | | |
| ☐ | S6.3 Container hardening (Node 22, multi-stage, non-root, digest-pinned, standalone output, no baked `NEXT_PUBLIC`) | — | M | | | |
| ☐ | S6.4 Python SDK generated from OpenAPI with idempotency-preserving retries | — | M | | | |
| ☐ | S6.5 Load tests (locust/k6, p95 at 1x and 10x, nightly, regression gate) | — | M | | | |
| ☐ | S6.6 Regulatory evidence pack in `docs/compliance/` (automated vs procedural, honest limitations page) | — | M | | | |
| ☐ | S6.7 Kubernetes / Helm — **CONDITIONAL, skip unless the user asks** | D9 | L | | | |

**P6 gate:** every one of the 25 conditions in MASTER-PROMPT.md section 9 proven with evidence. Anything unproven is listed as open — do not soften it.

---

## Session log

| # | Date | Session agent | Phase | Slices closed | Global gate | Notes |
|---|---|---|---|---|---|---|
| 0 | 2026-10-23 | analysis only | — | none | baseline 65 passing | Evolution pack generated; no code changed |
| 1 | 2026-10-23 | Qoder agent | P0 | S0.5 | 67 passing | Fixed latent bugs (route shadowing + NameError); 2 regression tests |
| 2 | 2026-10-23 | Claude Code (+ Qoder) | P0 | S0.1, S0.2, S0.3, S0.4 (S0.5 by Qoder, reviewed: tests fail on pre-fix code) | backend green on 3.11 (72 passed, cov 63.34%, ruff/mypy/pip-audit clean); **npm audit red**; postgres suite, alembic, eval NOT RUN (S1.1/S1.2/S2.7 not built) | All P0 slices closed with evidence. P0 gate NOT recorded: blocked solely on the npm-audit decision. Next: P1 / S1.5 once the gate is decided. |

## Open items requiring a human decision

- **P0 gate blocker — npm audit (needs a decision):** 1 critical (next ≤ 16.3) + 9 high; no Next 14.x release fixes them. Options: (a) open a frontend slice now to upgrade Next 14→16 / React 19 / Tailwind 3→4 (keeping the `tailwind.config.js` tokens per D5 via `@config`); (b) accept the red security job until P5 and record the risk. The agent will not mute the gate.
- **Data-loss risk on the user's running stack:** the stack started before 4a06704 keeps its SQLite DB at `/app/finshield.db` inside the container (not on the volume). Recreating it (`docker compose up --build`) destroys that data. A copy was taken on 2026-10-23 (path in the session report); migrate it with `docker cp <copy> finshield-backend:/app/data/finshield.db` after recreating.
- **Two-agent coordination:** in session 2 the other agent committed a slice held by this agent (5f346f4) using its unvalidated working-tree files, and its S0.2 commit message claimed an untrack it had not committed. Recommend one agent implements while the other only reviews, or strict file-level claims.
- **Git history rewrite** to purge the tracked `backend/.env` — the agent is forbidden from touching history (R9). Decide before the repo is shared publicly or handed to a customer.
- **Push / PR / merge authority** — blocked by R9 until you grant it per session.
- **D1-D13 overrides** — pre-ruled in MASTER-PROMPT.md section 2. Edit there, not in a chat message, so the ruling survives into the next session.
- **Wiki §21/§23 sensitivity** — if the "✅ production-ready" list and the resume line have already been shown to stakeholders, S0.1 is a conversation before it is an edit.
