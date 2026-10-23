# FinShield AI — Decision Map

Generated 2026-10-23 by `architecture-visualization:evolution-planner`.
Each decision is **OPEN** until you rule on it. Constraints are facts from the repo; options are the realistic choices; the recommendation is mine with its reasoning exposed so you can overrule it.

**Blocking map** — nothing in these slices should start before its decision is made:

| Decision | Blocks | Cost of deciding late |
|---|---|---|
| D1 classifier | S2.5, S2.7, S6.6 | Model cards, eval harness and the whole "ML" claim are written around the answer |
| D2 worker | S4.1, S4.2, S4.3, S5.7 | Webhooks, SLA sweeps and live UI all hang off the same choice |
| D3 tenancy | S3.4, S1.2 schema shape | `tenant_id` on 14 tables is far cheaper before data exists |
| D4 embeddings | S2.4, S2.7 | Re-embedding the corpus is a full rebuild |
| D5 UI kit | S5.2, S5.3, S5.6 | Every new screen is written twice if the primitive layer changes |
| D6 primary DB | S1.1, S1.2 | Migration baseline differs |
| D7 website/ | S5.8, S5.1 | Three design systems keep drifting |
| D8 payments | S6.1 | Card columns must be dropped in a migration |
| D9 deploy & secrets | S3.5, S6.2, S6.3, S6.7 | TLS, headers and image hardening depend on the target |
| D10 docs truth | S0.1, S5.6 | Drift continues in five places |
| D11 token storage | S5.4, S5.5 | Affects middleware design and CSP |
| D12 list data | S2.3 | Import format and matching thresholds follow the source |

---

## D1 — What actually performs risk classification?

**Constraints.** No `torch`, `transformers`, `peft`, `dspy`, `vllm` or any LLM client in `backend/requirements.txt` (15 pins total). `_ml_classify` returns `random.uniform` (`compliance_engine.py:297-304`) under a docstring reading "Simulate ML classification via RAG + LoRA". The product's stated differentiator is *local-first* — "no transaction data leaves your boundary" (`README.md:20,319`). AML decisions must be explainable to an examiner.

| Option | Pros | Cons |
|---|---|---|
| **A. Classical ML** (gradient boosting / logistic on transaction features, scikit-learn or LightGBM) | Runs on CPU, deterministic, feature importances = ready-made reasons, trivially versionable, cheap to eval, no GPU | Not the "LoRA-tuned Llama" story; needs a labelled dataset |
| **B. Local LLM + LoRA** (the documented design) | Matches README/Wiki/resume claims; handles free-text memo semantics | Needs ≥16GB VRAM per `README.md:133`, vLLM serving, DSPy pipeline, training data, model governance; 10-50× the effort; explanations are weaker, not stronger |
| **C. Hosted LLM API** | Fastest to a real signal on memo text | Directly contradicts the local-first claim; sends transaction data to a third party — a compliance disqualifier |
| **D. Honest heuristics** (drop the ML claim, keep rules + behavioral) | Zero new infra; fully explainable today | Loses the headline differentiator; no path to catching novel patterns |

**Recommendation: A now, behind an interface that B can satisfy later.** Define `RiskModel.score(features) -> (label, confidence, reasons)`; ship v1 as a classical model whose feature importances populate `reasons[]`. RAG (S2.4) already supplies the free-text/policy-context signal that would otherwise motivate an LLM, so B's marginal value is lower than the Wiki implies. Keep B as a second implementation of the same protocol, promoted through shadow mode (S2.5) once a labelled dataset exists.

**Consequences:** `model_versions` table + model cards become meaningful; the eval harness (S2.7) tests a deterministic artefact; README/Wiki must be reworded from "LoRA fine-tuned Llama" to "versioned, explainable risk model (LLM path designed, not shipped)".
**Reversibility: medium** — the protocol boundary makes swapping A→B a config change, but the training-data collection starts now either way.
**What would change my mind:** an existing labelled dataset plus GPU capacity, or a customer explicitly requiring LLM-based narrative generation.

---

## D2 — Async execution platform

**Constraints.** Zero `BackgroundTasks`/`asyncio` usage in `backend/app/`. `celery` appears once as a comment (`main.py:2606`); `redis` appears only as a string naming a dependency that does not exist (`main.py:2390,2555`, `db_models.py:280`). Compose has 3 services and no broker. Needed by: webhook delivery + DLQ (S4.2), SLA sweeps and baseline recompute (S4.3), live UI push (S5.7), sanctions list refresh (S2.3).

| Option | Pros | Cons |
|---|---|---|
| **A. Celery + Redis** | Already the documented design (`README.md:113`); mature, beat scheduler, retries, result backend, DLQ patterns | Two new services; Celery's config surface is large; heavier than the workload needs |
| **B. arq or RQ + Redis** | Small, async-native (fits FastAPI), simple | Fewer batteries; scheduler story weaker; less hiring familiarity |
| **C. FastAPI BackgroundTasks** | No infra at all | In-process: lost on restart, no retries, no DLQ, no scheduling — fails the webhook promise |
| **D. Postgres as queue** (`SELECT ... FOR UPDATE SKIP LOCKED`) | No new service; transactional with the data; survives restart | Must build retry/backoff/scheduling yourself; polling latency |

**Recommendation: A (Celery + Redis).** The Wiki already specifies it, the workload genuinely needs scheduled tasks *and* retried delivery *and* a DLQ, and hiring/docs familiarity matters for a product aimed at bank IT. Add Redis to compose with a healthcheck and `depends_on` conditions. Hard rule: **no screening-decision logic in the worker** — decisions stay synchronous and auditable in the API; the worker handles delivery, sweeps, refresh and recompute.
**Reversibility: medium** — task signatures are portable to B or D if ops complexity bites.

---

## D3 — Multi-tenancy isolation model

**Constraints.** Zero occurrences of "tenant" in the backend. Isolation today is per-*user* row filtering. `FinShield-AI-Wiki.md:823-833` specifies **per-tenant Postgres schemas** and `:981` mentions an unused `rls_policies.sql` placeholder. 14 tables would need a tenant dimension.

| Option | Pros | Cons |
|---|---|---|
| **A. Shared schema + `tenant_id` + Postgres RLS** | One migration path, one schema to version, cheap to add tenants, RLS enforced by the DB not by discipline | Weaker isolation story for the most paranoid buyers; every query must set the session variable correctly |
| **B. Schema-per-tenant** (the documented design) | Strongest isolation narrative; per-tenant backup/restore; matches Wiki | Alembic must run N times per migration; connection pooling and search get complicated; slow tenant onboarding |
| **C. Single-tenant deployment per customer** | Simplest code — no tenancy at all; strongest isolation | No SaaS economics; ops cost scales with customers |

**Recommendation: A for the SaaS product, with C as the enterprise deployment mode.** B is the most expensive option and its advantage over A+RLS is mostly narrative. Note that A contradicts the current Wiki text — that is a documentation change (S0.1), not a technical problem. Either way, add `tenant_id` in the S1.2 baseline migration while the tables are still empty of customer data.
**Reversibility: low** — this is the hardest decision in the set to undo. Decide before real customer data exists.

---

## D4 — Embedding strategy for RAG

**Constraints.** Retrieval SQL is real (`rag_service.py:276-278,305-307,343-345`). Embeddings are MD5 feature-hashing into 384 buckets (`:52-73`), which the docstring admits approximates "lexical overlap". The `SentenceTransformer("all-MiniLM-L6-v2")` path (`:36-38`) is behind `RAG_USE_SENTENCE_TRANSFORMERS` defaulting to `"false"` **and `sentence-transformers` is not in `requirements.txt`** — it cannot activate. Corpus today: 5 documents, 6 sanctions entries, 5 precedents (`seed_rag_data.py:27-178`).

| Option | Pros | Cons |
|---|---|---|
| **A. Local sentence-transformers (all-MiniLM-L6-v2)** | Real semantic retrieval; stays local-first; ~90MB model, CPU-viable | Adds `torch` (~800MB image growth); cold-start latency; needs a model download step in the image or a mounted volume |
| **B. Self-hosted embedding microservice** (TEI / Ollama) | Keeps the API image slim; GPU-optional; one embedder for all consumers | Another service to run and monitor |
| **C. Hosted embedding API** | Zero infra | Sends compliance text to a third party — conflicts with the local-first claim |
| **D. Keep hash embeddings** | No work | Retrieval is keyword overlap; the "agentic RAG" claim stays false |

**Recommendation: B if a separate service is acceptable, otherwise A.** A is the lowest-friction path to a true claim; B is the better long-term shape and keeps `torch` out of the API image. Either way: pin the embedding model *and dimension* in a `model_versions` row, and re-embed the whole corpus whenever either changes. Keep the hash path only as an explicitly-labelled degraded fallback that sets a `rag_degraded=true` reason on the decision.
**Reversibility: medium** — swapping models forces a full re-embed, which is cheap at 16 documents and expensive at 160 000.

---

## D5 — Frontend component strategy

**Constraints.** No component library (`package.json:11-15` = next, react, react-dom only). No primitives: zero Button/Input/Card/Badge/Modal/Table components; only `PlatformLayout`, `Sidebar`, `Topbar`. Markup is duplicated per page. `tailwind.config.js:10-32` already defines a real semantic token set. Accessibility is below baseline (S5.3 evidence). 67 arbitrary Tailwind values, 16 hex colours, 8 inline styles, 79 px magic numbers.

| Option | Pros | Cons |
|---|---|---|
| **A. shadcn/ui (Radix primitives, copied into repo)** | Correct focus management, ARIA, keyboard and focus traps *for free* — directly fixes the modal/menu/select a11y gaps; owns the source so tokens stay yours | Refactor cost; opinionated structure; must map Radix theming onto the existing tokens |
| **B. Hand-rolled primitives on existing tokens** | No new dependency; total control; smallest diff | You re-implement focus trapping, listbox semantics and typeahead yourself — that is where a11y bugs live |
| **C. Full library (MUI/Chakra/Ant)** | Fast, complete | Two design systems in one app; fights the existing Tailwind tokens; large bundle |

**Recommendation: A, mapped onto the existing token palette.** The binding requirement is WCAG 2.1 AA for a compliance tool used under audit pressure, and Radix is the cheapest credible route to correct modal/menu/select/table semantics. Keep the token layer from `tailwind.config.js` as the single source of colour and spacing truth (S5.1) and forbid raw palette classes.
**Reversibility: medium** — primitives are additive; migrating pages is incremental.

---

## D6 — Primary database

**Constraints.** `docker-compose.yml:32` sets `DATABASE_URL=sqlite:///./finshield.db` while `:5` runs `pgvector/pgvector:pg16` and `:33` points only the RAG store at Postgres. `psycopg2-binary` and `pgvector` are already pinned. Schema is `create_all` (`database.py:36-38`).

| Option | Pros | Cons |
|---|---|
| **A. Postgres primary, SQLite for tests only** | Unlocks RLS (D3), append-only triggers (S3.2), pgvector joins, concurrent workers, real backups | Requires S1.1 + S1.2 before anything else; local dev needs compose |
| **B. Keep SQLite primary** | Zero-friction local dev; single file | Blocks tenancy, immutability, concurrency and backup story — a hard ceiling for a regulated product |

**Recommendation: A.** This is not really a choice for a product whose pitch is regulator-defensible records. Keep `APP_ENV=test` on SQLite (`database.py:12-13`) so the existing 65 tests stay fast, and add a nightly Postgres run of the same suite to catch dialect drift.
**Reversibility: high now, low later** — do it before customer data exists.

---

## D7 — Fate of `website/`

**Constraints.** `website/platform/*.html` (863 lines across 4 files) contains **zero** `fetch`/`XMLHttpRequest`/`localStorage` calls — static mockups with hardcoded data (`dashboard.html:110,127`), unreferenced by any page and absent from compose. `website/css/` is a third design system (4937 lines of BEM). `website/pages/login.html` and `signup.html` are 13-line stubs. `tailwind.config.js:11,17` records that the app palette was copied from the website's.

| Option | Pros | Cons |
|---|---|---|
| **A. Delete `website/platform/*`, keep marketing site, link CTAs to platform-app** | Removes 863 lines of dead code and a broken entry point; one console | Loses the mockups as design reference (they are in git history) |
| **B. Keep as design reference in a `mockups/` folder** | Preserves intent | Still dead code; still a second design system |
| **C. Merge marketing into the Next.js app** | One deployable, shared tokens, one design system | Marketing and app have different performance/SEO needs; bigger refactor |

**Recommendation: A now, consider C later.** Fix or remove the login/signup stubs either way — a marketing site whose "Log in" goes nowhere is a credibility problem.
**Reversibility: high** (git history).

---

## D8 — Payments

**Constraints.** No provider integration exists. `PLANS` is a hardcoded list (`main.py:874`); subscribe/checkout/purchase endpoints (`:962,:1044,:1151`) adjust credits without charging. Card last4/expiry/holder are plaintext columns (`db_models.py:46-48`). `DEPLOYMENT.md:314-334` lists `PAYMONGO_SECRET_KEY` for code that does not exist. The frontend billing UI is fully wired (`settings/page.tsx:289-378`).

| Option | Pros | Cons |
|---|---|---|
| **A. Stripe Checkout / Payment Links** | Hosted fields keep you in PCI SAQ-A; subscriptions, invoicing, tax and dunning built in; enterprise buyers expect it | Stripe fees; less flexibility in checkout UX |
| **B. PayMongo** (as DEPLOYMENT.md hints) | Regional payment methods | Smaller surface for subscription/invoicing; less familiar to enterprise procurement |
| **C. Defer monetisation** | Focus on compliance features | Credits/billing UI stays decorative; pricing page is a lie |

**Recommendation: A, and delete the plaintext card columns in the same migration.** Never store card metadata you do not need — provider tokens replace all of it. If the target market is a specific region, revisit B.
**Reversibility: medium** — provider-specific customer ids persist, but the entitlement model is yours.

---

## D9 — Deployment target & secret management

**Constraints.** No Kubernetes manifests, Helm charts or Terraform exist despite `README.md:301-311`. `DEPLOYMENT.md:60-388` describes Railway/Vercel/Neon/Resend/Sentry/UptimeRobot — none present in-repo (no Procfile, no `sentry_sdk`, no `payment.py`). Compose hardcodes secrets (`:11,33,34`). No TLS anywhere; `next.config.js` has no `headers()`.

| Option | Pros | Cons |
|---|---|---|
| **A. Managed PaaS** (Railway/Fly/Render + managed Postgres) | TLS, secret store, backups, scaling handled; fastest to market; matches DEPLOYMENT.md's existing intent | Less control; per-tenant isolation is logical only; vendor dependency |
| **B. Self-hosted Kubernetes + Helm** | Full control; required by some bank procurement; strongest isolation story (per-customer namespace) | Highest ops burden; needs S6.7, S4.4, S4.5 all done first |
| **C. Customer-managed single-tenant deploy** (compose/Helm handed to the buyer) | Fits the local-first pitch; data never leaves their boundary | Support burden per install; version skew |

**Recommendation: A for your own SaaS, C as the enterprise offering, B only when a deal demands it.** For secrets: the platform's secret store plus `${VAR}` interpolation — **not** Vault. Vault is a real operational commitment and the Wiki's Vault claim (`README.md:123`) should be relabelled target-state until someone owns it.
**Reversibility: medium** — container images are portable; the secret-injection mechanism is not.

---

## D10 — Single source of truth for documentation

**Constraints.** Five doc surfaces overlap: `README.md` (347 lines), `FinShield-AI-Wiki.md` (1188 lines), `DEPLOYMENT.md` (488), `DOCKER.md` (173), and an in-app hardcoded `ENDPOINTS` array (`docs/page.tsx:6-40`) that has already drifted — it omits filings, notifications, search and rules-simulate. FastAPI already generates OpenAPI at `/docs`.

| Option | Pros | Cons |
|---|---|---|
| **A. OpenAPI is truth for the API; Wiki is design intent with status labels; README is onboarding** | Each surface has one job; API docs cannot drift | Requires discipline: every route needs a good docstring and tags |
| **B. Keep the Wiki as the single canonical document** | One place to read | It already contradicts the code in §21-§22; 1188 lines is unmaintainable as truth |
| **C. Generate the in-app docs route from the OpenAPI schema** | Kills the drifted array | Needs a build or runtime fetch step |

**Recommendation: A + C.** Generate the in-app reference from `/openapi.json` and delete the literal array. Add a status label convention (Implemented & wired / Built but not wired / Stub / Target) to every Wiki capability section — the Wiki is the best specification in the repo; its problem is tense, not content.
**Reversibility: high.**

---

## D11 — Frontend session and token storage

**Constraints.** JWT is stored in `localStorage` under `finshield_token` (`lib/api.ts:358-370`) and sent as a Bearer header (`:379-381`). There is no `middleware.ts`, so no route protection. No 401 interceptor — an expired token surfaces as a raw error string. `next.config.js:7-13` proxies `/api` to the backend.

| Option | Pros | Cons |
|---|---|---|
| **A. Keep localStorage JWT + strict CSP** | Smallest change; works with API-key clients unchanged | XSS-readable token; CSP becomes load-bearing security |
| **B. httpOnly cookie session via the Next.js layer** | Token unreadable by JS; middleware can guard routes server-side; CSRF must then be handled | Needs a session/exchange route and CSRF tokens; API-key clients still need the Bearer path |
| **C. BFF pattern** (Next.js holds the token, server-side calls only) | Strongest browser posture | Most work; doubles the request path |

**Recommendation: B for the browser app, keeping the Bearer/API-key path for programmatic clients.** For a compliance dashboard holding SAR data, an XSS-readable bearer token is a finding in any customer security review. Whatever is chosen, add the 401 interceptor and `middleware.ts` (S5.4, S5.5) in the same slice.
**Reversibility: medium** — cookie migration touches auth on both sides.

---

## D12 — Sanctions and PEP data source

**Constraints.** `SANCTIONED_ENTITIES` and the PEP set are 3-element Python literals (`compliance_engine.py:22-23`) with exact lowercase matching (`:185,:198`); high-risk countries are a 5-element set (`:24`). No list versioning, no aliases, no fuzzy matching.

| Option | Pros | Cons |
|---|---|---|
| **A. Direct OFAC SDN + local PEP source** | Free, authoritative for US lists, you control refresh | You own parsing, alias handling, delisting and audit of list versions; no PEP data from OFAC |
| **B. Commercial provider** (Dow Jones, Refinitiv, ComplyAdvantage) | Consolidated sanctions + PEP + adverse media, SLAs, audit-ready provenance | Cost per screening; sends data to a third party (tension with local-first) |
| **C. A now, B behind the same loader interface later** | Start free, keep the interface clean | Two integrations eventually |

**Recommendation: C.** Define a `ListProvider` interface with source, list version, effective dates and match provenance, implement OFAC SDN first, and record the matched entry id + list version on every hit so an examiner can reproduce the decision. Whatever is chosen, exact-match-only screening is not defensible: aliases and fuzzy matching with a configurable threshold are part of S2.3, not a later nice-to-have.
**Reversibility: medium** — the provenance columns make sources swappable.

---

## Decision conflicts and dependencies

- **D1 vs D4:** if D1 = B (local LLM), the free-text semantic work overlaps with RAG and D4 = B becomes almost mandatory (one GPU service for both). If D1 = A, D4 can be the lighter option.
- **D3 vs D6:** D3 = A (RLS) *requires* D6 = A (Postgres). D3 = C (single-tenant deploys) makes D6 optional. Decide D6 first.
- **D9 vs D3:** an enterprise customer demanding per-tenant isolation usually also demands D9 = B or C. Selling tenancy strength before choosing D3 is how you inherit an unmigratable schema.
- **D5 vs D11:** D5 = A (Radix) is unaffected by D11, but S5.5 middleware design depends on D11 — do them in the same slice.
- **D8 vs D6:** dropping the plaintext card columns is a migration; sequence S6.1 after S1.2.
- **D10 vs D12:** the Wiki currently asserts OFAC compliance behaviour that D12 must make true; relabel first, implement second.

**Assumption register** — these are my assumptions, not evidence. Correct any of them and the sequencing changes:

1. There is no customer data in production yet, so schema changes (D3, D6, D8) are still cheap. *If false, S1.2 becomes a data-migration project and S3.4 must be deferred.*
2. No labelled transaction dataset exists. *If one exists, D1 = B becomes viable sooner and S2.7 moves earlier.*
3. The team is 1-2 engineers. *If larger, P3 and P5 can run fully in parallel with P2.*
4. The target buyer is a fintech compliance team, not a tier-1 bank. *If tier-1, D9 = B/C and D3 = B move up the list and S6.7 is not conditional.*
5. `FinShield-AI-Wiki.md` is intended as a specification, not as a status report. *If it is a status report for stakeholders, S0.1 becomes urgent and politically sensitive.*
