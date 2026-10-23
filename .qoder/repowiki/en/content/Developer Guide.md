# Developer Guide

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [FinShield-AI-Wiki.md](file://FinShield-AI-Wiki.md)
- [docker-compose.yml](file://docker-compose.yml)
- [backend/requirements.txt](file://backend/requirements.txt)
- [backend/app/main.py](file://backend/app/main.py)
- [backend/app/auth.py](file://backend/app/auth.py)
- [backend/app/database.py](file://backend/app/database.py)
- [backend/app/db_models.py](file://backend/app/db_models.py)
- [backend/app/models.py](file://backend/app/models.py)
- [backend/app/compliance_engine.py](file://backend/app/compliance_engine.py)
- [backend/app/rag_service.py](file://backend/app/rag_service.py)
- [backend/app/seed_rag_data.py](file://backend/app/seed_rag_data.py)
- [backend/tests/test_api.py](file://backend/tests/test_api.py)
- [backend/tests/test_compliance_engine.py](file://backend/tests/test_compliance_engine.py)
- [backend/pytest.ini](file://backend/pytest.ini)
- [.github/workflows/ci.yml](file://.github/workflows/ci.yml)
- [platform-app/package.json](file://platform-app/package.json)
- [platform-app/AGENTS.md](file://platform-app/AGENTS.md)
- [platform-app/src/lib/api.ts](file://platform-app/src/lib/api.ts)
- [platform-app/src/contexts/AuthContext.tsx](file://platform-app/src/contexts/AuthContext.tsx)
- [platform-app/next.config.js](file://platform-app/next.config.js)
- [platform-app/tsconfig.json](file://platform-app/tsconfig.json)
- [DOCKER.md](file://DOCKER.md)
</cite>

## Update Summary
**Changes Made**
- Corrected port references from 8000 to 8091 throughout the document
- Updated API documentation URLs to reference `/api/docs` consistently
- Enhanced tech stack table with accurate implementation status labels
- Clarified single-file FastAPI architecture vs target package-based structure
- Improved gap analysis between current implementation and aspirational design

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Development Environment Setup](#development-environment-setup)
4. [Coding Standards and Conventions](#coding-standards-and-conventions)
5. [Git Workflow, Branching, and Pull Requests](#git-workflow-branching-and-pull-requests)
6. [Architecture Overview](#architecture-overview)
7. [Core Components](#core-components)
8. [Detailed Component Analysis](#detailed-component-analysis)
9. [Adding Features, Rules, and API Endpoints](#adding-features-rules-and-api-endpoints)
10. [Testing Strategy](#testing-strategy)
11. [Debugging, Logging, and Performance Profiling](#debugging-logging-and-performance-profiling)
12. [Continuous Integration and Quality Gates](#continuous-integration-and-quality-gates)
13. [Troubleshooting Guide](#troubleshooting-guide)
14. [Conclusion](#conclusion)

## Introduction
This Developer Guide explains how to contribute to FinShield as a developer. It covers the real shipped codebase, not the aspirational directory layout described elsewhere in the repository. The current implementation consists of three deployables:

- `backend/`: FastAPI transaction screening API with authentication, persistence, rule engine, optional RAG retrieval, and test suite.
- `platform-app/`: Next.js 14 App Router dashboard that calls the backend through `src/lib/api.ts`.
- `website/`: Static marketing site plus legacy platform console pages; it is not part of the main Docker Compose stack.

The shipped runtime stack is defined by `backend/requirements.txt` and `platform-app/package.json`. Many items mentioned in the README or Wiki — Celery, Redis, LangChain, DSPy, LoRA/PEFT/BitsAndBytes, vLLM, RAGAS, HashiCorp Vault, OpenTelemetry, Prometheus, structlog, Kubernetes/Helm — are roadmap targets. The implemented detection path uses deterministic rules in `backend/app/compliance_engine.py`, optional pgvector-based RAG enrichment in `backend/app/rag_service.py`, SQLite or PostgreSQL persistence in `backend/app/database.py`, JWT/API-key auth in `backend/app/auth.py`, ORM entities in `backend/app/db_models.py`, request/response schemas in `backend/app/models.py`, and route mounting in `backend/app/main.py`.

**Updated** The API documentation is available at `/api/docs` (FastAPI's OpenAPI schema), which serves as the authoritative source for the API surface rather than hardcoded endpoint arrays.

**Section sources**
- [README.md:18-53](file://README.md#L18-L53)
- [README.md:107-124](file://README.md#L107-L124)
- [README.md:197-222](file://README.md#L197-L222)
- [FinShield-AI-Wiki.md:35-59](file://FinShield-AI-Wiki.md#L35-L59)
- [FinShield-AI-Wiki.md:62-215](file://FinShield-AI-Wiki.md#L62-L215)

## Project Structure
The repository contains four top-level areas relevant to development:

| Area | Purpose | Current Status |
|---|---|---|
| `backend/` | FastAPI application, compliance engine, models, database configuration, tests | Implemented |
| `platform-app/` | Next.js 14 dashboard under `src/` | Implemented |
| `website/` | Static marketing site and legacy platform HTML pages | Legacy / separate service |
| `.github/workflows/ci.yml` | CI pipeline for backend tests, frontend build, Docker builds, security scan | Implemented |

```mermaid
graph TB
Repo["Repository Root"]
Backend["backend/"]
Platform["platform-app/"]
Website["website/"]
CI[".github/workflows/ci.yml"]
Compose["docker-compose.yml"]
Repo --> Backend
Repo --> Platform
Repo --> Website
Repo --> CI
Compose --> Backend
Compose --> Platform
```

**Diagram sources**
- [docker-compose.yml:3-61](file://docker-compose.yml#L3-L61)
- [.github/workflows/ci.yml:13-87](file://.github/workflows/ci.yml#L13-L87)

**Section sources**
- [docker-compose.yml:1-72](file://docker-compose.yml#L1-L72)
- [.github/workflows/ci.yml:1-114](file://.github/workflows/ci.yml#L1-L114)

## Development Environment Setup
### Prerequisites
- Python 3.11+ for the backend.
- Node.js 18+ for the dashboard.
- Docker and Docker Compose for the full local stack.
- PostgreSQL with pgvector if you want RAG retrieval enabled.
- A GPU with at least 16GB VRAM is listed as a prerequisite in the README, but the shipped backend does not require it for normal operation; GPU-only features are not part of the current dependency set.

### Local Stack via Docker Compose
The root `docker-compose.yml` defines exactly three services:

| Service | Image / Build | Port | Notes |
|---|---|---:|---|
| `postgres` | `pgvector/pgvector:pg16` | `5432` | Used by RAG when `RAG_DATABASE_URL` points to PostgreSQL. |
| `backend` | `backend/Dockerfile` | `8091` | Defaults to SQLite unless `DATABASE_URL` is set. |
| `frontend` | `platform-app/Dockerfile` | `3000` | Rewrites `/api/*` to the backend. |

Important environment details:
- The backend container sets `DATABASE_URL=sqlite:///./finshield.db`.
- The RAG path uses `RAG_DATABASE_URL=postgresql://finshield:finshield_secret@postgres:5432/finshield`.
- The frontend container sets `API_URL=http://backend:8091` and `NEXT_PUBLIC_API_URL=http://localhost:8091`.
- `website/` is not started by this compose file; it has its own Dockerfile and nginx configuration.

```mermaid
graph TB
Client["Developer Browser"]
Frontend["Frontend Container<br/>port 3000"]
Backend["Backend Container<br/>port 8091"]
Postgres["PostgreSQL + pgvector<br/>port 5432"]
Client --> Frontend
Frontend --> Backend
Backend --> Postgres
```

**Diagram sources**
- [docker-compose.yml:4-61](file://docker-compose.yml#L4-L61)
- [platform-app/next.config.js:4-14](file://platform-app/next.config.js#L4-L14)

### Local Development Without Docker
You can run the backend and frontend locally without containers:

1. Install backend dependencies from `backend/requirements.txt`.
2. Start PostgreSQL with pgvector if you plan to seed and query RAG data.
3. Set `DATABASE_URL` to your preferred database URL.
4. Set `RAG_DATABASE_URL` to the PostgreSQL connection string.
5. Run the FastAPI app using Uvicorn on port `8091`.
6. Install frontend dependencies from `platform-app/package.json`.
7. Run `npm run dev` inside `platform-app`; it serves on port `3000`.
8. Configure `NEXT_PUBLIC_API_URL` so the dashboard can reach the local backend.

### Database Persistence Model
`backend/app/database.py` chooses the database based on environment:

| Condition | Database |
|---|---|
| `APP_ENV=test` | SQLite file `test_finshield.db` |
| Default | SQLite file `finshield.db` |
| `DATABASE_URL` provided | Uses the configured URL |

When `RAG_DATABASE_URL` starts with `postgresql` and optional RAG dependencies are available, `backend/app/main.py` initializes `RAGRetrievalService`. The RAG tables live in that PostgreSQL database, not in the default SQLite database.

**Section sources**
- [README.md:127-160](file://README.md#L127-L160)
- [docker-compose.yml:4-61](file://docker-compose.yml#L4-L61)
- [backend/app/database.py:11-21](file://backend/app/database.py#L11-L21)
- [backend/app/main.py:133-152](file://backend/app/main.py#L133-L152)

## Coding Standards and Conventions
### Backend Conventions
- Use Pydantic v2 models for all API input and output contracts.
- Keep business logic out of FastAPI route handlers where possible; put it in `ComplianceEngine` or dedicated modules.
- Persist domain entities through SQLAlchemy ORM models in `backend/app/db_models.py`.
- Use `get_db()` dependency for per-request sessions.
- Log structured information through Python's logging module; avoid printing secrets.
- Treat thresholds, rule parameters, feature flags, and model versions as configuration, not hard constants.
- Do not silently auto-approve when downstream components fail; route to human review or return an error.

### Frontend Conventions
- Use the Next.js App Router under `platform-app/src/app`.
- Share UI shell components under `platform-app/src/components`.
- Manage session state through `platform-app/src/contexts/AuthContext.tsx`.
- Call the backend only through `platform-app/src/lib/api.ts`.
- Keep TypeScript strict mode enabled as configured in `platform-app/tsconfig.json`.
- Respect the Next.js agent warning in `platform-app/AGENTS.md`: the installed Next.js version may have breaking changes relative to training data.

### Naming Conventions
- Backend routes use `/api/v1/...` for operational endpoints and `/api/auth/...` for authentication.
- Transaction records include an idempotency key.
- Case IDs start with `CASE-`.
- API keys use the `fsk_live_` prefix and are stored hashed.
- Screening statuses use the `ScreeningStatus` enum values.
- Rule definitions expose stable `rule_id` identifiers such as `RULE-001`.

**Updated** The FastAPI application is currently implemented as a single-file architecture in `backend/app/main.py`, though the target design specifies a package-based structure with separate routers, middleware, and domain modules.

**Section sources**
- [backend/app/models.py:17-152](file://backend/app/models.py#L17-L152)
- [backend/app/auth.py:21-121](file://backend/app/auth.py#L21-L121)
- [platform-app/src/lib/api.ts:357-417](file://platform-app/src/lib/api.ts#L357-L417)
- [platform-app/AGENTS.md:1-10](file://platform-app/AGENTS.md#L1-L10)
- [platform-app/tsconfig.json:1-42](file://platform-app/tsconfig.json#L1-L42)

## Git Workflow, Branching, and Pull Requests
The CI workflow runs on:

- Pushes to `main` and `develop`.
- Pull requests targeting `main`.

Recommended contribution flow:

1. Create a feature branch from `develop`.
2. Implement changes following the conventions above.
3. Add tests for new behavior.
4. Run backend tests with `pytest`.
5. Build the frontend with `npm run build`.
6. Open a pull request against `main` (or `develop` depending on team policy).
7. Ensure CI passes: backend tests, frontend build, lint, Docker config validation, and security scan.

Quality gates enforced by CI:

| Gate | Scope |
|---|---|
| Backend tests | `backend/tests/` |
| Frontend build | `platform-app/` |
| Frontend lint | `platform-app/` |
| Docker build | All three Dockerfiles |
| Docker Compose validation | `docker-compose config` |
| Dependency vulnerability scan | `backend/requirements.txt` |

**Section sources**
- [.github/workflows/ci.yml:3-114](file://.github/workflows/ci.yml#L3-L114)

## Architecture Overview
At runtime, the dashboard makes HTTP requests to `/api/*`. Next.js rewrites those paths to the backend URL configured by `API_URL` or `NEXT_PUBLIC_API_URL`. The backend validates requests, authenticates users or API keys, runs the compliance engine, optionally enriches results with RAG retrieval, persists outcomes, and returns typed responses.

```mermaid
sequenceDiagram
participant User as "Developer or Client"
participant Dashboard as "Next.js Dashboard"
participant Backend as "FastAPI Backend"
participant Engine as "ComplianceEngine"
participant DB as "SQLite or PostgreSQL"
participant RAG as "RAG Retrieval Service"
User->>Dashboard : Submit transaction or open case
Dashboard->>Backend : POST /api/v1/transactions
Backend->>Backend : Validate request and authenticate
Backend->>Engine : screen(transaction, rule_configs)
Engine->>DB : Read user rule configs
Engine-->>Backend : ScreeningResult
Backend->>RAG : Optional multi-hop retrieval
RAG-->>Backend : RAG context
Backend->>DB : Persist transaction and related records
Backend-->>Dashboard : Screening result
```

**Diagram sources**
- [platform-app/next.config.js:4-14](file://platform-app/next.config.js#L4-L14)
- [backend/app/main.py:434-570](file://backend/app/main.py#L434-L570)
- [backend/app/compliance_engine.py:89-162](file://backend/app/compliance_engine.py#L89-L162)
- [backend/app/rag_service.py:361-412](file://backend/app/rag_service.py#L361-L412)

## Core Components
### Backend Runtime
The FastAPI application mounts authentication routes, API key management, transaction screening, cases, credits, stats, rules, search, notifications, billing, and more. It also configures CORS, rate limiting, exception handling, request logging middleware, and startup initialization.

Key responsibilities:
- Request validation through Pydantic models.
- Authentication via JWT bearer tokens or hashed API keys.
- Idempotent transaction submission.
- Credit accounting.
- Case creation and listing.
- Rule listing and per-user rule configuration.
- Optional RAG enrichment.

**Updated** The backend is currently implemented as a single-file FastAPI application in `backend/app/main.py` (2927 lines), containing all routes, middleware, and business logic. The target architecture specifies a package-based structure with separate modules for API routes, domain logic, workers, and shared utilities.

**Section sources**
- [backend/app/main.py:54-152](file://backend/app/main.py#L54-L152)
- [backend/app/main.py:176-570](file://backend/app/main.py#L176-L570)

### Compliance Engine
The compliance engine implements a seven-stage pipeline:

1. Idempotency check.
2. Input validation.
3. Hard rule evaluation.
4. Behavioral analysis.
5. ML classification simulation.
6. Risk scoring.
7. Decision.

It exposes rule definitions, supports per-user rule overrides, determines credit tiers, and maps rule actions to final screening statuses.

**Section sources**
- [backend/app/compliance_engine.py:30-162](file://backend/app/compliance_engine.py#L30-L162)
- [backend/app/compliance_engine.py:164-381](file://backend/app/compliance_engine.py#L164-L381)

### Data Models and Schemas
Request/response contracts are defined in `backend/app/models.py`. Persistent entities are defined in `backend/app/db_models.py`. Examples include users, API keys, transactions, cases, audit logs, notifications, rule configurations, filings, circuit breakers, webhook events, account baselines, and precedent decisions.

**Section sources**
- [backend/app/models.py:17-152](file://backend/app/models.py#L17-L152)
- [backend/app/db_models.py:22-353](file://backend/app/db_models.py#L22-L353)

### Authentication
Authentication supports two bearer-token paths:

| Path | Behavior |
|---|---|
| API key | Starts with `fsk_`; backend verifies the hashed key and loads the owning user. |
| JWT token | Decodes the token payload and loads the user by subject ID. |

Passwords are hashed with bcrypt. Tokens are signed with HS256 using a secret loaded from `JWT_SECRET_KEY`.

**Section sources**
- [backend/app/auth.py:21-121](file://backend/app/auth.py#L21-L121)

### RAG Retrieval
RAG retrieval is optional. When `RAG_DATABASE_URL` points to PostgreSQL and optional dependencies are available, the service:

- Creates the `vector` extension.
- Creates RAG tables.
- Embeds text using either hashing-based vectors or optional sentence-transformers.
- Searches compliance documents, sanctions entries, and precedent decisions.
- Performs multi-hop retrieval combining policies, sanctions matches, and similar precedents.

**Section sources**
- [backend/app/rag_service.py:1-412](file://backend/app/rag_service.py#L1-L412)
- [backend/app/seed_rag_data.py:1-198](file://backend/app/seed_rag_data.py#L1-L198)

## Detailed Component Analysis
### Transaction Screening Flow
The transaction endpoint performs these steps:

1. Check trial expiry and credits.
2. Check idempotency key.
3. Load user rule configurations.
4. Run `ComplianceEngine.screen`.
5. Optionally enrich with RAG retrieval.
6. Update credits.
7. Persist the transaction.
8. Create notifications for important events.
9. Return the response.

```mermaid
flowchart TD
Start(["POST /api/v1/transactions"]) --> Auth["Authenticate user or API key"]
Auth --> Trial["Check trial and credits"]
Trial --> Idem{"Idempotency key exists?"}
Idem --> |Yes| ReturnStored["Return stored result"]
Idem --> |No| Rules["Load user rule configs"]
Rules --> Engine["Run compliance engine"]
Engine --> RAGCheck{"RAG service available?"}
RAGCheck --> |Yes| Enrich["Enrich with RAG context"]
RAGCheck --> |No| Persist["Persist transaction"]
Enrich --> Persist
Persist --> Notify["Create notifications"]
Notify --> Response(["Return ScreeningResult"])
```

**Diagram sources**
- [backend/app/main.py:434-570](file://backend/app/main.py#L434-L570)
- [backend/app/compliance_engine.py:89-162](file://backend/app/compliance_engine.py#L89-L162)

**Section sources**
- [backend/app/main.py:434-570](file://backend/app/main.py#L434-L570)

### Rule Engine Flow
The rule engine evaluates four built-in rules:

| Rule ID | Type | Action | Purpose |
|---|---|---|---|
| `RULE-001` | Sanctions | Block | Matches known sanctioned entities. |
| `RULE-002` | PEP | Flag | Matches politically exposed persons. |
| `RULE-003` | Threshold | Review | Checks amount thresholds. |
| `RULE-004` | Geography | Escalate | Blocks high-risk country destinations. |

User rule configurations can enable/disable rules and override editable parameters.

```mermaid
flowchart TD
Tx["Transaction"] --> Sanctions["Sanctions check"]
Tx --> PEP["PEP check"]
Tx --> Threshold["Threshold check"]
Tx --> Geography["High-risk country check"]
Sanctions --> Actions["Map rule action to status"]
PEP --> Actions
Threshold --> Actions
Geography --> Actions
Actions --> Decision["Final screening decision"]
```

**Diagram sources**
- [backend/app/compliance_engine.py:40-87](file://backend/app/compliance_engine.py#L40-L87)
- [backend/app/compliance_engine.py:164-240](file://backend/app/compliance_engine.py#L164-L240)
- [backend/app/compliance_engine.py:329-361](file://backend/app/compliance_engine.py#L329-L361)

**Section sources**
- [backend/app/compliance_engine.py:40-87](file://backend/app/compliance_engine.py#L40-L87)
- [backend/app/compliance_engine.py:164-240](file://backend/app/compliance_engine.py#L164-L240)
- [backend/app/compliance_engine.py:329-361](file://backend/app/compliance_engine.py#L329-L361)

### Authentication Flow
Both the dashboard and programmatic clients authenticate through bearer tokens. The frontend stores the JWT in `localStorage` and attaches it to every request through `api.ts`.

```mermaid
sequenceDiagram
participant UI as "Dashboard UI"
participant AuthCtx as "AuthContext"
participant ApiClient as "api.ts"
participant Backend as "FastAPI"
UI->>AuthCtx : login(email, password)
AuthCtx->>ApiClient : api.login()
ApiClient->>Backend : POST /api/auth/login
Backend-->>ApiClient : TokenResponse
ApiClient->>AuthCtx : Store token
UI->>ApiClient : Screen transaction
ApiClient->>Backend : POST /api/v1/transactions with Authorization header
Backend-->>ApiClient : ScreeningResult
```

**Diagram sources**
- [platform-app/src/contexts/AuthContext.tsx:42-68](file://platform-app/src/contexts/AuthContext.tsx#L42-L68)
- [platform-app/src/lib/api.ts:357-417](file://platform-app/src/lib/api.ts#L357-L417)
- [backend/app/auth.py:59-113](file://backend/app/auth.py#L59-L113)

**Section sources**
- [platform-app/src/contexts/AuthContext.tsx:1-107](file://platform-app/src/contexts/AuthContext.tsx#L1-L107)
- [platform-app/src/lib/api.ts:357-417](file://platform-app/src/lib/api.ts#L357-L417)
- [backend/app/auth.py:59-113](file://backend/app/auth.py#L59-L113)

## Adding Features, Rules, and API Endpoints
### Extending Existing Functionality
When adding functionality:

1. Decide whether the change belongs in the API layer, the engine, the data model, or the frontend client.
2. For backend logic, prefer extending `ComplianceEngine` or adding a focused service rather than growing `main.py`.
3. For persistence, add or extend SQLAlchemy models in `backend/app/db_models.py`.
4. For API contracts, add Pydantic models in `backend/app/models.py`.
5. For the dashboard, add types and methods in `platform-app/src/lib/api.ts`.
6. For UI state, use `platform-app/src/contexts/AuthContext.tsx` patterns or create a new context if needed.

### Adding a New Compliance Rule
To add a new rule:

1. Define the rule metadata in `ComplianceEngine.rule_definitions`.
2. Implement evaluation in `_run_rules`.
3. Map the rule action to a screening status in `_make_decision`.
4. If the rule has editable parameters, expose them through `parameters` and read them through the `param` helper.
5. Add tests in `backend/tests/test_compliance_engine.py`.
6. Add integration tests in `backend/tests/test_api.py` if the rule is configurable through the API.

Example pattern reference:
- Rule definition structure: [backend/app/compliance_engine.py:40-87](file://backend/app/compliance_engine.py#L40-L87)
- Rule evaluation: [backend/app/compliance_engine.py:164-240](file://backend/app/compliance_engine.py#L164-L240)
- Decision mapping: [backend/app/compliance_engine.py:329-361](file://backend/app/compliance_engine.py#L329-L361)

### Adding a New API Endpoint
Follow this pattern:

1. Add request/response models in `backend/app/models.py`.
2. Add the route handler in `backend/app/main.py`.
3. Apply authentication via `Depends(get_current_user)` where required.
4. Apply rate limiting via `@limiter.limit(...)` where appropriate.
5. Persist data through `app.database.get_db()`.
6. Add tests covering success, authentication, validation, and error cases.
7. Add frontend types and methods in `platform-app/src/lib/api.ts`.

**Updated** The interactive API documentation is available at `http://localhost:8091/api/docs` (FastAPI's OpenAPI schema), which automatically reflects all registered endpoints and their schemas.

Example reference:
- Transaction endpoint: [backend/app/main.py:434-570](file://backend/app/main.py#L434-L570)
- API client wrapper: [platform-app/src/lib/api.ts:373-417](file://platform-app/src/lib/api.ts#L373-L417)

### Adding a New Feature Page in the Dashboard
Use the existing App Router convention:

1. Create a folder under `platform-app/src/app/<feature>/page.tsx`.
2. Reuse shared layout components under `platform-app/src/components`.
3. Call backend endpoints through `platform-app/src/lib/api.ts`.
4. Handle authentication state through `platform-app/src/contexts/AuthContext.tsx`.

**Section sources**
- [backend/app/compliance_engine.py:40-87](file://backend/app/compliance_engine.py#L40-L87)
- [backend/app/compliance_engine.py:164-240](file://backend/app/compliance_engine.py#L164-L240)
- [backend/app/compliance_engine.py:329-361](file://backend/app/compliance_engine.py#L329-L361)
- [backend/app/main.py:434-570](file://backend/app/main.py#L434-L570)
- [platform-app/src/lib/api.ts:373-417](file://platform-app/src/lib/api.ts#L373-L417)

## Testing Strategy
### Backend Tests
The backend uses pytest with async support. Test configuration is in `backend/pytest.ini`.

Two major test files exist:

| File | Scope |
|---|---|
| `backend/tests/test_api.py` | Integration-style tests for auth, transactions, cases, credits, API keys, stats, rules, idempotency, billing, and root endpoint. |
| `backend/tests/test_compliance_engine.py` | Unit tests for the compliance engine pipeline, rules, credit tiers, decisions, idempotency, and rule result structure. |

Tests set `APP_ENV=test` before importing the app so the test database is used.

### Running Tests Locally
- Backend unit tests: `pytest backend/tests/test_compliance_engine.py -v`
- Backend integration tests: `pytest backend/tests/test_api.py -v`
- Full backend test suite: `pytest backend/tests/ -v`

### Test Expectations
Tests assert:
- Health endpoint returns expected version and service fields.
- Registration and login work correctly.
- Unauthenticated access returns 401.
- Transaction screening returns valid statuses.
- Sanctioned senders are blocked.
- High-risk countries trigger blocking behavior.
- API keys authenticate programmatic requests.
- Cases can be created and retrieved.
- Credits decrease after screening.
- Rules can be listed and customized.
- Duplicate idempotency keys return stored results.

**Section sources**
- [backend/pytest.ini:1-3](file://backend/pytest.ini#L1-L3)
- [backend/tests/test_api.py:1-560](file://backend/tests/test_api.py#L1-L560)
- [backend/tests/test_compliance_engine.py:1-224](file://backend/tests/test_compliance_engine.py#L1-L224)

## Debugging, Logging, and Performance Profiling
### Backend Logging
The backend configures Python logging at startup. In debug mode, log level is set to DEBUG; otherwise it uses INFO. A request logging middleware records method, path, status code, and duration.

For debugging:
- Enable debug logging by setting `DEBUG=true`.
- Inspect request durations via the `X-Process-Time-Ms` response header.
- Check logs for rate limit warnings, validation errors, and unhandled exceptions.

### Database Debugging
SQLAlchemy echo can be enabled by setting `DEBUG=true`, which affects the engine configuration.

### RAG Debugging
If RAG enrichment fails, the backend logs a warning but continues screening. To investigate:
- Verify `RAG_DATABASE_URL` points to a running PostgreSQL instance.
- Verify the `vector` extension is available.
- Seed sample data using `backend/app/seed_rag_data.py`.
- Confirm embeddings are generated and stored.

### Frontend Debugging
- Use browser developer tools to inspect network requests to `/api/*`.
- Check `localStorage` for the stored token.
- Verify `NEXT_PUBLIC_API_URL` resolves to the correct backend URL.
- Watch for `ApiError` thrown by `api.ts` when responses are not OK.

### Performance Considerations
- The compliance engine measures total pipeline latency and per-rule latency.
- The backend middleware measures request duration.
- RAG retrieval adds an extra step; it is optional and non-blocking for screening.
- Avoid heavy imports in hot paths; optional dependencies like sentence-transformers are gated behind an environment flag.

**Section sources**
- [backend/app/main.py:46-51](file://backend/app/main.py#L46-L51)
- [backend/app/main.py:118-126](file://backend/app/main.py#L118-L126)
- [backend/app/database.py:17-21](file://backend/app/database.py#L17-L21)
- [backend/app/rag_service.py:31-44](file://backend/app/rag_service.py#L31-L44)
- [platform-app/src/lib/api.ts:373-417](file://platform-app/src/lib/api.ts#L373-L417)

## Continuous Integration and Quality Gates
The GitHub Actions workflow enforces:

| Job | Trigger | Responsibility |
|---|---|---|
| `backend-tests` | Push to `main`/`develop`, PR to `main` | Install Python dependencies, run pytest, verify import order. |
| `frontend-build` | Push to `main`/`develop`, PR to `main` | Install Node dependencies, build Next.js app, run lint. |
| `docker-build` | Push to `refs/heads/main` | Build backend, platform, and website images; validate compose config. |
| `security-scan` | Pull requests | Run safety check against backend requirements. |

Expected contributor checks before opening a PR:

1. Backend tests pass.
2. Frontend builds successfully.
3. Linting passes.
4. Docker images build.
5. No obvious dependency vulnerabilities.

**Section sources**
- [.github/workflows/ci.yml:1-114](file://.github/workflows/ci.yml#L1-L114)

## Troubleshooting Guide
### Backend Cannot Connect to Database
Symptoms:
- Application fails to initialize tables.
- RAG enrichment fails.

Checks:
- Confirm `DATABASE_URL` is set correctly.
- Confirm `RAG_DATABASE_URL` points to PostgreSQL with pgvector.
- Confirm the `vector` extension exists in the RAG database.
- For tests, confirm `APP_ENV=test` so the test database is used.

Relevant files:
- [backend/app/database.py:11-21](file://backend/app/database.py#L11-L21)
- [backend/app/rag_service.py:148-155](file://backend/app/rag_service.py#L148-L155)

### RAG Retrieval Is Not Available
Symptoms:
- RAG enrichment is skipped.
- Policy/sanctions/precedent context is missing.

Checks:
- Ensure `RAG_DATABASE_URL` starts with `postgresql`.
- Ensure optional RAG dependencies are installed.
- Seed RAG data using `backend/app/seed_rag_data.py`.
- Confirm PostgreSQL is reachable from the backend.

Relevant files:
- [backend/app/main.py:138-150](file://backend/app/main.py#L138-L150)
- [backend/app/rag_service.py:31-44](file://backend/app/rag_service.py#L31-L44)
- [backend/app/seed_rag_data.py:10-24](file://backend/app/seed_rag_data.py#L10-L24)

### Frontend Cannot Reach Backend
Symptoms:
- Dashboard shows network errors.
- API calls fail with 401 or connection errors.

Checks:
- Verify `NEXT_PUBLIC_API_URL` points to the running backend.
- Verify `API_URL` is set for server-side rewrites.
- Confirm the frontend rewrite rule forwards `/api/*` to the backend.
- Confirm CORS allows the frontend origin.

Relevant files:
- [platform-app/next.config.js:4-14](file://platform-app/next.config.js#L4-L14)
- [backend/app/main.py:62-70](file://backend/app/main.py#L62-L70)

### Authentication Fails
Symptoms:
- Login succeeds but subsequent requests return 401.
- API key requests are rejected.

Checks:
- Confirm the token is stored in `localStorage`.
- Confirm the `Authorization` header is attached.
- For API keys, confirm the key starts with `fsk_` and is active.
- Confirm `JWT_SECRET_KEY` is consistent across restarts.

Relevant files:
- [platform-app/src/lib/api.ts:357-381](file://platform-app/src/lib/api.ts#L357-L381)
- [backend/app/auth.py:21-24](file://backend/app/auth.py#L21-L24)
- [backend/app/auth.py:76-113](file://backend/app/auth.py#L76-L113)

### Tests Fail Because of Database State
Symptoms:
- Tests fail due to missing tables or stale data.

Checks:
- Ensure `APP_ENV=test` is set before importing the app.
- Use the test database file.
- Reset the database in tests if needed.

Relevant files:
- [backend/tests/test_api.py:7-19](file://backend/tests/test_api.py#L7-L19)
- [backend/app/database.py:41-44](file://backend/app/database.py#L41-L44)

### Next.js Breaking Changes
Symptoms:
- Code written against older Next.js conventions fails.
- Agent-generated suggestions conflict with the installed version.

Action:
- Read `platform-app/AGENTS.md`.
- Consult the resolved Next.js documentation under `node_modules/next/dist/docs/`.
- Treat the installed version as authoritative.

Relevant files:
- [platform-app/AGENTS.md:1-10](file://platform-app/AGENTS.md#L1-L10)

**Section sources**
- [backend/app/database.py:11-21](file://backend/app/database.py#L11-L21)
- [backend/app/rag_service.py:148-155](file://backend/app/rag_service.py#L148-L155)
- [backend/app/seed_rag_data.py:10-24](file://backend/app/seed_rag_data.py#L10-L24)
- [platform-app/next.config.js:4-14](file://platform-app/next.config.js#L4-L14)
- [backend/app/main.py:62-70](file://backend/app/main.py#L62-L70)
- [platform-app/src/lib/api.ts:357-381](file://platform-app/src/lib/api.ts#L357-L381)
- [backend/app/auth.py:21-24](file://backend/app/auth.py#L21-L24)
- [backend/app/auth.py:76-113](file://backend/app/auth.py#L76-L113)
- [backend/tests/test_api.py:7-19](file://backend/tests/test_api.py#L7-L19)
- [backend/app/database.py:41-44](file://backend/app/database.py#L41-L44)
- [platform-app/AGENTS.md:1-10](file://platform-app/AGENTS.md#L1-L10)

## Conclusion
FinShield's shipped codebase is a local-first compliance engine with a FastAPI backend, a Next.js dashboard, and a static website. Contributors should focus on the three real modules: backend, platform-app, and website. Follow the established conventions for models, engines, routes, tests, and frontend clients. Treat configuration as first-class, keep hard rules deterministic and auditable, and ensure failures route to human review rather than silent approval. Before making changes, verify behavior against the actual source files, update tests, and ensure CI passes. For Next.js-specific issues, always consult the installed version's documentation as warned by `platform-app/AGENTS.md`.

**Updated** The current architecture uses a single-file FastAPI approach in `backend/app/main.py`, while the target design specifies a package-based structure. The API documentation is available at `/api/docs` and serves as the authoritative source for the API surface. Port 8091 is the standard backend port, not 8000. The tech stack includes both implemented features and roadmap targets, clearly distinguished by implementation status labels.