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
- **Multi-tenant isolation** — separate PostgreSQL schemas per tenant for regulatory-grade data isolation
- **Data privacy (GDPR/CCPA)** — DSAR handling, right-to-erasure workflow, PII classification and masking
- **Encryption & key management** — at-rest (pgcrypto), in-transit (TLS 1.3), secrets via Vault
- **Observability** — distributed tracing (OpenTelemetry), metrics (Prometheus), structured JSON logs
- **Model lifecycle** — shadow mode, data drift detection, eval harness, model cards, sign-off workflow
- **Full audit logging** — append-only, every decision and config change, chain-of-custody export

---

## Architecture

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

| Layer | Technology |
|---|---|
| API | FastAPI |
| Async Processing | Celery + Redis |
| Database | PostgreSQL 16 + pgvector |
| Retrieval | LangChain (agentic RAG) |
| Prompt Optimization | DSPy |
| Classification | Llama (LoRA via PEFT + BitsAndBytes) |
| Model Serving | vLLM |
| Behavioral Scoring | Statistical (z-score / isolation forest) |
| RAG Evaluation | RAGAS |
| Frontend | React 18 + TypeScript |
| Observability | OpenTelemetry + Prometheus + structlog |
| Containerization | Docker Compose (dev) / Kubernetes + Helm (prod) |
| Secrets | HashiCorp Vault |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for dashboard)
- GPU with ≥16GB VRAM (for model inference; CPU-only mode available for development)

### Local Development

```bash
# Clone the repository
git clone https://github.com/your-org/finshield-ai.git
cd finshield-ai

# Copy environment configuration
cp .env.example .env
# Edit .env with your local settings

# Start the full stack (API + worker + Postgres/pgvector + Redis + dashboard)
docker compose -f docker/docker-compose.yml up -d

# Run database migrations
docker compose -f docker/docker-compose.yml exec api alembic upgrade head

# Load sample compliance policies into the RAG index
docker compose -f docker/docker-compose.yml exec api python -m rag.ingest_policies --seed

# Access the services
# API:          http://localhost:8000
# API Docs:     http://localhost:8000/docs
# Dashboard:    http://localhost:3000
# Prometheus:   http://localhost:9090
```

### Submitting Your First Transaction

```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: TX-00001" \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{
    "account_id": "ACC-4471",
    "amount": 18400.00,
    "currency": "USD",
    "type": "withdrawal",
    "destination_country": "US",
    "memo": "Wire transfer for equipment purchase",
    "metadata": {
      "channel": "online_banking",
      "beneficiary": "Acme Corp"
    }
  }'
```

Response:
```json
{
  "transaction_id": "TX-88213",
  "status": "pending_review",
  "case_id": "CASE-2024-00847",
  "trigger_source": "behavioral",
  "severity": "flagged",
  "message": "Transaction flagged for review — behavioral anomaly detected"
}
```

---

## Project Structure

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

The API is versioned (`/api/v1/...`) with idempotent transaction submission and webhook events.

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

Full API documentation: [http://localhost:8000/docs](http://localhost:8000/docs) (when running locally)

---

## Testing

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

### Development
```bash
docker compose -f docker/docker-compose.yml up -d
```

### Production (Kubernetes)
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

- **Local-first**: all inference runs in your infrastructure, no data leaves your boundary
- **Prompt injection defense**: multi-layer (denylist, structured delimiting, perplexity scoring, length limits)
- **Encryption**: at rest (pgcrypto/TDE), in transit (TLS 1.3, mTLS between services)
- **Secrets management**: HashiCorp Vault integration, API key hashing and rotation
- **RBAC**: role-scoped access with configurable permission matrix per tenant
- **Audit**: every action, every config change, every model decision — immutably logged

Report security vulnerabilities to `security@your-org.com`. Do not file publicly.

---

## Documentation

- **[Project Wiki](./FinShield-AI-Wiki.md)** — canonical reference covering architecture, technical flow, all modules, design principles, user stories, and known gaps
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
