---
kind: error_handling
name: Error Handling — FastAPI Exception Handlers, HTTPException Propagation, and Frontend ApiError
category: error_handling
scope:
    - '**'
source_files:
    - backend/app/main.py
    - backend/app/auth.py
    - backend/app/database.py
    - platform-app/src/lib/api.ts
    - backend/tests/test_api.py
---

## Overview

FinShield's error handling is split across two deployables:

- **Backend (FastAPI)**: centralized exception handlers in `backend/app/main.py`, business errors raised as `fastapi.HTTPException` from route handlers and the auth dependency, plus a request-scoped logging middleware.
- **Frontend (Next.js)**: a thin `request()` wrapper in `platform-app/src/lib/api.ts` that translates non-`2xx` responses into a typed `ApiError` class carrying the HTTP status and a human-readable detail string.

There is no custom error-class hierarchy on the backend (no sentinel exceptions), no `panic`/`recover` analog, and no global error-reporting SDK. Errors are surfaced to callers via standard HTTP status codes and JSON bodies.

## Backend: Centralized Exception Handlers (`backend/app/main.py`)

Four `@app.exception_handler` registrations cover the full lifecycle of an incoming request:

| Handler | Trigger | Response shape | Logging |
|---|---|---|---|
| `rate_limit_handler` | `slowapi.errors.RateLimitExceeded` | `429 {"detail": "Rate limit exceeded..."}` | `logger.warning` with client host |
| `http_exception_handler` | Any `fastapi.HTTPException` | Echoes `exc.status_code` and `exc.detail` | `logger.info` with method, path, detail |
| `validation_exception_handler` | `RequestValidationError` (Pydantic) | `422 {"detail": "Invalid request data", "errors": [...]}` | `logger.warning` with parsed errors |
| `global_exception_handler` | Any unhandled `Exception` | `500 {"detail": "Internal server error"}` | `logger.error(..., exc_info=True)` |

The `HTTPException` handler is the canonical bridge between business logic and the wire format: every route handler raises it rather than returning raw dicts for error cases. Examples include:

- `400`: duplicate email, unknown plan, invalid date format, empty name fields, unsupported export format.
- `401`: invalid credentials, missing bearer token, invalid/expired JWT, invalid API key, invalid token payload, user not found.
- `403`: account disabled, trial expired.
- `402`: insufficient credits.
- `404`: transaction/case/key not found.

A single `@app.middleware("http")` (`request_logging_middleware`) wraps every request, logs `method → status (duration_ms)`, and injects an `X-Process-Time-Ms` response header. It does not swallow exceptions; they bubble to the handlers above.

## Business-Layer Error Raising Patterns

Route handlers raise `HTTPException` directly at the point of validation failure. There is no intermediate service layer or custom exception type — the pattern is:

```python
if not resource:
    raise HTTPException(status_code=404, detail="Resource not found")
```

Optional dependencies are handled by catching `Exception` around their initialization and setting `app.state.rag_service = None`, then guarding downstream calls with `getattr(app.state, "rag_service", None)`. The same `try/except Exception` pattern is used inside the screening pipeline so that RAG enrichment failures do not abort the core transaction flow.

## Auth Error Path (`backend/app/auth.py`)

`get_current_user` is the central auth gate. It raises `HTTPException` with explicit `status.HTTP_401_UNAUTHORIZED` / `status.HTTP_403_FORBIDDEN` codes and always attaches `headers={"WWW-Authenticate": "Bearer"}` when authentication fails. Two auth paths exist:

1. **API key** (`fsk_live_*` prefix): hashed against stored `ApiKey.key_hash`; failure returns 401.
2. **JWT bearer**: decoded via `jose.jwt.decode`; `JWTError` is caught inside `decode_access_token` and returns `None`, which the caller converts to 401.

Password hashing uses `bcrypt`; token decoding catches `JWTError` specifically rather than broad `Exception`.

## Database Session Cleanup (`backend/app/database.py`)

`get_db()` is a generator dependency using `try/finally` to ensure `db.close()` runs even if the handler raises. This is the only place where session-level cleanup is explicitly guarded.

## Frontend Error Handling (`platform-app/src/lib/api.ts`)

All API calls go through a single `request<T>()` function:

1. Attaches `Authorization: Bearer <token>` from `localStorage('finshield_token')`.
2. Calls `fetch` against `/api/*`.
3. If `!res.ok`, reads the body once, tries to parse it as JSON, falls back to raw text, then throws `new ApiError(res.status, errorDetail)`.
4. On success, returns `res.json()`.

`ApiError` extends `Error` and exposes a `status: number` property plus `name = 'ApiError'`, enabling callers to distinguish network/server errors from other JS exceptions. The frontend does not have its own retry or fallback logic — it propagates `ApiError` upward to page components, which render user-facing messages based on the status code.

## Tests as Enforcement Surface

`backend/tests/test_api.py` asserts expected status codes for error paths, effectively enforcing the contract:

- Unauthenticated access → `401`.
- Invalid Pydantic input → `422`.
- Duplicate registration → `400`.
- Wrong password → `401`.
- Nonexistent case/transaction → `404`.
- Unknown billing plan → `400`.
- Idempotent replay → `200` (not `500`).

These assertions act as the de facto specification for which status codes routes must return.

## Conventions Observed

- Backend business errors are expressed as `fastapi.HTTPException` with a plain-text `detail` string; there is no shared error-code enum or structured error envelope beyond what FastAPI produces.
- Validation errors are delegated to Pydantic + FastAPI's built-in `RequestValidationError` handler, which returns `422` with the full `exc.errors()` list.
- Global unhandled exceptions are caught and logged with `exc_info=True`, but the response body deliberately omits stack traces from clients.
- Optional services (RAG) fail open: initialization and runtime failures are logged and ignored so the core screening pipeline remains available.
- Frontend errors are uniformly wrapped in `ApiError` with the original HTTP status preserved, allowing UI layers to branch on `error.status`.
- No custom sentinel error types exist on the backend; no `try/except` blocks wrap entire route handlers — errors are raised at the failing boundary.
- Rate limiting is enforced by `slowapi` and translated to `429` by a dedicated handler.