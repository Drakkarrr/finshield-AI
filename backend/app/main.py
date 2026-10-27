"""
FinShield AI — FastAPI application: app setup, middleware, startup and router registration.
Routes live in app/api/ (one module per domain); shared singletons in app/core.py.
"""
import os
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from dotenv import load_dotenv
from opentelemetry.trace import SpanKind

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app import crypto, metrics, observability
from app.api import (
    admin,
    audit,
    auth,
    behavioral,
    billing,
    breakers,
    cases,
    change_requests,
    filings,
    health,
    keys,
    lists,
    models,
    notifications,
    privacy,
    rag,
    rules,
    search,
    settings,
    stats,
    transactions,
    webhooks,
)
from app.core import limiter, logger
from app.domain.rag.embedders import load_embedder
from app.domain.rag.service import RAGRetrievalService
from app.permissions import authorize


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="FinShield AI",
    description="Transaction Compliance Engine — Production API with auth, DB, and rate limiting",
    version="2.4.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",  # under /api so the web app's proxy serves it (docs page)
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)
app.state.limiter = limiter


# --- Exception Handlers ---
# Starlette types handlers as (Request, Exception); each is registered for one exception class.
async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    client = request.client.host if request.client else "unknown"
    logger.warning(f"Rate limit exceeded: {request.method} {request.url.path} from {client}")
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    logger.info(f"HTTP {exc.status_code}: {request.method} {request.url.path} — {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    logger.warning(f"Validation error: {request.method} {request.url.path} — {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request data", "errors": exc.errors()},
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    observability.capture_exception(exc)
    if request.method == "POST" and request.url.path == "/api/v1/transactions":
        metrics.PIPELINE_ERRORS.inc()
    logger.error(f"Unhandled exception: {request.method} {request.url.path} — {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# --- Middleware ---
# Security headers (S6.2). The API serves JSON, so its CSP forbids everything; the interactive docs
# pages load Swagger/ReDoc assets from a CDN and keep the framework default instead. HSTS is sent
# only over HTTPS (behind a TLS proxy uvicorn trusts X-Forwarded-Proto from FORWARDED_ALLOW_IPS)
# or when HSTS_ENABLED=true. The web app sets its own headers in platform-app/next.config.js.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_PATHS = ("/api/docs", "/api/redoc")
HSTS = "max-age=31536000; includeSubDomains"


def _security_headers(request: Request, response) -> None:
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    path = request.url.path
    if not path.startswith(DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", API_CSP)
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if request.url.scheme == "https" or os.getenv("HSTS_ENABLED", "false").lower() == "true":
        response.headers.setdefault("Strict-Transport-Security", HSTS)


async def request_logging_middleware(request: Request, call_next):
    """Request id (propagated or new), root span, HTTP metrics by route template."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.monotonic()
    status = 500  # an exception escaping call_next is answered as 500 by the outermost handler
    with observability.tracer.start_as_current_span(f"HTTP {request.method}", kind=SpanKind.SERVER) as span:
        span.set_attribute("http.request_id", request_id)
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            span.update_name(f"{request.method} {route}")
            span.set_attribute("http.route", route)
            span.set_attribute("http.status_code", status)
            elapsed = time.monotonic() - start
            metrics.HTTP_REQUESTS.labels(method=request.method, route=route, status=str(status)).inc()
            metrics.HTTP_LATENCY.labels(method=request.method, route=route).observe(elapsed)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(round(elapsed * 1000, 2))
    _security_headers(request, response)
    return response


def check_payments_config() -> None:
    """Refuse to run production with simulated payments (credits without payment) unless the
    operator opted in explicitly with ALLOW_SIMULATED_PAYMENTS=true (local compose does)."""
    if (os.getenv("APP_ENV", "production").lower() == "production"
            and os.getenv("PAYMENTS_MODE", "simulated").lower() == "simulated"
            and os.getenv("ALLOW_SIMULATED_PAYMENTS", "false").lower() != "true"):
        raise RuntimeError("Refusing to start: APP_ENV=production with PAYMENTS_MODE=simulated. "
                           "Set PAYMENTS_MODE=stripe, or ALLOW_SIMULATED_PAYMENTS=true for local development only.")


# --- Startup ---
async def startup():  # run by lifespan()
    # Schema is managed by Alembic (`alembic upgrade head` runs in the container entrypoint).
    crypto.public_key_pem()  # fail fast: DATA_ENCRYPTION_KEY is required outside tests

    check_payments_config()  # S7.5: no free credits in production by accident

    # RAG is optional: without RAG_DATABASE_URL decisions report rag_status="disabled".
    rag_database_url = os.getenv("RAG_DATABASE_URL", "")
    app.state.rag_service = None
    if rag_database_url.startswith("postgresql"):
        try:
            app.state.rag_service = RAGRetrievalService(rag_database_url, load_embedder())
            logger.info("RAG retrieval enabled (embedder %s)", app.state.rag_service.embedder.name)
        except Exception as e:
            logger.warning("RAG disabled: service failed to initialise (%s)", e)
    else:
        logger.warning("RAG disabled: RAG_DATABASE_URL is not a postgresql:// URL; decisions report rag_status=disabled")

    logger.info(f"FinShield AI v2.4.0 started on port {os.getenv('APP_PORT', '8091')}")


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.middleware("http")(request_logging_middleware)

# Registration order is route-matching order; it follows the original main.py section order.
# Every router except auth (register/login/self-profile), provider callbacks and health runs the RBAC check.
app.include_router(auth.router)
for _module in (keys, transactions, cases, billing, stats, search, notifications, rules, filings, behavioral,
                breakers, webhooks, privacy, rag, settings, lists, models, change_requests, admin, audit):
    app.include_router(_module.router, dependencies=[Depends(authorize)])
app.include_router(billing.provider_router)  # signature-authenticated provider callbacks
app.include_router(health.router)
