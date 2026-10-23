<p align="center">
  <h1 align="center">FinShield AI</h1>
  <p align="center">
    <strong>Local-first transaction compliance engine</strong><br/>
    RAG retrieval · LoRA classifier · Behavioral fraud detection · Case management · SAR/STR filing
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"/>
    <img src="https://img.shields.io/badge/FastAPI-0.110-009688" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791" alt="PostgreSQL"/>
    <img src="https://img.shields.io/badge/Llama-LoRA%20fine--tuned-orange" alt="Llama LoRA"/>
    <img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"/>
  </p>
</p>

---

> **Documentation status.** Parts of this README describe the *target* product, not the code as it stands. Sections are labelled **Implemented** or **Target**. The authoritative gap analysis — every claim checked against source with `path:line` evidence — lives in [docs/architecture/evolution/](./docs/architecture/evolution/README.md), and implementation progress is tracked in [PROGRESS.md](./docs/architecture/evolution/PROGRESS.md). Where this README and the code disagree, the code wins; the OpenAPI schema at `/api/docs` is the source of truth for the API surface.

---

## What is FinShield AI?

FinShield AI is a **full-lifecycle compliance engine** for financial transactions. It screens transactions against hard compliance rules, ML-based classification, and continuous behavioral monitoring — then routes flagged items through case management, investigation workflow, and regulatory filing (SAR/STR). All inference runs on infrastructure you control. No transaction data leaves your boundary.

It's designed for compliance teams at fintechs and banks who need:
- **Detection** that covers 100% of transactions (behavioral monitor) without ML cost on every one
- **Investigation** workflow (cases, not flat queues) with SLA enforcement and escalation
- **Regulatory filing** (SAR/STR) with deadline tracking and narrative assistance
- **Audit trail** defensible to regulators — every decision, every override, every config change
- **Config-first** operation — thresholds, rules, model versions, all runtime, no redeploy

---

## Key Features

> **Target feature set.** This list is the product vision. For the per-feature status (`Implemented & wired` / `Built but not wired` / `Stub` / `Absent`) see [Wiki §21](./FinShield-AI-Wiki.md#21-implementation-status--future-work). In short, today: the hard-rule engine, case management, SAR/STR filing records, rule configuration and pgvector retrieval are implemented; the classifier and behavioral stage in the screening path are simulated; circuit breakers, webhooks, DSAR, multi-tenancy, encryption, observability and the model lifecycle are not yet built or are stubs.

### Detection Pipeline
- **Hard rule engine** — deterministic compliance rules (sanctions blocks, country restrictions, amount thresholds) authored from admin UI, no code changes
- **Agentic RAG retrieval** — multi-hop retrieval across policy, sanctions, and precedent indexes using pgvector + LangChain
- **LoRA fine-tuned classifier** — DSPy-compiled, Pydantic-validated compliance decisions (approve/flag/block)
- **Independent risk scorer** — decoupled from classifier to prevent correlated blind spots
- **Behavioral monitoring** — per-account anomaly detection on 100% of transactions, with cold-start handling for new accounts
- **Gating logic** — reconciles all signals; disagreement or low confidence forces human review

### Investigation & Filing
- **Case management** — lifecycle states, assignment, SLA timers, escalation policies, investigator notes
- **SAR/STR filing** — draft generation, narrative assistance, deadline tracking, safe harbor logging
- **Real-time dashboard** — case-centric workspace with WebSocket push, full reasoning trail per transaction

### Enterprise Operations
- **Circuit breaker resilience** — graceful degradation when dependencies fail; never silently auto-approves
- **Multi-tenant isolation** — shared schema with `tenant_id` on every owned table, enforced by PostgreSQL row-level security (ruling D3; originally specified as schema-per-tenant)
- **Data privacy (GDPR/CCPA)** — DSAR handling, right-to-erasure workflow, PII classification and masking
- **Encryption & key management** — at-rest (pgcrypto), in-transit (TLS 1.3), secrets via Vault
- **Observability** — distributed tracing (OpenTelemetry), metrics (Prometheus), structured JSON logs
- **Model lifecycle** — shadow mode, data drift detection, eval harness, model cards, sign-off workflow
- **Full audit logging** — append-only, every decision and config change, chain-of-custody export

---

## Architecture

> **Target pipeline.** Today the screening path runs, in order: idempotency check → hard rules (sanctions/PEP/geography/amount against small built-in lists) → a simulated behavioral score → a simulated classifier → risk blend → rule-action precedence gate → optional pgvector RAG check (when `RAG_DATABASE_URL` points at Postgres). There is no circuit-breaker check, no worker and no webhook delivery in the path yet.

```
Transaction → Idempotency Check → Sanitization → Circuit Breaker Check
                                                         |
                                            +------------+------------+
                                          healthy                  degraded
                                            |                        |
                                      Hard Rule Engine         Human review
                                            |                  (degraded mode)
                                     +------+------+
                                   BLOCK         pass
                                     |             |
                                     |       Behavioral Monitor
                                     |             |
                                     |       +-----+-----+
                                     |     below      above threshold
                                     |       |            |
                                     |   auto-pass   RAG + Classifier
                                     |       |       + Risk Scorer
                                     |       |            |
                                     |       +-----+------+
                                     |             |
                                     |        Gating Logic
                                     |             |
                                     |     +-------+-------+
                                     |     |               |
                                     |  auto-resolve    Create/attach
                                     |     |            to case
                                     |     |               |
                                     |     |         Case Management
                                     |     |          (SLA, assign,
                                     |     |           escalate)
                                     |     |               |
                                     |     |          +----+----+
                                     |     |        resolved  confirmed
                                     |     |          |          |
                                     |     |          |     SAR/STR filing
                                     |     |          |          |
                                     +-----+----------+----------+
                                             |
                                       Audit Log (append-only)
                                             |
                                       Dashboard + Webhooks
```

See the [Project Wiki](./FinShield-AI-Wiki.md) for the full technical flow, design principles, and step-by-step pipeline description.

---

## Tech Stack

Status: **Implemented** = in `backend/requirements.txt` / `platform-app/package.json` and used. **Partial** = present but not as described. **Target** = not in the repo; on the roadmap ([migration-roadmap.md](./docs/architecture/evolution/migration-roadmap.md)). Where an architecture decision has replaced the original choice, the ruling is noted ([decision-map.md](./docs/architecture/evolution/decision-map.md)).

| Layer | Technology | Status |
|---|---|---|
| API | FastAPI 0.115 (SQLAlchemy 2.0 sync, Pydantic 2.9, slowapi) | Implemented |
| Async Processing | Celery + Redis | Target (S4.1) |
| Database | PostgreSQL 16 + pgvector, Alembic migrations | Implemented — Postgres is primary (SQLite only for the test suite) |
| Retrieval | LangChain (agentic RAG) | Partial — direct pgvector cosine search without LangChain; embeddings are an MD5 feature hash, not a semantic model (S2.4) |
| Prompt Optimization | DSPy | Target — superseded by ruling D1 (no LLM in the decision path) |
| Classification | Llama (LoRA via PEFT + BitsAndBytes) | Target — the current "classifier" is simulated; ruling D1 replaces it with a deterministic `RiskModel` (S2.5) |
| Model Serving | vLLM | Target — superseded by ruling D1 |
| Behavioral Scoring | Statistical (z-score / isolation forest) | Partial — a z-score monitor exists but is not called by screening (S2.1) |
| RAG Evaluation | RAGAS | Target (S2.7) |
| Frontend | Next.js 14 + React 18 + TypeScript + Tailwind 3 | Implemented |
| Observability | OpenTelemetry + Prometheus + structlog | Target (S4.4) — today: stdlib logging + `X-Process-Time-Ms` header |
| Containerization | Docker Compose (dev) / Kubernetes + Helm (prod) | Partial — root `docker-compose.yml` implemented; Kubernetes superseded by ruling D9 (managed PaaS) |
| Secrets | HashiCorp Vault | Target — superseded by ruling D9 (platform secret store) |

---

## Quick Start

### Prerequisites
- Docker with Docker Compose v2
- For running the backend outside Docker: Python 3.11
- For running the dashboard outside Docker: Node.js 20+

No GPU is needed — nothing in the current stack runs a model.

### Run the stack with Docker (Implemented)

```bash
git clone <your-fork-url> finshield
cd finshield

# Create your local env file, then set JWT_SECRET_KEY and POSTGRES_PASSWORD in it.
# Compose refuses to start while either is unset.
cp .env.example .env

# Starts postgres (pgvector), backend (FastAPI) and frontend (Next.js)
docker compose up -d --build
docker compose ps        # wait until all three are healthy

# Optional: seed the RAG index (policies, sanctions entries, precedents)
docker compose exec backend python -m app.seed_rag_data
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8091 |
| API docs (OpenAPI) | http://localhost:8091/api/docs |
| Health | http://localhost:8091/api/health |

PostgreSQL is the primary database. The backend container runs `alembic upgrade head` before it starts serving, so the schema is always at the latest migration.

**Upgrading from an older checkout that stored data in SQLite?** Copy the old file out of the old backend container first (`docker cp finshield-backend:/app/finshield.db ./finshield-old.db`), bring the new stack up, then import it:

```bash
docker cp ./finshield-old.db finshield-backend:/tmp/old.db
docker compose exec backend python -m scripts.sqlite_to_postgres /tmp/old.db
```

### Run the backend without Docker (Implemented)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # set JWT_SECRET_KEY and DATABASE_URL
docker compose up -d postgres                         # from the repo root: Postgres on 127.0.0.1:5432
alembic upgrade head
uvicorn app.main:app --port 8091 --reload
```

PostgreSQL is required outside the test suite (SQLite is test-only). Without `RAG_DATABASE_URL` the app runs with RAG disabled.

### Submitting Your First Transaction (Implemented)

```bash
# 1. Register (returns a JWT); or log in with POST /api/auth/login
TOKEN=$(curl -s -X POST http://localhost:8091/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@example.com","password":"change-me-please","first_name":"Ada","last_name":"Analyst"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Screen a transaction
curl -s -X POST http://localhost:8091/api/v1/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "idempotency_key": "TX-00001",
    "amount": 18400.00,
    "currency": "USD",
    "transaction_type": "wire",
    "sender_name": "Acme Corp",
    "receiver_name": "Globex Ltd",
    "destination_country": "US",
    "description": "Wire transfer for equipment purchase"
  }'
```

`transaction_type` is one of `wire`, `ach`, `card`, `international`, `crypto`, `p2p`. Programmatic clients can use an API key (`fsk_…`, created at `POST /api/v1/keys`) in place of the JWT. The response is a `TransactionResponse`:

```json
{
  "success": true,
  "data": {
    "transaction_id": "…",
    "idempotency_key": "TX-00001",
    "status": "approved | flagged | blocked | in_review",
    "risk_score": 0.31,
    "credit_tier": "…",
    "credits_consumed": 1.0,
    "rule_results": [{"rule_id": "…", "rule_type": "…", "rule_name": "…", "triggered": false, "detail": null, "latency_ms": 0.1}],
    "behavioral_score": 0.12,
    "ml_classification": "…",
    "ml_confidence": 0.9,
    "total_latency_ms": 4.2,
    "pipeline_stages": ["…"],
    "rag_context": null
  },
  "error": null
}
```

Until roadmap slice S2.2 lands, `behavioral_score`, `ml_classification` and `ml_confidence` contain simulated (random) values, so the same payload can score differently on repeat submissions.

---

## Project Structure

### Actual structure (Implemented)

```
finshield/
├── backend/                  # FastAPI service
│   ├── app/
│   │   ├── main.py           # app setup + all API routes (being split into api/ + domain/, slice S1.6)
│   │   ├── compliance_engine.py  # screening pipeline: rules, scoring, precedence gate
│   │   ├── rag_service.py    # pgvector retrieval (policies, sanctions, precedents)
│   │   ├── seed_rag_data.py  # RAG seed corpus (python -m app.seed_rag_data)
│   │   ├── auth.py           # bcrypt passwords, JWT, fsk_ API keys
│   │   ├── db_models.py      # SQLAlchemy ORM models
│   │   ├── models.py         # Pydantic request/response schemas
│   │   └── database.py       # engine, session, init_db()
│   ├── migrations/           # Alembic (schema owner; runs on container start)
│   ├── scripts/              # sqlite_to_postgres.py (one-off import of old SQLite data)
│   ├── tests/                # pytest suite (API + engine; Postgres-only checks run in CI)
│   ├── Dockerfile
│   └── requirements.txt
├── platform-app/             # Next.js 14 dashboard (src/app, src/components, src/lib/api.ts)
├── website/                  # static nginx marketing site
├── docs/architecture/evolution/  # gap analysis, roadmap, implementation ledger
├── .github/workflows/ci.yml
├── docker-compose.yml        # postgres (pgvector, primary DB) + backend + frontend
├── FinShield-AI-Wiki.md      # design specification (with implementation-status labels)
├── DEPLOYMENT.md / DOCKER.md
└── README.md
```

### Target structure (not yet built)

Ruling D13 replaces the layout below with packages *inside* `backend/app/` (`api/`, `domain/`, `worker/`) — see [MASTER-PROMPT.md §5](./docs/architecture/evolution/MASTER-PROMPT.md). The original target tree is kept for reference:

```
finshield-ai/
├── api/                  # FastAPI application, routers, schemas, middleware
├── config/               # Centralized runtime configuration service
├── worker/               # Celery worker, tasks, pipeline orchestration
├── scoring/              # Behavioral, risk, and gating scoring logic
├── cases/                # Case management domain (lifecycle, SLA, assignment)
├── filings/              # SAR/STR filing generation and tracking
├── rules/                # Hard rule engine (no-code compliance rules)
├── models/               # LoRA adapters, training, DSPy signatures, inference
├── rag/                  # pgvector RAG (embedding, retrieval, agentic chains)
├── events/               # Event bus (internal Redis Streams + webhook dispatch)
├── privacy/              # GDPR/CCPA (DSAR, erasure, PII masking)
├── security/             # Prompt injection defense, RBAC, encryption, key mgmt
├── db/                   # SQLAlchemy models, Alembic migrations
├── dashboard/            # React frontend (case queue, admin, reports)
├── audit/                # Append-only audit logger, export, retention
├── observability/        # OpenTelemetry, Prometheus metrics, structured logging
├── sdk/                  # Python SDK for integrating systems
├── common/               # Shared exceptions, utilities, constants
├── docker/               # Dockerfiles and docker-compose
├── deploy/k8s/           # Kubernetes Helm chart
└── tests/                # Unit, integration, eval, and load tests
```

---

## Configuration

> **Target.** Today the only runtime-configurable parameters are per-user hard-rule overrides (`/api/v1/rules`, editable from the dashboard's Rules page). Thresholds, model versions, feature flags, SLA timers and retention are code constants; tenants do not exist yet. The runtime config service is roadmap slice S1.4.

FinShield treats all operational parameters as runtime configuration, not code:

| Parameter | Example | Scope |
|---|---|---|
| Gating thresholds | `gate.auto_resolve_confidence_min = 0.80` | Per tenant |
| Behavioral trigger | `fraud.behavioral.trigger_threshold = 0.65` | Per tenant/policy |
| Model version | Active LoRA adapter (staging/production) | Per tenant |
| Feature flags | Enable/disable behavioral, sanctions, filing | Per tenant/env |
| Hard rules | Condition-action pairs, priority-ordered | Per tenant |
| SLA timers | Per-severity case deadlines | Per tenant |
| Data retention | Audit log retention window | Per tenant/jurisdiction |

All config changes are audit-logged with before/after values and actor identity.

See [Wiki Section 12](./FinShield-AI-Wiki.md#12-configuration--extensibility-philosophy) for the full configurable parameters table.

---

## API Overview

The API is versioned (`/api/v1/...`) with idempotent transaction submission. The live OpenAPI schema at `http://localhost:8091/api/docs` is the source of truth (ruling D10); the table below is a summary.

| Endpoint | Method | Description | Status |
|---|---|---|---|
| `/api/auth/register`, `/api/auth/login` | POST | Create an account / obtain a JWT | Implemented |
| `/api/v1/keys` | GET/POST/DELETE | Manage `fsk_` API keys | Implemented |
| `/api/v1/transactions` | POST | Submit a transaction for screening | Implemented |
| `/api/v1/transactions/{id}` | GET | Get transaction status and decision | Implemented |
| `/api/v1/cases` | GET | List cases (filterable by status, severity, assignee) | Implemented |
| `/api/v1/cases/{id}` | GET | Get case detail with full reasoning trail | Implemented |
| `/api/v1/filings` | GET | List SAR/STR filings | Implemented |
| `/api/v1/rules`, `/api/v1/rules/{id}` | GET / PATCH | List built-in hard rules / override one per user (enable, threshold, action) | Implemented — creating new rules is Target |
| `/api/v1/rules/simulate` | POST | Simulate rule configuration against historical transactions | Implemented |
| `/api/health` | GET | System health | Implemented — see the Wiki status table for probe coverage |
| `/api/v1/privacy/dsar` | POST | Submit a data subject access request | Stub — records an audit entry only (S3.3) |
| `/api/v1/cases/{id}/resolve` | POST | Resolve a case (approve, override, escalate) | Target — case status changes go through the case update routes today |
| `/api/v1/filings/{id}` | GET | Get filing detail and status | Implemented |
| `/api/v1/admin/users` | CRUD | User and role management | Target (S3.1) |
| `/api/v1/settings` | GET/PUT | Thresholds, retention, notification config | Target (S1.4) |

<details><summary>Original target endpoint table</summary>

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/transactions` | POST | Submit a transaction for screening |
| `/api/v1/transactions/{id}` | GET | Get transaction status and decision |
| `/api/v1/cases` | GET | List cases (filterable by status, severity, assignee) |
| `/api/v1/cases/{id}` | GET | Get case detail with full reasoning trail |
| `/api/v1/cases/{id}/resolve` | POST | Resolve a case (approve, override, escalate) |
| `/api/v1/filings` | GET | List SAR/STR filings |
| `/api/v1/filings/{id}` | GET | Get filing detail and status |
| `/api/v1/rules` | GET/POST | List/create hard compliance rules |
| `/api/v1/rules/{id}/simulate` | POST | Simulate a rule against historical data |
| `/api/v1/admin/users` | CRUD | User and role management |
| `/api/v1/settings` | GET/PUT | Thresholds, retention, notification config |
| `/api/v1/health` | GET | System health (per-dependency circuit breaker status) |
| `/api/v1/privacy/dsar` | POST | Submit a data subject access request |

</details>

Full API documentation: [http://localhost:8091/api/docs](http://localhost:8091/api/docs) (when running locally)

---

## Testing

### Current suite (Implemented)

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
APP_ENV=test python -m pytest tests/ -v --cov=app      # unit + API tests on SQLite; e2e excluded by default
ruff check . && mypy app                                # lint + typecheck

# End-to-end filing flow against a running stack (docker compose up first)
APP_ENV=test python -m pytest tests/e2e -m e2e -v

cd ../platform-app
npm ci && npx tsc --noEmit && npm run lint && npm run build
```

### Target suite (not yet built)

Evaluation harness (S2.7) and load tests (S6.5) are on the roadmap. The commands below describe that target:

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires docker-compose running)
pytest tests/integration/ -v

# ML evaluation (classifier precision/recall)
python tests/eval/eval_classifier.py

# Behavioral monitor evaluation (AUC, precision, recall)
python tests/eval/eval_behavioral.py

# RAG evaluation (RAGAS metrics)
python tests/eval/eval_rag.py

# Load testing
locust -f tests/load/test_throughput.py
```

---

## Deployment

### Development (Implemented)
```bash
docker compose up -d --build
```

### Production

There is no production deployment target in the repo yet. Ruling D9 sets it as a managed PaaS using the platform's own secret store (roadmap slices S6.2/S6.3); [DEPLOYMENT.md](./DEPLOYMENT.md) describes a proposed setup. Before any production use, see the blockers in [evolution-summary.md](./docs/architecture/evolution/evolution-summary.md).

### Production on Kubernetes (Target — conditional, ruling D9)

No Helm chart or `deploy/` directory exists. The original target:

```bash
# Add the Helm repo
helm repo add finshield ./deploy/k8s

# Install with your values
helm install finshield finshield/finshield \
  --namespace finshield \
  --create-namespace \
  --values deploy/k8s/values-prod.yaml
```

See [Wiki Section 17](./FinShield-AI-Wiki.md#17-enterprise--fintech-readiness) for HA, DR, multi-region, and capacity planning details.

---

## Security

**Implemented today:** bcrypt password hashing; HS256 JWTs; hashed `fsk_` API keys accepted alongside JWTs; per-user row filtering on every authenticated route; rate limits on register (5/min), login (10/min) and screening (60/min); all inference local (there is no external model call).

**Target** (not yet built — see roadmap phase P3 and S6.2):

- **Local-first**: all inference runs in your infrastructure, no data leaves your boundary
- **Prompt injection defense**: multi-layer (denylist, structured delimiting, perplexity scoring, length limits)
- **Encryption**: at rest (pgcrypto/TDE), in transit (TLS 1.3, mTLS between services)
- **Secrets management**: HashiCorp Vault integration, API key hashing and rotation
- **RBAC**: role-scoped access with configurable permission matrix per tenant
- **Audit**: every action, every config change, every model decision — immutably logged

Report security vulnerabilities to `security@your-org.com`. Do not file publicly.

---

## Documentation

- **[Architecture evolution](./docs/architecture/evolution/README.md)** — authoritative gap analysis between docs and code, roadmap, and implementation ledger
- **[Project Wiki](./FinShield-AI-Wiki.md)** — design specification (design intent, with implementation-status labels) covering architecture, technical flow, all modules, design principles, user stories, and known gaps
  - [Technical Flow](./FinShield-AI-Wiki.md#3-technical-flow) — full pipeline walkthrough
  - [Behavioral Monitoring](./FinShield-AI-Wiki.md#4-behavioral-monitoring--fraud-detection) — anomaly detection with cold-start handling
  - [Hard Rule Engine](./FinShield-AI-Wiki.md#5-hard-rule-engine) — no-code deterministic compliance rules
  - [Case Management](./FinShield-AI-Wiki.md#6-case-management) — investigation workflow with SLA enforcement
  - [SAR/STR Filing](./FinShield-AI-Wiki.md#7-sarstr-filing) — regulatory filing support
  - [Circuit Breaker](./FinShield-AI-Wiki.md#8-circuit-breaker--resilience) — degraded mode routing
  - [Data Privacy](./FinShield-AI-Wiki.md#10-data-privacy--gdpr-compliance) — GDPR/CCPA compliance
  - [ML Operations](./FinShield-AI-Wiki.md#14-ml-operations--model-lifecycle) — shadow mode, drift detection, model cards
  - [Project Structure](./FinShield-AI-Wiki.md#19-project-structure) — full directory layout with module descriptions

---

## License

Proprietary. All rights reserved.
