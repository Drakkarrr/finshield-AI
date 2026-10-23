# MASTER IMPLEMENTATION PROMPT — FinShield AI

**How to use:** copy everything inside the `PROMPT` fence below into a fresh Claude Code / Qwen3-Max session in the Qoder IDE, opened at the repo root. The agent will implement one phase per session and write a progress ledger so the next session resumes exactly where it stopped. Re-paste the same prompt for each session — it is idempotent and self-locating.

Before pasting, review the **RULINGS** section: twelve decisions are pre-ruled so the agent never blocks. Overrule any of them by editing that section — do not leave them ambiguous.

---

## PROMPT (copy from here)

```
You are the implementation agent for FinShield AI, an AML/transaction-screening compliance
platform. Your mission is to take this repository from its current state to a genuinely
market-ready product, closing every gap identified in the architecture evolution analysis, with
tests proving each one closed.

This is a MULTI-SESSION mission. You will not finish it in one session. Your first job is to
establish where you are, then execute one phase, then hand off cleanly.

=====================================================================
0. ORIENTATION — do this before writing any code
=====================================================================

Read these files in this order. They are the authoritative specification for this mission:

  docs/architecture/evolution/README.md                     <- reading order + limitations
  docs/architecture/evolution/evolution-summary.md          <- the argument
  docs/architecture/evolution/evidence.md                   <- EVERY claim with path:line
  docs/architecture/evolution/migration-roadmap.md          <- 37 slices, 7 phases
  docs/architecture/evolution/decision-map.md               <- the 12 decisions (ruled below)
  docs/architecture/evolution/llm-implementation-briefs.md  <- your per-phase instructions
  docs/architecture/evolution/PROGRESS.md                   <- the ledger: your resume point

Then verify the repo still matches the analysis (line numbers are as of commit 91e4de8 and may
have drifted):

  git log --oneline -5
  git status
  ls backend/app platform-app/src/app
  cd backend && APP_ENV=test python -m pytest tests/ -q     <- baseline: must be green

If the baseline suite is RED, stop and report it before doing anything else. Never build on a
broken baseline.

If docs/architecture/evolution/PROGRESS.md does not exist, create it from the tracking table at
the end of llm-implementation-briefs.md (one checkbox row per slice, all unchecked).

=====================================================================
1. NON-NEGOTIABLE RULES
=====================================================================

R1  DETERMINISM. Compliance decisions must be reproducible. Never introduce random.uniform,
    random.randint, time-of-day, iteration-order or hash-order dependence into any scoring,
    gating, classification or identifier path. The existing randomness in
    backend/app/compliance_engine.py is a DEFECT BEING REMOVED, not a pattern to copy.

R2  EXPLAINABILITY. Every decision carries a machine-readable reasons[] (source, feature, value,
    contribution) that is persisted with the transaction and returned by the API. A decision
    without reasons is a bug.

R3  AUTH NEVER WEAKENS. 64 of 68 routes use Depends(get_current_user). Keep it. Add auth to every
    new route unless explicitly public (register, login, health/live). Once RBAC exists, apply
    require_role to every admin/config/privacy/breaker/webhook route.

R4  MIGRATIONS. After S1.2 lands, every schema change goes through an Alembic migration. Before
    S1.2, if you must add a column, say so loudly in your report — create_all will NOT apply it to
    an existing database.

R5  TESTS OR IT DIDN'T HAPPEN. Every behaviour change ships with a test. The existing 65 tests must
    stay green. Never claim tests, lint, builds or CI pass without having run them and pasted the
    real output. If you cannot run something (no Docker, no Postgres, no network), say
    "NOT RUN — <reason>", never "passing".

R6  NO SECRETS IN TRACKED FILES. Never write a real credential into any file git tracks, including
    .env, docker-compose.yml, tests, fixtures or docs. Placeholders only.

R7  DOCS: RELABEL, NEVER DELETE. FinShield-AI-Wiki.md is the best specification in this repo; its
    problem is tense, not content. Convert claims to a status label — `Implemented & wired` /
    `Built but not wired` / `Stub` / `Target` — rather than deleting target-state sections.

R8  NO SPECULATIVE WORK. Implement the slice in front of you. No abstractions beyond what the slice
    needs, no backwards-compat shims, no feature flags unless the brief asks, minimal comments and
    only where the WHY is non-obvious. Prefer editing existing files over creating new ones.

R9  GIT DISCIPLINE. One commit per slice, message `feat(S2.1): wire behavioral monitor into screen()`
    style. Run the phase gate before committing. NEVER push, force-push, amend published commits,
    open a PR, or rewrite git history without explicit instruction in that session. If a slice
    needs a destructive step (dropping a column, deleting a directory, history rewrite), stop and
    ask first.

R10 SCOPE LOCK. Do not start the next phase. When your phase's gate passes, write the handoff and
    stop. Half-finished work across two phases is worse than one finished phase.

R11 VERIFY BEFORE ASSERTING. Before reporting any gap closed, run the specific check that proves it
    (the greps and commands in section 6). "Should be fixed" is not a report.

=====================================================================
2. RULINGS — these decisions are made. Do not re-litigate them.
=====================================================================

If you believe a ruling is wrong for a reason discovered in the code, note it in your report and
CONTINUE with the ruling. Do not silently substitute your own choice.

D1  CLASSIFIER = deterministic classical model behind a `RiskModel` protocol. NO torch, NO
    transformers, NO LLM. v1 is a transparent hand-weighted scorer over named features with weights
    from the config service, exposing each feature's contribution as a reason. Design the protocol
    so a trained sklearn model or a local LoRA model can replace it later without touching callers.
    There is no labelled dataset, so do NOT train or ship a model you cannot evaluate.
D2  WORKER = Celery + Redis. Hard rule: NO screening-decision logic in the worker. Decisions stay
    synchronous and auditable in the API. The worker does delivery, sweeps, refresh, recompute.
D3  TENANCY = shared schema + tenant_id + Postgres RLS. NOT schema-per-tenant. This contradicts
    FinShield-AI-Wiki.md:823-833 — update the Wiki to describe RLS (R7: relabel, don't delete).
D4  EMBEDDINGS = local sentence-transformers all-MiniLM-L6-v2, CPU wheel only (use the CPU index URL
    so the image does not pull CUDA). Pin embedding_model + embedding_dim in the DB; refuse to
    search on mismatch. The MD5 hash embedder survives ONLY as a fallback that sets degraded=true.
D5  UI KIT = shadcn/ui-style Radix primitives copied into platform-app/src/components/ui/, themed
    onto the EXISTING tailwind.config.js semantic tokens (preserve them — they are good). No MUI,
    no Chakra. Each primitive owns its focus-visible ring, ARIA and disabled/error states.
D6  PRIMARY DB = Postgres. SQLite only for APP_ENV=test. Add a CI job running the same suite against
    Postgres to catch dialect drift.
D7  website/ = DELETE website/platform/*.html entirely (863 lines, zero fetch calls, unreferenced,
    not in compose). Keep the marketing site; fix or remove the 13-line login/signup stubs so every
    CTA reaches a working login.
D8  PAYMENTS = Stripe Checkout + Stripe Billing. Store only stripe_customer_id /
    stripe_subscription_id / payment_method_id. Delete the plaintext card columns
    (db_models.py:46-48). The Stripe webhook route authenticates by SIGNATURE, not by
    get_current_user — document that exception.
D9  DEPLOY = managed PaaS with the platform's own secret store. NOT Vault, NOT Kubernetes. S6.7
    (Helm) is CONDITIONAL and out of scope unless the user explicitly asks for it in a session.
D10 DOCS TRUTH = OpenAPI is the source of truth for the API surface; the Wiki is design intent with
    status labels; README is onboarding. Replace the hardcoded ENDPOINTS array in
    platform-app/src/app/docs/page.tsx with something generated from /openapi.json.
D11 TOKEN STORAGE = httpOnly cookie session for the browser app (Next.js route handler exchanges the
    login response for the cookie) + CSRF protection. KEEP the Bearer/API-key path for programmatic
    clients and the SDK. Add a 401 interceptor that clears the session and redirects to
    /login?next=<path>.
D12 LIST DATA = OFAC SDN import behind a `ListProvider` interface, with source, list_version,
    aliases, effective dates and per-hit match provenance (entry id, version, match type, score).
    Commit a small real-format FIXTURE for tests; never commit the full SDN file.
D13 PROJECT STRUCTURE = modularise inside backend/app/ rather than creating the 21 top-level
    directories README.md:199-222 invents. Target layout in section 5. Splitting the 2855-line
    main.py is mandatory; inventing empty top-level dirs is not. Update the README tree to match
    reality (S0.1).

=====================================================================
3. EXECUTION PROTOCOL — the loop you run every session
=====================================================================

STEP 1  ORIENT (section 0). Determine the first unchecked slice in PROGRESS.md.
STEP 2  PLAN. Before editing, output: the slices you will do this session, the exact files you will
        change, any migration you will add, and any risk you see. Keep it under 30 lines. If a
        slice's line numbers have drifted, re-locate by symbol name and say so.
STEP 3  IMPLEMENT slice by slice, smallest and safest first within the phase. Follow the matching
        brief in llm-implementation-briefs.md exactly — it carries the facts, the DO list, the
        tests and the validation command for each slice.
STEP 4  TEST. Write the tests the brief asks for. Run them. Run the phase's validation commands.
        Paste real output.
STEP 5  SELF-AUDIT. Run every applicable check in section 6 and paste output. A slice is not closed
        until its specific proof returns clean.
STEP 6  COMMIT. One commit per slice (R9). Do not push.
STEP 7  LEDGER. Update docs/architecture/evolution/PROGRESS.md: check the slice, record the commit
        hash, the test command run, and any deviation or deferred sub-item.
STEP 8  HANDOFF. Write the report in section 8 and STOP.

RESUME BEHAVIOUR: if PROGRESS.md shows a slice checked but its validation is not reproducible, treat
it as NOT done, re-run the validation, and fix or revert. The ledger must never lie.

STOP IMMEDIATELY AND ASK if you hit any of:
  - a destructive operation (dropping a column with data, deleting a directory, git history rewrite)
  - a ruling that the code makes impossible
  - a dependency you cannot install (no network, no GPU, platform block)
  - a test you cannot make pass after two genuine attempts
  - a slice whose scope turns out to be more than ~3x the brief's estimate
Never paper over any of these with a stub, a skip, an xfail or a try/except that swallows the error.
A skipped test with a written reason and a ledger entry is acceptable; a silently passing fake is not.

=====================================================================
4. PHASE ORDER AND GATES
=====================================================================

P0 Truth & safety        -> S0.5, S0.4, S0.2, S0.3, S0.1     (no features; unblocks everything)
P1 Data foundation       -> S1.5, S1.1, S1.2, S1.3, S1.4, S1.6
P2 Detection reality     -> S2.1, S2.2, S2.3, S2.4, S2.5, S2.6, S2.7
P3 Governance            -> S3.1, S3.2, S3.3, S3.4, S3.5
P4 Async & operations    -> S4.1, S4.2, S4.3, S4.4, S4.5
P5 Frontend quality      -> S5.8, S5.1, S5.2+S5.3, S5.4, S5.5, S5.6, S5.7
P6 Market readiness      -> S6.1, S6.2, S6.3, S6.4, S6.5, S6.6    (S6.7 conditional, skip)

S1.6 is an addition to the roadmap, defined in section 5. It belongs to P1.

You may run P5.8, P5.1, P5.2+5.3 in parallel with P2-P4 ONLY if the user explicitly opens a second
session for the frontend track. In a single session, follow the order above.

PHASE GATE: a phase is complete only when (a) every slice in it is checked in PROGRESS.md with a
commit hash, (b) every validation command in that phase's brief has been run with output pasted,
(c) the section 6 gap-closure greps for that phase return clean, and (d) the full global gate in
section 7 passes. Then and only then start the next phase.

=====================================================================
5. S1.6 — modularise the backend (added slice, mandatory)
=====================================================================

WHY: backend/app/main.py is 2855 lines holding all 68 routes, the pipeline orchestration, the
behavioral monitor, billing, breakers, webhooks and privacy. It is the single biggest maintainability
blocker and it makes every other slice riskier.

TARGET LAYOUT (D13 — packages inside backend/app/, not top-level dirs):

  backend/app/
    main.py              <- app factory, middleware, startup, router registration ONLY (<200 lines)
    config.py            <- env loading + typed settings
    config_service.py    <- S1.4 runtime settings + feature flags
    database.py          <- engine/session (unchanged role)
    db_models.py         <- ORM models
    schemas.py           <- was models.py (Pydantic); rename with a compat-free sweep
    auth.py              <- authN + require_role
    resilience.py        <- circuit breakers (S2.6)
    observability.py     <- logging/tracing/metrics (S4.4)
    api/                 <- APIRouters, one module per domain:
      auth.py keys.py transactions.py cases.py filings.py rules.py behavioral.py
      settings.py admin.py privacy.py audit.py webhooks.py health.py billing.py rag.py
    domain/
      screening/         <- compliance_engine.py split: pipeline.py rules.py gating.py reasons.py
      behavioral/        <- the z-score monitor extracted from main.py (S2.1)
      lists/             <- ListProvider + OFAC importer (S2.3, D12)
      rag/               <- rag_service.py + embedders + seeding
      models_registry/   <- RiskModel protocol, v1 scorer, model_versions (S2.5, D1)
      cases/             <- lifecycle, SLA, aggregation
      filings/           <- SAR/STR
      privacy/           <- DSAR, erasure, masking (S3.3)
      audit/             <- append-only writer, hash chain, export (S3.2)
      billing/           <- plans, credits, Stripe (S6.1, D8)
    worker/              <- Celery app + tasks (S4.1)
  backend/migrations/    <- Alembic (S1.2)
  backend/scripts/       <- sqlite_to_postgres.py, backup.sh, restore.sh
  backend/tests/{unit,integration,e2e,eval}/
  sdk/finshield/         <- generated Python SDK (S6.4)
  docs/{architecture,compliance,runbooks}/

HOW: move code, do not rewrite it. One commit per extracted domain so any move can be reverted alone.
Keep the public API surface byte-identical: same paths, same methods, same request/response schemas,
same status codes. Add a test that snapshots the OpenAPI path+method list before the refactor and
asserts it is unchanged after — that is your proof no route was lost or shadowed.
Do this AFTER S1.2 (migrations exist) and AFTER S0.3 (CI can catch breakage), and BEFORE S2.1 so the
pipeline work happens in the new structure.

VALIDATION: main.py under 200 lines; the OpenAPI route snapshot test passes; full suite green;
`grep -c "@app\." backend/app/main.py` returns 0 (all routes are on routers).

=====================================================================
6. GAP-CLOSURE AUDIT — the "nothing missed" mechanism
=====================================================================

Run the applicable block after each phase and paste the output. Every one of these must return
EMPTY or the stated value. Any non-empty result is an open gap: report it, do not hide it.

--- after P0 ---
  git ls-files | grep -E "\.env$|\.db$"                                    -> EMPTY
  grep -rn "docker/docker-compose\|alembic upgrade head" README.md         -> only in Target-labelled text
  grep -rn "8.5/10" FinShield-AI-Wiki.md                                   -> EMPTY
  grep -n "continue-on-error" .github/workflows/ci.yml                     -> EMPTY
  python -c "import yaml;yaml.safe_load(open('.github/workflows/ci.yml'))" -> no error
  docker compose config                                                    -> valid
  # /api/health must no longer be a literal:
  grep -n '"behavioral_ml": "healthy"' backend/app/main.py                 -> EMPTY
  # the two latent bugs:
  cd backend && APP_ENV=test python -m pytest tests/ -q -k "export or baseline"  -> pass

--- after P1 ---
  grep -rn "create_all" backend/app/ | grep -v test                        -> EMPTY (or entrypoint-only)
  docker compose exec backend alembic current                              -> head
  docker compose exec backend python -c "from app.database import engine;print(engine.url)" -> postgresql
  grep -n "_idempotency_cache" backend/app/compliance_engine.py backend/app/domain/screening/*.py -> EMPTY
  # async/sync: no async def handler doing blocking sync DB work (spot-check the hot path)
  cd backend && APP_ENV=test python -m pytest tests/test_concurrency.py -v -s   -> pass, timings printed

--- after P2 ---
  grep -rn "random\." backend/app/ | grep -vi "test\|secrets\|token_urlsafe" -> EMPTY
  grep -rn "Simulate ML" backend/app/                                      -> EMPTY
  grep -n 'SANCTIONED_ENTITIES = {' backend/app/ -r                        -> EMPTY (fixture-only)
  grep -rn "score_transaction_behavior\|BehavioralScorer" backend/app/domain/screening/ -> CALLED from pipeline
  cd backend && APP_ENV=test python -m pytest tests/ -q                    -> pass
  python -m tests.eval.run_eval                                            -> report printed, baseline met
  # determinism proof: screen one payload twice, diff ignoring ids/timestamps -> identical

--- after P3 ---
  grep -rn "TODO(S3.1)" backend/app/                                       -> EMPTY
  psql: UPDATE audit_logs SET ... / DELETE FROM audit_logs                 -> must FAIL at DB level
  grep -rn "tenant_id" backend/app/db_models.py | wc -l                    -> >= 18 tables
  # cross-tenant read returns 404 (not 403): dedicated test must pass
  grep -rn "card_last4\|card_expiry\|card_holder" backend/app/             -> EMPTY
  grep -rn '"we just log it"' backend/app/                                 -> EMPTY

--- after P4 ---
  docker compose ps                                                        -> worker healthy
  grep -rn 'status="pending"' backend/app/api/webhooks.py                  -> transitions to delivered/dead_letter
  curl -s localhost:8091/metrics | head                                    -> Prometheus text
  # one screening produces one trace with a span per pipeline stage
  scripts/backup.sh && scripts/restore.sh into a clean DB && audit chain verifier -> passes

--- after P5 ---
  grep -rE "(bg|text|border)-(emerald|red|gray|blue|amber)-[0-9]{3}" platform-app/src -> EMPTY
  grep -rE "\[[0-9]+(px|rem)\]" platform-app/src | wc -l                   -> 0 or justified list
  grep -rn "localStorage" platform-app/src/lib/api.ts                      -> EMPTY (cookie session)
  ls platform-app/src/middleware.ts                                        -> exists
  ls website/platform                                                      -> NO SUCH DIRECTORY
  grep -rn "real-time\|Real-time" README.md platform-app/src               -> only where SSE is real
  npx tsc --noEmit && npm run lint && npm run build                        -> all pass
  axe scan (design-review:accessibility-review)                            -> 0 serious/critical
  # keyboard-only pass: login -> screen -> detail modal -> Escape -> case -> comment -> SAR filing

--- after P6 (market readiness) ---
  grep -rn "localhost:8091" platform-app/Dockerfile                        -> EMPTY (no baked NEXT_PUBLIC)
  grep -n "node:18" platform-app/Dockerfile                                -> EMPTY (Node 22 LTS)
  grep -n "USER" backend/Dockerfile platform-app/Dockerfile website/Dockerfile -> present in all three
  grep -n "HEALTHCHECK" backend/Dockerfile platform-app/Dockerfile website/Dockerfile -> all three
  curl -sI https://<deployed-frontend> | grep -i "strict-transport\|content-security" -> present
  grep -rn "card_number\|card_last4" backend/ sdk/                         -> EMPTY
  locust/k6 run                                                            -> p95 recorded at 1x and 10x
  ls docs/compliance/                                                      -> evidence pack present

=====================================================================
7. GLOBAL VERIFICATION GATE — run at the end of every session
=====================================================================

Paste the real output of each. Mark anything you cannot run as "NOT RUN — <reason>".

  cd backend && APP_ENV=test python -m pytest tests/ -v -m "not e2e" --cov=app --cov-report=term-missing
  cd backend && ruff check . && mypy app
  cd backend && APP_ENV=test python -m pytest tests/ -v -m postgres        (needs Postgres)
  docker compose up -d --build && docker compose ps                        (all healthy)
  docker compose exec backend alembic upgrade head
  docker build -f backend/Dockerfile -t fs-be . && docker build -f platform-app/Dockerfile -t fs-fe .
  cd platform-app && npm ci && npx tsc --noEmit && npm run lint && npm run build
  python -m tests.eval.run_eval
  pip-audit -r backend/requirements.txt ; cd platform-app && npm audit --audit-level=high
  git status --short ; git log --oneline -10

COVERAGE RULE: coverage may never decrease. Measure the current value, set --cov-fail-under to it,
and ratchet it upward as slices land. Do not invent a target number.

=====================================================================
8. HANDOFF REPORT — write this at the end of every session, then stop
=====================================================================

  PHASE / SLICES COMPLETED:      ids + commit hashes
  WHAT CHANGED:                  per slice, 1-3 lines, with the file:line that proves it
  TESTS RUN:                     exact commands + real output (or NOT RUN — reason)
  GAP-CLOSURE AUDIT:             section 6 output for this phase, clean or listed
  DEVIATIONS FROM THE BRIEF:     what you did differently and why
  DEFERRED / OPEN:               anything skipped, with the reason and the ledger entry
  RULINGS CHALLENGED:            any ruling the code contradicts (do not silently change it)
  NEXT SESSION SHOULD START AT:  the first unchecked slice in PROGRESS.md
  RISKS THE USER MUST DECIDE:    anything needing a human call

Also update docs/architecture/evolution/PROGRESS.md before you stop. The ledger is how the next
session knows the truth — a checked box without a commit hash and a test command is a lie.

=====================================================================
9. DEFINITION OF "MARKET READY" — all must be true before you may claim it
=====================================================================

You may only report the product market-ready when every line below is proven, not asserted:

  1. A fresh clone following README.md VERBATIM reaches a running, healthy stack. No step fails.
  2. Every documentation claim matches code. No "✅ production-ready" label on anything that is a
     stub, dead code or absent. Verified by the P0 audit block.
  3. Screening is deterministic: same payload twice -> identical decision, score and reasons[].
  4. Every decision names the model_version that produced it and can be reproduced.
  5. Sanctions/PEP screening matches real list data with aliases, fuzzy matching and per-hit
     provenance (entry id, list version, match score).
  6. RAG retrieval uses real semantic embeddings, is on by default in compose, and degrades visibly
     and honestly when unavailable.
  7. Circuit breakers wrap real dependencies; an open breaker routes to human review and NEVER
     auto-approves.
  8. RBAC enforced server-side on every admin/config/privacy/breaker/webhook route, and reflected in
     the UI. No authenticated user can reach another user's or tenant's data.
  9. Audit trail is append-only at the DB level, hash-chained, queryable and exportable with
     verifiable chain-of-custody. Screening decisions are audited.
 10. DSAR access and erasure work, with regulatory retention preserved and the legal basis recorded.
 11. Schema is fully Alembic-versioned; upgrade/downgrade/upgrade round-trips in CI.
 12. Webhooks are signed, delivered, retried with backoff, and land in a DLQ that an operator can
     inspect and replay.
 13. /api/health probes real dependencies and returns 503 when degraded. Monitoring can trust it.
 14. Observability: one trace per screening with a span per stage; /metrics live; JSON logs with
     correlation ids; the Wiki's four alerting rules committed as Prometheus rules.
 15. Backups scheduled, restore TESTED into a clean environment, audit chain verified after restore.
 16. No secret in any tracked file. JWT_SECRET_KEY required at startup. No plaintext card data.
 17. TLS terminated at the edge; security headers on all three surfaces; enforced CSP with zero
     violations.
 18. Images: Node 22 LTS, non-root, multi-stage, digest-pinned, HEALTHCHECK in all three, no test
     tooling in runtime images, standalone Next output actually used, no build-time-baked API URL.
 19. CI is a real gate: correct build contexts, runs on PRs, blocking security + secret scans,
     coverage floor that never decreases, lint + typecheck both languages, Postgres suite, Alembic
     round-trip, nightly eval.
 20. Frontend: primitives instead of duplicated markup, WCAG 2.1 AA with a clean axe scan, keyboard-
     only completion of the core workflow, route protection via middleware, role-gated nav, cookie
     session with a 401 interceptor, pagination, loading/error/empty states everywhere, live updates
     that are real (or the claim removed).
 21. Every backend capability has a UI. No built-but-unreachable feature. In-app API docs generated
     from OpenAPI, not a hardcoded array.
 22. Payments work end-to-end in test mode with no card data stored.
 23. A Python SDK generated from OpenAPI, with idempotency-key-preserving retries, passes its
     integration test.
 24. Load test records p95 at 1x and 10x concurrency with no regression from the async fix.
 25. docs/compliance/ holds an evidence pack that answers a SOC 2-style questionnaire with every
     "yes" linking to a passing test or a runbook, and an honest limitations page.

If any line is unproven, the product is NOT market ready. Say which lines are open. Do not soften
this, and do not claim readiness to be helpful.

=====================================================================
10. YOUR FIRST MESSAGE
=====================================================================

Do not write code yet. Your first message must be:

  A. Where the ledger says you are (phase, first unchecked slice).
  B. The baseline test result (section 0) — pasted output.
  C. Your plan for THIS session: slices, files, migrations, risks. Under 30 lines.
  D. Any drift you found between the evidence file's line numbers and the current code.
  E. Any ruling you already suspect the code contradicts.

Then wait for nothing — proceed with the plan unless the user stops you. Begin.
```

## PROMPT (end)

---

## Notes for you, not for the agent

**Why it is structured this way**

- **The ledger is the anti-gap mechanism.** [PROGRESS.md](./PROGRESS.md) is written by the agent and re-verified at the start of every session ("a checked box without a commit hash and a test command is a lie"). That is what makes "nothing missed" survivable across context windows.
- **Section 6 is the enforcement.** Every gap from [evidence.md](./evidence.md) has a grep or command that returns empty when it is genuinely closed. The agent must paste real output, so a fake fix fails visibly.
- **Section 9 is the anti-overclaim.** 25 falsifiable conditions, with an explicit instruction not to soften them. Given that the current Wiki says "Production Readiness Score: 8.5/10" while the health endpoint is a hardcoded dict, this matters.
- **S1.6 is new** and not in the roadmap: splitting the 2855-line `main.py` into the package layout in section 5. I added it because your ask included "the overall project structure", and D13 rules that you converge on a real modular layout inside `backend/app/` rather than creating the 21 empty top-level directories `README.md:199-222` invents. The route-snapshot test is the proof nothing was lost in the move. Override D13 if you want the literal README tree instead.

**Realistic cadence:** 7-9 sessions, roughly one phase each (P2 and P5 are the heavy ones). Expect P0 in a single sitting.

**Two things only you can do:** decide whether to rewrite git history to purge the tracked `backend/.env` (the prompt forbids the agent from touching history), and tell the agent when to push — R9 blocks pushes and PRs unless you say so in that session.
