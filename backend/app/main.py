"""
FinShield AI — FastAPI application: app setup, middleware, startup and router registration.
Routes live in app/api/ (one module per domain); shared singletons in app/core.py.
"""
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api import (
    admin,
    auth,
    behavioral,
    billing,
    breakers,
    cases,
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
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    logger.error(f"Unhandled exception: {request.method} {request.url.path} — {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# --- Middleware ---
async def request_logging_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)
    logger.debug(f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)")
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


# --- Startup ---
async def startup():  # run by lifespan()
    # Schema is managed by Alembic (`alembic upgrade head` runs in the container entrypoint).

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
# Every router except auth (register/login/self-profile) and health runs the RBAC check.
app.include_router(auth.router)
for _module in (keys, transactions, cases, billing, stats, search, notifications, rules, filings, behavioral,
                breakers, webhooks, privacy, rag, settings, lists, models, admin):
    app.include_router(_module.router, dependencies=[Depends(authorize)])
app.include_router(health.router)
