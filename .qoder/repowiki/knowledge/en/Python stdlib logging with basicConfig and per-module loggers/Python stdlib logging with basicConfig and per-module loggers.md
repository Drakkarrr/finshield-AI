---
kind: logging_system
name: Python stdlib logging with basicConfig and per-module loggers
category: logging_system
scope:
    - '**'
source_files:
    - backend/app/main.py
    - backend/app/rag_service.py
---

## What system/approach is used

The FinShield backend uses Python's built-in `logging` module (no third-party logger framework). There is no structured-logging library, no JSON formatter, no centralized sink configuration — just `logging.basicConfig` at application startup and a module-level `logger = logging.getLogger(...)` in each consumer.

The Next.js platform-app (`platform-app/`) has no logging framework installed or used; the only JS-side output is the default browser console via `console.log`, which is not part of an application logging system. The static website (`website/`) is pure HTML/CSS/JS served by nginx and contains no server-side logging.

## Key files and packages

- `backend/app/main.py` — defines the root `finshield` logger and configures `basicConfig` (lines 47–51).
- `backend/app/rag_service.py` — creates its own module logger via `logging.getLogger(__name__)` (line 27) and logs RAG lifecycle events.
- Other backend modules (`auth.py`, `compliance_engine.py`, `database.py`, `db_models.py`, `models.py`, `seed_rag_data.py`) do not import or configure logging directly; they rely on the root logger configured in `main.py`.

## Architecture and conventions

### Initialization

At module load time, `main.py` calls:

```python
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finshield")
```

This sets up a single `StreamHandler` writing to stderr with a plain-text format containing timestamp, level, logger name, and message. The effective log level is controlled by the `DEBUG` environment variable: `DEBUG=true` enables `DEBUG`; otherwise `INFO`.

### Logger naming

- The application-wide logger is named `finshield` and is obtained once as `logger = logging.getLogger("finshield")` in `main.py`.
- The RAG service obtains a child logger via `logging.getLogger(__name__)`, which resolves to `app.rag_service` under the `finshield` hierarchy.
- No other module imports `logging` or creates its own logger instance.

### Log levels observed

| Level | Usage pattern | Example locations |
|-------|---------------|-------------------|
| `info` | Normal operational milestones: DB init, RAG init, user registration/login, API key creation/revocation, case creation, transaction screening results. | `main.py`: lines 136, 144, 149, 152, 219, 253, 384, 426, 565–568, 764; `rag_service.py`: lines 40, 155, 188, 222, 251 |
| `warning` | Recoverable or degraded conditions: rate limiting, validation errors, RAG enrichment failure, optional dependency fallback. | `main.py`: lines 84, 102, 146, 505; `rag_service.py`: line 42 |
| `error` | Unhandled exceptions with full traceback (`exc_info=True`). | `main.py`: line 111 |
| `debug` | Per-request HTTP method/path/status/duration inside the `request_logging_middleware`. | `main.py`: line 124 |

### Exception handling integration

Four FastAPI exception handlers centralize error logging:

- `RateLimitExceeded` → `logger.warning` with client host.
- `HTTPException` → `logger.info` with status code, method, path, detail.
- `RequestValidationError` → `logger.warning` with method, path, Pydantic errors.
- Catch-all `Exception` → `logger.error` with `exc_info=True` for full stack traces.

### Middleware request logging

A FastAPI `@app.middleware("http")` wraps every request, measures elapsed time via `time.monotonic()`, emits a `DEBUG`-level log entry with method, path, status code, and duration in milliseconds, and injects an `X-Process-Time-Ms` response header.

### Sinks and routing

There is no custom handler, file sink, syslog sink, or external log aggregation SDK. All output goes through the default `StreamHandler` attached by `basicConfig`, which writes to `stderr`. Structured fields are not emitted as JSON; instead, contextual data (user email, risk score, credit tier, etc.) is interpolated into the message string.

## Conventions and constraints

- **Single initialization point**: `logging.basicConfig` is called exactly once in `backend/app/main.py` before any route handlers run. This is enforced by the fact that `main.py` is the FastAPI application entrypoint imported by the Dockerfile/uvicorn command.
- **Level selection via env var**: The effective log level is determined by `os.getenv("DEBUG") == "true"`; all other values fall back to `INFO`. There is no `LOG_LEVEL` setting.
- **Format is fixed**: Every log line follows `%(asctime)s [%(levelname)s] %(name)s: %(message)s`. No custom formatter is registered.
- **Logger instances are module-scoped**: Each consumer either reuses the `finshield` logger from `main.py` or creates one via `logging.getLogger(__name__)` (only `rag_service.py` does this).
- **No structured logging**: Fields such as `user_id`, `transaction_id`, `risk_score`, and `status` are embedded as interpolated strings rather than emitted as structured key/value pairs.
- **Tracebacks only for unhandled exceptions**: Only the global `Exception` handler passes `exc_info=True`; other error paths log messages without stack traces.
- **Frontend has no application logging**: The Next.js app does not install or configure a logging library; it relies on the browser console, which is outside the scope of the backend logging system.