# FinShield AI — Evolution Summary

**Produced by:** `architecture-visualization:evolution-planner` (+ `c4model`, `graphviz`) with `design-review` lenses for the frontend track. **Date:** 2026-10-23.
**Artifacts:** [current-vs-target.dsl](./current-vs-target.dsl) · [gap-map.dot](./gap-map.dot) · [architecture-evolution.dot](./architecture-evolution.dot) · [migration-roadmap.md](./migration-roadmap.md) · [decision-map.md](./decision-map.md) · [evidence.md](./evidence.md) · [llm-implementation-briefs.md](./llm-implementation-briefs.md)

---

## 1. Why change is needed

FinShield AI is a **working prototype wrapped in production documentation**. That single sentence is the whole problem, and it is a better problem to have than the reverse.

What is genuinely there: 68 API routes with real persistence, bcrypt + JWT + hashed API-key auth applied to 64 of them, per-user row scoping, a case lifecycle with comments/notes/aggregation, SAR/STR filing with 30-day FinCEN deadline math and auto-populated structured data, a per-user rule-override layer that runs end-to-end from the admin UI into the screening engine, 65 passing tests, and — the best-designed piece in the repo — a rule-action precedence gate that makes a triggered rule's declared action authoritative over the numeric score (`compliance_engine.py:339-361`). Eight of eleven frontend routes are wired to real CRUD through a fully typed API client with no `any`. This is not a mockup.

What is not there: **the detection intelligence the product is named for.** `_ml_classify` returns `random.uniform` under a docstring that says "Simulate ML classification via RAG + LoRA" (`compliance_engine.py:297-304`). The behavioral stage adds `random.uniform(0, 0.15)` with the comment "Add some randomness to simulate ML inference" (`:292-293`). Sanctions screening is exact-match against a three-name Python set: `{"globalremit","darkfund","terrorfin"}` (`:22`). Two identical transactions can receive different compliance decisions. For an AML product, non-reproducibility is not a quality gap — it is the thing that makes it unsellable, because the first question an examiner asks is "why was this flagged, and would the same transaction be flagged tomorrow?"

The cruel detail is that **the real behavioral monitor already exists and is orphaned.** A genuine z-score anomaly detector with cold-start thresholds (`main.py:2196-2220`), backed by an `account_baselines` table and a real recomputation routine (`:2267-2310`), is reachable only through a standalone endpoint. `screen()` never calls it. The same pattern repeats for RAG: the pgvector cosine-distance SQL is real (`rag_service.py:276-345`), but embeddings are MD5 feature-hashing (`:52-73`), the real `sentence-transformers` path is gated behind a flag defaulting to false *and the dependency is not in `requirements.txt`*, and the whole service is constructed only when `RAG_DATABASE_URL` is set — which compose does and local `.env` does not, so in development all four RAG routes silently return 503.

So the change needed is not "build more". It is: **connect what exists, replace what is random, version what is asserted, and stop documenting what is not true.**

## 2. What changes first, and why that order

Phase 0 is deliberately feature-free, because four findings make every later slice more expensive if left alone:

1. **`backend/.env` is tracked in git** and has been since the first commit, despite `.gitignore:26` listing it — it was never `git rm --cached`. Its `JWT_SECRET_KEY` is a readable placeholder that is nonetheless a live signing key.
2. **CI cannot have been passing.** `.github/workflows/ci.yml:81,84` runs `docker build ./backend`, but `backend/Dockerfile:12` does `COPY backend/requirements.txt .` — root-relative from a subdirectory context. The job only runs on push to `main`, so it was never a PR gate. Meanwhile the `safety` scan has `continue-on-error: true` (`:112`), making the only security check advisory.
3. **There is no schema versioning.** `Base.metadata.create_all` (`database.py:36-38`) cannot alter an existing table, so any column addition silently no-ops on a live database, and `alembic` is not installed — while `README.md:150` tells users to run `alembic upgrade head` against a `docker/docker-compose.yml` path that does not exist.
4. **The health endpoint is fiction.** `main.py:2830-2845` returns `"database": "healthy"`, `"rag_classifier": "healthy"` and so on without probing anything, and `DEPLOYMENT.md:386` points an uptime monitor at it. Monitoring will report green through a total outage.

Then Phase 1, because Postgres-primary plus Alembic is a **prerequisite, not a preference**: `model_versions` (D1), sanctions tables (S2.3), `tenant_id` (D3), audit constraints (S3.2) and dropping the plaintext card columns (D8) are all schema changes, and `docker-compose.yml:32` currently makes SQLite the primary store while pgvector Postgres sits beside it serving only RAG.

Phase 2 is the product core: wire the orphaned monitor into `screen()`, delete the randomness, put real sanctions data behind a versioned list provider, turn RAG on with real embeddings, and put a versioned model behind a `RiskModel` protocol with shadow mode. Only then does Phase 3 (RBAC, immutable audit, DSAR, tenancy) have something worth governing — note that today **every authenticated user can hit the circuit-breaker, DSAR and webhook-admin endpoints**, because there is no `role` column at all.

Two latent bugs should be fixed inside Phase 0 rather than discovered later: `/api/v1/transactions/export` is registered after `/{tx_id}` and is therefore unreachable — while `transactions/page.tsx:98` calls it; and `POST /api/v1/behavioral/update-baseline` raises `NameError` for any account with more than one transaction, because `import math` is function-local at `main.py:2177` while `math.sqrt` is called at `main.py:2274`. Neither is caught by tests, because no test touches either path.

## 3. The frontend track runs in parallel

The design review found a real token foundation and no system on top of it. `tailwind.config.js:10-32` defines a genuinely semantic palette (`bg/surface/border/ink/accent` plus `success/warning/danger/info` and shadow tokens) — better than most prototypes. But there is no `DESIGN.md`, no primitives directory, and **zero** Button/Input/Card/Badge/Modal/Table components, so status badges, modal shells and table markup are re-implemented per page. Debt counts: 67 arbitrary Tailwind values, 16 hardcoded hex colours, 8 inline `style={{}}`, 79 raw px values, plus semantic-token leakage where pages reach for `bg-emerald-500` and `text-red-600` directly.

Accessibility is below baseline for a compliance tool: 12 `aria-*` attributes in the entire app, all of them `aria-required`; zero `role=`, zero `aria-label`, zero `sr-only`, zero table `<caption>`; no `<th scope>`; roughly 12 of 42 form controls without a label; **two** `focus:` styles in all of `src/`; risk bars and the dashboard donut encoding meaning by colour alone; and modals with no focus trap or Escape handling.

Authorization in the browser is cosmetic: there is **no `middleware.ts`**, and `isAuthenticated` is consulted only by the root redirect (`page.tsx:12`). `/cases`, `/filings`, `/settings` and `/api-keys` all render for a logged-out visitor and fail at the API layer with unhandled 401s, because the client has no 401 interceptor. The JWT sits in `localStorage` (`api.ts:358-370`) — XSS-readable bearer token for SAR data.

Two cheap wins here: delete `website/platform/*.html` (863 lines of static mockups with zero `fetch` calls, unreferenced and not in compose), and replace the in-app `docs` page's hardcoded `ENDPOINTS` array (`docs/page.tsx:6-40`) — which has already drifted, omitting filings, notifications, search and rules-simulate — with something generated from the backend's OpenAPI schema. Conversely, **eight working backend capabilities have no UI at all**: the rule simulator, rule stats, case notes, `check-sla`, case aggregation, all three behavioral endpoints, the circuit-breaker health routes and webhook dispatch. The Risk Officer and Admin user stories in the Wiki currently have no screens.

## 4. Risks and what remains unresolved

**Documentation is the largest single risk.** `FinShield-AI-Wiki.md:1129-1140` marks behavioral monitoring, circuit breakers, webhook DLQ, GDPR/DSAR and immutable audit as "✅ fully implemented, tested, and production-ready"; `:1181` states "Production Readiness Score: 8.5/10"; `:1187` is a resume line naming Celery, LangChain, LoRA/PEFT, DSPy, vLLM and Kubernetes. Every one of those is contradicted by the code. The Wiki is the best specification in the repository — the problem is tense, not content — so the fix is a status label per capability, not deletion. Until that happens, any evaluator, investor, auditor or hiring manager reading it is being misled, and that risk is reputational rather than technical.

**Twelve decisions are open** (see [decision-map.md](./decision-map.md)), and five of them gate real work: D1 (classifier technology — the recommendation is a deterministic classical model behind a `RiskModel` protocol, with the LoRA path deferred to the same interface, because explainability and CPU-only operation beat the marketing story), D2 (worker — Celery + Redis, with a hard rule that no decision logic moves into the worker), D3 (tenancy — shared schema + `tenant_id` + RLS, which **contradicts the Wiki's schema-per-tenant design** and is the hardest choice here to reverse), D4 (embeddings), and D9 (deploy target and secrets — the recommendation is a managed PaaS plus its secret store, *not* Vault, which nobody currently owns).

**Three assumptions could invalidate the sequencing**, and they are worth checking before Phase 1 starts: that no production customer data exists yet (if it does, S1.2 becomes a data-migration project and S3.4 must be deferred); that no labelled transaction dataset exists (if one does, D1's LLM path becomes viable sooner); and that the target buyer is a fintech compliance team rather than a tier-1 bank (if tier-1, D3 = schema-per-tenant, D9 = self-hosted Kubernetes and S6.7 stop being conditional and move up).

**Two contradictions to resolve explicitly rather than quietly:** the local-first promise (`README.md:20,319` — "no transaction data leaves your boundary") rules out hosted LLM and hosted embedding APIs, which constrains D1 and D4; and the Wiki's per-tenant-schema design conflicts with the recommended RLS approach, so one of the two documents has to change.

## 5. Next actions

1. **Rule on D6 and D3 first** — they are cheap today and expensive after customer data exists.
2. **Land Phase 0** (S0.1-S0.5): ~1 week, unblocks everything, and immediately removes four ship-blockers. Use the ready-to-paste briefs in [llm-implementation-briefs.md](./llm-implementation-briefs.md).
3. **Fix the Wiki's tense** in the same PR as S0.1, so no slice lands while the docs still overclaim.
4. **Re-run this analysis after Phase 1** — `architecture-health` will diff the gap map against the code and tell you whether the drift stopped.
5. **Regenerate the Repo Wiki** once Phase 0 lands, so the generated knowledge base reflects reality rather than the current overclaim. (`.qoder/repowiki/wiki_plan.yaml` is already configured to pin the aspirational-vs-real distinction.)
