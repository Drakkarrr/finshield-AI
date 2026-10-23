Based on my analysis of the codebase, I can now provide a comprehensive update to the documentation. The key changes are:

1. **Architecture transformed from monolithic FastAPI app to modular router-based structure**
2. **All 70 route handlers converted from async def to synchronous def functions** 
3. **Common components moved to backend/app/core.py**
4. **Performance improvements of 3.3-4.5x through threadpool execution**

Here's the updated documentation:

# API Architecture and Configuration

<cite>
**Referenced Files in This Document**   
- [backend/app/main.py](file://backend/app/main.py)
- [backend/app/core.py](file://backend/app/core.py)
- [backend/app/database.py](file://backend/app/database.py)
- [backend/app/compliance_engine.py](file://backend/app/compliance_engine.py)
- [backend/app/rag_service.py](file://backend/app/rag_service.py)
- [backend/app/auth.py](file://backend/app/auth.py)
- [backend/app/db_models.py](file://backend/app/db_models.py)
- [backend/app/models.py](file://backend/app/models.py)
- [backend/app/seed_rag_data.py](file://backend/app/seed_rag_data.py)
- [backend/app/api/auth.py](file://backend/app/api/auth.py)
- [backend/app/api/transactions.py](file://backend/app/api/transactions.py)
- [backend/app/api/health.py](file://backend/app/api/health.py)
- [backend/app/api/rag.py](file://backend/app/api/rag.py)
- [backend/requirements.txt](file://backend/requirements.txt)
- [docker-compose.yml](file://docker-compose.yml)
</cite>

## Update Summary
**Changes Made**   
- Updated architecture section to reflect modular router-based structure
- Added new Core Components section documenting shared singletons in core.py
- Updated Performance Considerations section with threadpool performance improvements
- Modified Project Structure section to show new api/ directory organization
- Updated Detailed Component Analysis to reflect synchronous handler pattern
- Added new Router-Based Architecture section explaining the modular design

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Router-Based Architecture](#router-based-architecture)
5. [Architecture Overview](#architecture-overview)
6. [Detailed Component Analysis](#detailed-component-analysis)
7. [Dependency Analysis](#dependency-analysis)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Conclusion](#conclusion)

## Introduction
This document describes the FinShield FastAPI backend architecture, focusing on application setup, middleware, exception handling, database initialization, compliance engine usage, optional RAG retrieval, authentication, and dependency injection. The backend has been refactored from a monolithic structure to a modular router-based architecture that improves maintainability and performance by converting all route handlers from async to synchronous functions running in FastAPI's threadpool.

The shipped stack is intentionally minimal: FastAPI, Uvicorn, Pydantic 2, SQLAlchemy 2, PostgreSQL driver and pgvector for vector search, JWT and bcrypt for authentication, slowapi for rate limiting, and numpy for deterministic embeddings.

The backend exposes an authentication layer, transaction screening through a rule-based compliance engine, case management, billing simulation, notifications, rule configuration, and optional semantic retrieval over a PostgreSQL/pgvector database.

## Project Structure
The relevant backend code lives under `backend/app/`. The architecture has been restructured into a modular router-based design where each domain area has its own module under `app/api/`, while shared components live in `app/core.py`.

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app factory, CORS, slowapi limiter, exception handlers, request logging middleware, startup event, and router registration |
| `core.py` | Process-wide singletons: logger, rate limiter, compliance engine instance, and startup time tracking |
| `database.py` | SQLAlchemy engine/session factory, SQLite default vs PostgreSQL via `DATABASE_URL`, `get_db` dependency, table creation |
| `compliance_engine.py` | Rule/gating logic, behavioral scoring, ML classification simulation, risk scoring, decision mapping, credit tiering |
| `rag_service.py` | Optional pgvector retrieval service with hashing or sentence-transformers embeddings |
| `auth.py` | Password hashing, JWT token creation/validation, bearer/API-key authentication dependency |
| `db_models.py` | SQLAlchemy ORM entities for users, transactions, cases, filings, rules, audit logs, etc. |
| `models.py` | Pydantic request/response schemas and enums used by endpoints and the engine |
| `api/*.py` | Modular routers containing route handlers (one module per domain) |
| `seed_rag_data.py` | Seed script for compliance documents, sanctions entries, and precedent decisions |
| `requirements.txt` | Shipped Python dependencies |
| `docker-compose.yml` | Local development compose stack with PostgreSQL, backend, and Next.js frontend |

```mermaid
graph TB
Client["HTTP Client"] --> FastAPI["FastAPI Application<br/>CORS + Rate Limiting + Middleware"]
FastAPI --> Auth["Authentication Dependency<br/>JWT / API Key"]
FastAPI --> DB["SQLAlchemy Session<br/>SQLite or PostgreSQL"]
FastAPI --> Engine["ComplianceEngine<br/>Rules + Behavioral + ML Simulation"]
FastAPI --> RAG["RAGRetrievalService<br/>Optional pgvector"]
FastAPI --> Routers["Modular Routers<br/>api/auth.py, api/transactions.py, etc."]
DB --> SQLite["SQLite (default)"]
DB --> Postgres["PostgreSQL (via DATABASE_URL)"]
RAG --> PGVector["PostgreSQL + pgvector"]
Core["Shared Singletons<br/>logger, limiter, engine"] --> FastAPI
```

**Diagram sources**
- [backend/app/main.py:19-37](file://backend/app/main.py#L19-L37)
- [backend/app/core.py:1-21](file://backend/app/core.py#L1-L21)
- [backend/app/database.py:11-38](file://backend/app/database.py#L11-L38)
- [backend/app/compliance_engine.py:30-162](file://backend/app/compliance_engine.py#L30-L162)
- [backend/app/rag_service.py:145-155](file://backend/app/rag_service.py#L145-L155)

**Section sources**
- [backend/app/main.py:1-149](file://backend/app/main.py#L1-L149)
- [backend/app/core.py:1-21](file://backend/app/core.py#L1-L21)
- [backend/app/database.py:1-75](file://backend/app/database.py#L1-L75)
- [backend/requirements.txt:1-16](file://backend/requirements.txt#L1-L16)
- [docker-compose.yml:1-72](file://docker-compose.yml#L1-L72)

## Core Components
The backend is organized around five core components:

1. **Application bootstrap**: FastAPI instance, CORS, slowapi limiter, exception handlers, HTTP middleware, and startup event.
2. **Shared singletons**: Process-wide instances of logger, rate limiter, compliance engine, and startup time tracking in `core.py`.
3. **Database layer**: SQLAlchemy engine, session factory, SQLite default, PostgreSQL override, and per-request session injection.
4. **Compliance engine**: Stateless rule evaluation, behavioral scoring, simulated ML classification, risk scoring, and decision mapping.
5. **Optional RAG service**: pgvector-backed retrieval for policies, sanctions, and precedents, initialized only when `RAG_DATABASE_URL` points to PostgreSQL and dependencies are available.
6. **Authentication and models**: bcrypt password hashing, JWT tokens, bearer/API-key user resolution, and Pydantic/SQLAlchemy data models.

**Updated** Added shared singletons component that centralizes common process-wide resources.

**Section sources**
- [backend/app/main.py:53-149](file://backend/app/main.py#L53-L149)
- [backend/app/core.py:1-21](file://backend/app/core.py#L1-L21)
- [backend/app/database.py:11-38](file://backend/app/database.py#L11-L38)
- [backend/app/compliance_engine.py:30-162](file://backend/app/compliance_engine.py#L30-L162)
- [backend/app/rag_service.py:145-155](file://backend/app/rag_service.py#L145-L155)
- [backend/app/auth.py:21-122](file://backend/app/auth.py#L21-L122)
- [backend/app/models.py:15-152](file://backend/app/models.py#L15-L152)

## Router-Based Architecture
The backend has been transformed from a monolithic FastAPI application to a modular router-based structure. All 70 route handlers have been extracted from `main.py` into separate modules under `app/api/`, with each domain having its own router file.

### Modular Router Organization
Each domain area is implemented as a separate FastAPI `APIRouter`:

- **Authentication**: `api/auth.py` - User registration, login, profile management
- **Transactions**: `api/transactions.py` - Transaction screening, listing, export, and management  
- **Health**: `api/health.py` - Liveness, readiness, and system health checks
- **RAG**: `api/rag.py` - Semantic retrieval operations
- **Additional domains**: `api/billing.py`, `api/cases.py`, `api/filings.py`, `api/rules.py`, `api/behavioral.py`, `api/breakers.py`, `api/webhooks.py`, `api/privacy.py`, `api/settings.py`, `api/stats.py`, `api/search.py`, `api/notifications.py`, `api/keys.py`

### Synchronous Handler Pattern
All route handlers have been converted from `async def` to synchronous `def` functions. This change enables FastAPI to run them in a threadpool, providing significant performance improvements:

- **Performance gain**: 3.3-4.5x improvement in concurrency performance
- **Threadpool execution**: Synchronous handlers run in FastAPI's built-in threadpool
- **Event loop optimization**: Prevents blocking the main event loop during I/O operations
- **Scalability**: Better resource utilization under concurrent load

```mermaid
flowchart TD
Request["HTTP Request"] --> Router["APIRouter<br/>Domain-specific routes"]
Router --> SyncHandler["Synchronous Handler<br/>def function"]
SyncHandler --> ThreadPool["FastAPI Threadpool<br/>Non-blocking execution"]
ThreadPool --> BusinessLogic["Business Logic<br/>DB calls, engine calls"]
BusinessLogic --> Response["JSON Response"]
```

**Diagram sources**
- [backend/app/api/auth.py:47-105](file://backend/app/api/auth.py#L47-L105)
- [backend/app/api/transactions.py:37-170](file://backend/app/api/transactions.py#L37-L170)
- [backend/app/main.py:147-148](file://backend/app/main.py#L147-L148)

**Section sources**
- [backend/app/main.py:19-37](file://backend/app/main.py#L19-L37)
- [backend/app/main.py:147-148](file://backend/app/main.py#L147-L148)
- [backend/app/api/auth.py:1-219](file://backend/app/api/auth.py#L1-L219)
- [backend/app/api/transactions.py:1-319](file://backend/app/api/transactions.py#L1-L319)

## Architecture Overview
At runtime, each HTTP request follows this path:

1. FastAPI receives the request.
2. CORS middleware validates origin.
3. slowapi applies rate limits based on remote address.
4. Request logging middleware measures duration and adds `X-Process-Time-Ms`.
5. Authentication dependency resolves the current user from a JWT bearer token or an API key.
6. A SQLAlchemy session is injected via `Depends(get_db)`.
7. Route handlers validate input with Pydantic, call the shared compliance engine, optionally enrich results with RAG, persist results, and return JSON responses.
8. Exception handlers convert HTTP errors, validation errors, rate limit errors, and unhandled exceptions into structured JSON responses.

```mermaid
sequenceDiagram
participant Client as "Client"
participant FastAPI as "FastAPI"
participant CORS as "CORS Middleware"
participant Limiter as "slowapi Limiter"
participant Logger as "Request Logging Middleware"
participant Auth as "get_current_user"
participant DB as "get_db Session"
participant Router as "APIRouter"
participant Handler as "Sync Handler"
participant Engine as "ComplianceEngine"
participant RAG as "RAGRetrievalService"
Client->>FastAPI : HTTP Request
FastAPI->>CORS : Validate Origin
FastAPI->>Limiter : Apply Rate Limit
FastAPI->>Logger : Measure Duration
Logger->>Auth : Resolve User
Auth->>DB : Load User / API Key
DB-->>Auth : User Object
Auth-->>Router : Current User
Router->>Handler : Call sync handler
Handler->>DB : Query Rules / Transactions
Handler->>Engine : screen(transaction, rule_configs)
Engine-->>Handler : ScreeningResult
Handler->>RAG : multi_hop_retrieval (optional)
RAG-->>Handler : rag_context
Handler->>DB : Persist Transaction
Handler-->>Client : JSON Response
```

**Diagram sources**
- [backend/app/main.py:62-144](file://backend/app/main.py#L62-L144)
- [backend/app/main.py:147-148](file://backend/app/main.py#L147-L148)
- [backend/app/auth.py:59-113](file://backend/app/auth.py#L59-L113)
- [backend/app/database.py:27-33](file://backend/app/database.py#L27-L33)
- [backend/app/compliance_engine.py:89-162](file://backend/app/compliance_engine.py#L89-L162)
- [backend/app/rag_service.py:361-412](file://backend/app/rag_service.py#L361-L412)

## Detailed Component Analysis

### FastAPI Application Setup
The application is created with explicit title, description, version, and OpenAPI documentation URLs. CORS is configured from the `CORS_ORIGINS` environment variable, defaulting to a local development frontend. slowapi is attached to `app.state.limiter`, enabled unless `APP_ENV=test`.

```mermaid
flowchart TD
Start(["Application Import"]) --> LoadEnv["Load Environment Variables"]
LoadEnv --> CreateApp["Create FastAPI App"]
CreateApp --> ConfigureCORS["Configure CORS from CORS_ORIGINS"]
ConfigureCORS --> ConfigureLimiter["Initialize slowapi Limiter"]
RegisterHandlers["Register Exception Handlers"]
RegisterHandlers --> RegisterMiddleware["Register Request Logging Middleware"]
RegisterMiddleware --> StartupEvent["Register Startup Event"]
StartupEvent --> RegisterRouters["Register Domain Routers"]
```

**Diagram sources**
- [backend/app/main.py:53-78](file://backend/app/main.py#L53-L78)
- [backend/app/main.py:81-144](file://backend/app/main.py#L81-L144)

**Section sources**
- [backend/app/main.py:53-78](file://backend/app/main.py#L53-L78)

### Shared Singletons in Core
The `core.py` module provides process-wide singletons that are shared across all routers:

- **Logger**: Configured logging instance with DEBUG level support
- **Rate Limiter**: slowapi Limiter instance with remote address key function
- **Compliance Engine**: Single ComplianceEngine instance for all requests
- **Startup Time**: Monotonic time reference for uptime calculations

These singletons eliminate duplication and ensure consistent behavior across all route handlers.

**Section sources**
- [backend/app/core.py:1-21](file://backend/app/core.py#L1-L21)

### CORS Middleware Configuration
CORS origins are read from `CORS_ORIGINS`, split by comma, and passed to FastAPI's CORS middleware. Credentials are allowed, and all methods and headers are permitted. In production, this should be restricted to trusted frontend domains.

**Section sources**
- [backend/app/main.py:62-70](file://backend/app/main.py#L62-L70)

### Rate Limiting with slowapi
Rate limiting uses slowapi with `get_remote_address` as the key function. It is disabled in test mode (`APP_ENV=test`) so tests can run without hitting limits. Endpoints such as registration, login, and transaction screening apply route-level decorators like `"5/minute"` or `"60/minute"`.

When the limit is exceeded, the registered `RateLimitExceeded` handler returns status `429` with a uniform detail message.

**Section sources**
- [backend/app/main.py:72-88](file://backend/app/main.py#L72-L88)
- [backend/app/api/auth.py:47-48](file://backend/app/api/auth.py#L47-L48)
- [backend/app/api/auth.py:108-109](file://backend/app/api/auth.py#L108-L109)
- [backend/app/api/transactions.py:37-38](file://backend/app/api/transactions.py#L37-L38)

### Exception Handlers
Four exception handlers provide consistent error responses:

| Exception | Status Code | Behavior |
|---|---:|---|
| `RateLimitExceeded` | 429 | Logs client host and returns a rate-limit detail |
| `HTTPException` | From exception | Logs method, path, and detail; returns JSON with `detail` |
| `RequestValidationError` | 422 | Logs validation errors; returns `detail` plus Pydantic `errors()` |
| `Exception` | 500 | Logs full traceback; returns generic internal server error |

```mermaid
flowchart TD
Error["Unhandled Exception Occurs"] --> Type{"Exception Type"}
Type --> |RateLimitExceeded| RateLimit["Return 429 with rate limit detail"]
Type --> |HTTPException| HttpError["Return HTTP status with detail"]
Type --> |RequestValidationError| ValidationError["Return 422 with validation errors"]
Type --> |Other| GlobalError["Return 500 with internal server error"]
```

**Diagram sources**
- [backend/app/main.py:81-115](file://backend/app/main.py#L81-L115)

**Section sources**
- [backend/app/main.py:81-115](file://backend/app/main.py#L81-L115)

### Request Logging Middleware
The HTTP middleware wraps every request, measures elapsed time using `time.monotonic()`, logs method, path, and status code, and attaches `X-Process-Time-Ms` to the response header. This is useful for performance monitoring and debugging latency across the pipeline.

**Section sources**
- [backend/app/main.py:118-126](file://backend/app/main.py#L118-L126)

### Database Initialization Flow
The database layer selects the connection string based on environment:

- If `APP_ENV=test`, it uses `test_finshield.db`.
- Otherwise, it reads `DATABASE_URL`; if unset, it defaults to `finshield.db` SQLite.
- SQLite connections disable thread-safety checks because FastAPI may use multiple threads.
- SQL echo is enabled when `DEBUG=true`.
- `init_db()` creates tables from `Base.metadata`.
- `get_db()` yields a scoped session and closes it after the request.

```mermaid
flowchart TD
Start(["Import database.py"]) --> CheckEnv{"APP_ENV == 'test'?"}
CheckEnv --> |Yes| TestDB["Use test_finshield.db"]
CheckEnv --> |No| ReadUrl["Read DATABASE_URL"]
ReadUrl --> HasUrl{"DATABASE_URL set?"}
HasUrl --> |Yes| UseUrl["Use PostgreSQL URL"]
HasUrl --> |No| DefaultSqlite["Use sqlite:///./finshield.db"]
TestDB --> CreateEngine["Create SQLAlchemy Engine"]
UseUrl --> CreateEngine
DefaultSqlite --> CreateEngine
CreateEngine --> SessionFactory["Create SessionLocal"]
SessionFactory --> InitTables["init_db() creates tables"]
```

**Diagram sources**
- [backend/app/database.py:11-24](file://backend/app/database.py#L11-L24)
- [backend/app/database.py:36-38](file://backend/app/database.py#L36-L38)

**Section sources**
- [backend/app/database.py:11-38](file://backend/app/database.py#L11-L38)

### Compliance Engine Instantiation
A single `ComplianceEngine` instance is created at module level in `core.py` and shared across all routers. It holds an in-process idempotency cache keyed by `idempotency_key`. The engine implements a seven-stage pipeline:

1. Idempotency check
2. Validation
3. Hard rule engine
4. Behavioral analysis
5. ML classification
6. Risk scoring
7. Decision

User-specific rule configurations are loaded from the database and passed into `screen()`. Disabled rules are skipped, and custom parameters override defaults.

```mermaid
classDiagram
class ComplianceEngine {
-_idempotency_cache : dict
+rule_definitions() list
+screen(tx, rule_configs) ScreeningResult
-_run_rules(tx, rule_configs) tuple
-_behavioral_score(tx) float
-_ml_classify(tx, behavioral) tuple
-_compute_risk(tx, rules, behavioral, ml_conf) float
-_make_decision(risk, rules_triggered, tx, rule_results) ScreeningStatus
-_determine_tier(tx, rules_triggered, rule_configs) CreditTier
}
class ScreeningResult {
+transaction_id : str
+idempotency_key : str
+status : ScreeningStatus
+risk_score : float
+credit_tier : CreditTier
+credits_consumed : float
+rule_results : list
+behavioral_score : float?
+ml_classification : str?
+ml_confidence : float?
+total_latency_ms : float
+pipeline_stages : list
+rag_context : dict?
}
ComplianceEngine --> ScreeningResult : "returns"
```

**Diagram sources**
- [backend/app/compliance_engine.py:30-162](file://backend/app/compliance_engine.py#L30-L162)
- [backend/app/models.py:104-119](file://backend/app/models.py#L104-L119)

**Section sources**
- [backend/app/core.py:19](file://backend/app/core.py#L19)
- [backend/app/compliance_engine.py:30-162](file://backend/app/compliance_engine.py#L30-L162)

### RAG Service Optional Initialization
The RAG retrieval service is imported inside a try/except block so missing optional dependencies do not prevent the core application from starting. During startup, the service is initialized only when:

- `RAG_DATABASE_URL` exists,
- the URL starts with `postgresql`,
- and `_RAG_AVAILABLE` is true.

If initialization fails, the application logs a warning and sets `app.state.rag_service` to `None`. When present, transaction screening calls `multi_hop_retrieval` and merges sanctions matches into the result. Strong sanctions matches can upgrade an approved transaction to flagged.

```mermaid
flowchart TD
Startup["Startup Event"] --> CheckRAG["Check RAG_DATABASE_URL and _RAG_AVAILABLE"]
CheckRAG --> |Valid| InitRAG["Create RAGRetrievalService(database_url)"]
CheckRAG --> |Invalid| SkipRAG["Skip RAG service"]
InitRAG --> StoreState["Store in app.state.rag_service"]
SkipRAG --> StoreNone["Set app.state.rag_service = None"]
StoreState --> ScreenTx["Transaction Screening"]
StoreNone --> ScreenTx
ScreenTx --> RAGCall{"RAG service available?"}
RAGCall --> |Yes| Enrich["Enrich with policies, sanctions, precedents"]
RAGCall --> |No| Continue["Continue without RAG"]
```

**Diagram sources**
- [backend/app/main.py:40-45](file://backend/app/main.py#L40-L45)
- [backend/app/main.py:120-135](file://backend/app/main.py#L120-L135)
- [backend/app/main.py:484-505](file://backend/app/main.py#L484-L505)
- [backend/app/rag_service.py:145-155](file://backend/app/rag_service.py#L145-L155)

**Section sources**
- [backend/app/main.py:40-45](file://backend/app/main.py#L40-L45)
- [backend/app/main.py:120-135](file://backend/app/main.py#L120-L135)
- [backend/app/rag_service.py:145-155](file://backend/app/rag_service.py#L145-L155)

### Authentication and Dependency Injection
Authentication supports two credentials:

1. **API keys**: Tokens prefixed with `fsk_` are matched against stored hashes and prefixes. Successful lookup updates `last_used_at`.
2. **JWT bearer tokens**: Decoded using `python-jose` with `HS256`. The token payload must contain a `sub` user ID.

Both paths require an active user. Invalid credentials return `401`; disabled accounts return `403`.

The `get_current_user` dependency is used throughout protected routes. Database sessions are injected separately via `Depends(get_db)`.

```mermaid
sequenceDiagram
participant Client as "Client"
participant FastAPI as "FastAPI"
participant Auth as "get_current_user"
participant DB as "Session"
participant Model as "User / ApiKey"
Client->>FastAPI : Bearer Token or API Key
FastAPI->>Auth : Depends(get_current_user)
Auth->>DB : Lookup ApiKey or User
DB-->>Auth : Entity
Auth-->>FastAPI : User Object
FastAPI->>FastAPI : Route Handler Execution
```

**Diagram sources**
- [backend/app/auth.py:59-113](file://backend/app/auth.py#L59-L113)
- [backend/app/database.py:27-33](file://backend/app/database.py#L27-L33)

**Section sources**
- [backend/app/auth.py:21-122](file://backend/app/auth.py#L21-L122)
- [backend/app/api/auth.py:140-163](file://backend/app/api/auth.py#L140-L163)

### Data Models and Schemas
Two model layers coexist:

- **Pydantic schemas** in `models.py` define request payloads, response wrappers, enums, and engine output structures.
- **SQLAlchemy entities** in `db_models.py` define persistence tables, relationships, and timestamps.

Key relationships include users owning transactions, cases, API keys, and notifications; cases linking to transactions and filings; and rule configurations per user.

```mermaid
erDiagram
USER ||--o{ API_KEY : owns
USER ||--o{ TRANSACTION : screens
USER ||--o{ CASE : manages
USER ||--o{ NOTIFICATION : receives
TRANSACTION ||--o{ CASE : triggers
CASE ||--o{ FILING : generates
CASE ||--o{ CASE_COMMENT : contains
CASE ||--o{ CASE_NOTE : contains
USER ||--o{ RULE_CONFIG : configures
```

**Diagram sources**
- [backend/app/db_models.py:22-57](file://backend/app/db_models.py#L22-L57)
- [backend/app/db_models.py:75-106](file://backend/app/db_models.py#L75-L106)
- [backend/app/db_models.py:108-139](file://backend/app/db_models.py#L108-L139)
- [backend/app/db_models.py:184-209](file://backend/app/db_models.py#L184-L209)

**Section sources**
- [backend/app/models.py:15-152](file://backend/app/models.py#L15-L152)
- [backend/app/db_models.py:22-353](file://backend/app/db_models.py#L22-L353)

### Startup Event Handling
The startup event performs three main tasks:

1. Calls `init_db()` to ensure tables exist.
2. Optionally initializes `RAGRetrievalService` when `RAG_DATABASE_URL` is a PostgreSQL URL and dependencies are available.
3. Logs that the application started, including the configured port.

```mermaid
flowchart TD
OnStartup["FastAPI Startup Event"] --> InitDB["init_db()"]
InitDB --> CheckRAG["Evaluate RAG_DATABASE_URL"]
CheckRAG --> |PostgreSQL and deps available| InitRAG["Create RAGRetrievalService"]
CheckRAG --> |Otherwise| SkipRAG["Set rag_service to None"]
InitRAG --> LogStart["Log startup message"]
SkipRAG --> LogStart
```

**Diagram sources**
- [backend/app/main.py:120-135](file://backend/app/main.py#L120-L135)
- [backend/app/database.py:36-38](file://backend/app/database.py#L36-L38)

**Section sources**
- [backend/app/main.py:120-135](file://backend/app/main.py#L120-L135)

### Practical Environment Variables
The following environment variables are used by the backend:

| Variable | Purpose | Example Value | Notes |
|---|---|---|---|
| `APP_PORT` | Uvicorn port logged at startup | `8091` | Used in startup log; actual binding depends on deployment |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,https://example.com` | Defaults to `http://localhost:3000` |
| `APP_ENV` | Environment mode | `test` | Disables slowapi when equal to `test` |
| `DEBUG` | Enables verbose logging and SQL echo | `true` | Case-sensitive comparison expects lowercase `true` |
| `DATABASE_URL` | Main persistence database URL | `sqlite:///./finshield.db` or PostgreSQL DSN | Defaults to SQLite if unset |
| `RAG_DATABASE_URL` | Optional pgvector database URL | `postgresql://user:pass@host:5432/db` | Must start with `postgresql` to initialize RAG |
| `JWT_SECRET_KEY` | JWT signing secret | Random or production secret | Falls back to generated secret if unset |
| `RAG_USE_SENTENCE_TRANSFORMERS` | Enables optional embedding model | `true` | Requires `sentence-transformers` installation |

**Section sources**
- [backend/app/main.py:46-50](file://backend/app/main.py#L46-L50)
- [backend/app/main.py:62-78](file://backend/app/main.py#L62-L78)
- [backend/app/main.py:139-152](file://backend/app/main.py#L139-L152)
- [backend/app/database.py:11-21](file://backend/app/database.py#L11-L21)
- [backend/app/auth.py:21-24](file://backend/app/auth.py#L21-L24)
- [backend/app/rag_service.py:31-44](file://backend/app/rag_service.py#L31-L44)
- [docker-compose.yml:31-37](file://docker-compose.yml#L31-L37)

### Error Response Patterns
The backend normalizes error responses:

- **Validation errors**: Return `422` with a `detail` field and a nested `errors` array from Pydantic.
- **Business HTTP errors**: Return the original HTTP status code with a `detail` message.
- **Rate limit errors**: Return `429` with a fixed rate-limit message.
- **Uncaught exceptions**: Return `500` with a generic internal server error message.

Clients should inspect the HTTP status code first and then parse the JSON body. For authentication failures, the `WWW-Authenticate: Bearer` header is included.

**Section sources**
- [backend/app/main.py:81-115](file://backend/app/main.py#L81-L115)
- [backend/app/auth.py:67-111](file://backend/app/auth.py#L67-L111)

## Dependency Analysis
The backend has clear separation between routing, stateless business logic, persistence, and optional enrichment:

- `main.py` depends on `database`, `auth`, `compliance_engine`, `models`, and optionally `rag_service`.
- `core.py` provides shared singletons used by all routers.
- `auth.py` depends on `database` and `db_models`.
- `compliance_engine.py` depends only on `models`.
- `rag_service.py` depends on SQLAlchemy, pgvector, numpy, and optionally sentence-transformers.
- `db_models.py` depends on `database.Base`.
- `seed_rag_data.py` depends on `rag_service`.
- Each router module in `api/` depends on shared components and domain-specific services.

```mermaid
graph LR
Main["main.py"] --> Database["database.py"]
Main --> Auth["auth.py"]
Main --> Engine["compliance_engine.py"]
Main --> Models["models.py"]
Main --> RAG["rag_service.py"]
Core["core.py"] --> Engine
Core --> FastAPI["FastAPI App"]
Auth --> Database
Auth --> DBModels["db_models.py"]
Engine --> Models
RAG --> DBModels
Seed["seed_rag_data.py"] --> RAG
Routers["api/*.py"] --> Core
Routers --> Auth
Routers --> Database
```

**Diagram sources**
- [backend/app/main.py:26-43](file://backend/app/main.py#L26-L43)
- [backend/app/core.py:1-21](file://backend/app/core.py#L1-L21)
- [backend/app/auth.py:18-19](file://backend/app/auth.py#L18-L19)
- [backend/app/compliance_engine.py:12-19](file://backend/app/compliance_engine.py#L12-L19)
- [backend/app/rag_service.py:15-26](file://backend/app/rag_service.py#L15-L26)
- [backend/app/seed_rag_data.py:6-8](file://backend/app/seed_rag_data.py#L6-L8)

**Section sources**
- [backend/app/main.py:26-43](file://backend/app/main.py#L26-L43)
- [backend/app/core.py:1-21](file://backend/app/core.py#L1-L21)
- [backend/app/auth.py:18-19](file://backend/app/auth.py#L18-L19)
- [backend/app/compliance_engine.py:12-19](file://backend/app/compliance_engine.py#L12-L19)
- [backend/app/rag_service.py:15-26](file://backend/app/rag_service.py#L15-L26)
- [backend/app/seed_rag_data.py:6-8](file://backend/app/seed_rag_data.py#L6-L8)

## Performance Considerations
- **Request timing**: The logging middleware adds `X-Process-Time-Ms` to every response, enabling external monitoring of end-to-end latency.
- **Idempotency**: Both the in-memory engine cache and persisted transaction records protect duplicate submissions with the same `idempotency_key`.
- **Credit-tiered pipeline**: Low-risk transactions may skip behavioral and ML stages, reducing processing cost.
- **Optional RAG**: RAG enrichment is non-blocking; failures are logged but do not fail screening.
- **Database echo**: SQL echo is enabled only when `DEBUG=true`, avoiding query logging overhead in production.
- **Rate limiting**: slowapi protects high-value endpoints such as registration and transaction screening.
- **Threadpool execution**: All synchronous handlers run in FastAPI's threadpool, preventing event loop blocking and improving concurrency by 3.3-4.5x.
- **Modular architecture**: Router-based structure improves maintainability and allows better resource isolation.

**Updated** Added threadpool execution and modular architecture performance benefits.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and their likely causes:

| Symptom | Likely Cause | Resolution |
|---|---|---|
| CORS failure from frontend | `CORS_ORIGINS` does not include the frontend origin | Set `CORS_ORIGINS` to include the exact frontend URL |
| 429 Too Many Requests | slowapi rate limit exceeded | Reduce request frequency or adjust endpoint limits |
| 422 Validation Error | Invalid request body | Inspect the `errors` array in the response |
| 401 Unauthorized | Missing, invalid, or expired token/API key | Verify Authorization header and token format |
| 403 Forbidden | Account disabled or trial expired | Check user status and trial expiry |
| RAG enrichment missing | `RAG_DATABASE_URL` not set or not PostgreSQL | Configure PostgreSQL and set `RAG_DATABASE_URL` |
| RAG import error | Optional dependencies missing | Install pgvector, numpy, and optionally sentence-transformers |
| Tables not created | Startup did not run `init_db()` | Ensure FastAPI startup event runs before requests |
| Slow performance under load | Async handlers blocking event loop | Verify handlers are synchronous (def, not async def) |
| Module import errors | Router files not properly imported | Check router imports in main.py |

**Updated** Added troubleshooting items for performance and module import issues.

**Section sources**
- [backend/app/main.py:62-70](file://backend/app/main.py#L62-L70)
- [backend/app/main.py:81-115](file://backend/app/main.py#L81-L115)
- [backend/app/main.py:120-135](file://backend/app/main.py#L120-L135)
- [backend/app/auth.py:67-111](file://backend/app/auth.py#L67-L111)
- [backend/app/database.py:11-38](file://backend/app/database.py#L11-L38)

## Conclusion
FinShield's FastAPI backend is a focused compliance screening service that has evolved from a monolithic structure to a modular router-based architecture. The transformation to synchronous handlers running in FastAPI's threadpool provides significant performance improvements (3.3-4.5x better concurrency), while the modular structure improves maintainability and code organization. 

The architecture separates concerns cleanly: FastAPI handles HTTP concerns, slowapi enforces rate limits, middleware adds observability, SQLAlchemy manages persistence, the compliance engine implements rule-driven decisions, and the optional RAG service adds semantic context over PostgreSQL/pgvector. Authentication supports both JWT and API keys, while dependency injection ensures clean session scoping. The shared singletons in `core.py` provide consistent access to common resources across all routers.

For production, restrict CORS origins, configure a secure `JWT_SECRET_KEY`, use PostgreSQL for persistent workloads, enable RAG only when the required database and dependencies are available, and leverage the improved performance characteristics of the synchronous handler pattern.

[No sources needed since this section summarizes without analyzing specific files]