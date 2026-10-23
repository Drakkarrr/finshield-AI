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
| Qoder (observed in working tree) | P0: S0.5 → S0.4 → S0.2 (front of P0) | `backend/app/main.py`, `backend/app/auth.py`, `backend/tests/test_api.py`, `*/Dockerfile`, `docker-compose.yml`, `.env.example` | 2026-10-23 |
| Claude Code | P0: S0.1 → S0.3 (back of P0) + review of every Qoder change | `README.md`, `FinShield-AI-Wiki.md`, `DEPLOYMENT.md`, `DOCKER.md`, `.github/workflows/ci.yml`, `backend/pytest.ini`, `backend/requirements-dev.txt`, `backend/ruff.toml`, `backend/mypy.ini`, `backend/tests/e2e/**` | 2026-10-23 |

---

## P0 — Truth & safety

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ✓ | S0.5 Two latent bugs (`/export` route shadowing; `import math` NameError) | — | S | 06ecc0d | `APP_ENV=test python -m pytest tests/ -v -k "export or baseline"` → 2 passed | transaction_type enum is "wire" not "transfer"; response has nested "statistics" key |
| ☐ | S0.4 Real health probes (`/health/live`, `/health/ready`, Docker HEALTHCHECKs, compose conditions) | — | S | | | |
| ☐ | S0.2 Secrets hygiene (untrack `.env`, `.env.example`, compose `${VAR:?}`, `127.0.0.1:5432`, require `JWT_SECRET_KEY`) | — | S | | | |
| ☐ | S0.3 Fix CI (build contexts, Python 3.11, blocking scans, ruff+mypy, coverage floor, `tsc --noEmit`, e2e marker) | — | M | | | |
| ☐ | S0.1 Reconcile docs with code (README quickstart + tree + stack status; Wiki §21/§22 relabel; DEPLOYMENT.md) | D10 | S | | | |

**P0 gate:** all section-6 "after P0" checks clean · global gate green · a fresh clone following README verbatim reaches a healthy stack.

## P1 — Data foundation

| ✓ | Slice | Decision | Effort | Commit | Test command run | Deviations |
|---|---|---|---|---|---|---|
| ☐ | S1.5 Remove in-memory idempotency cache | — | S | | | |
| ☐ | S1.1 Postgres as primary DB (compose, test-on-SQLite, CI Postgres job, `sqlite_to_postgres.py`) | D6 | M | | | |
| ☐ | S1.2 Alembic migrations (unify RAG metadata, baseline, entrypoint, CI up/down/up) | — | M | | | |
| ☐ | S1.3 Fix async/sync DB access (convention chosen + `test_concurrency.py`) | — | M | | | |
| ☐ | S1.4 Runtime config service (`settings`, `feature_flags`, honour rule priority/effective dates, audit changes) | — | M | | | |
| ☐ | S1.6 Modularise backend (split 2855-line `main.py` into `api/` + `domain/`; OpenAPI route snapshot test) | D13 | L | | | |

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
| ☐ | S5.8 Retire dead frontends (delete `website/platform/`, fix login/signup stubs and CTAs) | D7 | S | | | |
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
| 1 | 2026-10-23 | Qoder agent | P0 | S0.5 | 67 passing | Fixed route shadowing + NameError; 2 regression tests added |

## Open items requiring a human decision

- **Git history rewrite** to purge the tracked `backend/.env` — the agent is forbidden from touching history (R9). Decide before the repo is shared publicly or handed to a customer.
- **Push / PR / merge authority** — blocked by R9 until you grant it per session.
- **D1-D13 overrides** — pre-ruled in MASTER-PROMPT.md section 2. Edit there, not in a chat message, so the ruling survives into the next session.
- **Wiki §21/§23 sensitivity** — if the "✅ production-ready" list and the resume line have already been shown to stakeholders, S0.1 is a conversation before it is an edit.
