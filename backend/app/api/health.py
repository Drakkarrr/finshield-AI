"""FinShield AI — Liveness, readiness, health and service root."""
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import config_service, resilience
from app.core import logger, start_time
from app.database import get_db
from app.domain.lists import provider as lists
from app.models import (
    HealthResponse,
)

router = APIRouter()


# ============================================================
# SYSTEM ROUTES
# ============================================================

def _probe_dependencies(request: Request, db: Session) -> tuple[dict[str, str], bool]:
    """Probe real dependencies. Returns (per-dependency status, all_ok).

    Exception detail is logged, never returned: these endpoints are unauthenticated.
    """
    services: dict[str, str] = {}
    all_ok = True

    try:
        db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception:
        logger.exception("Health probe failed: database")
        services["database"] = "unavailable"
        all_ok = False

    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service is None:
        services["rag_service"] = "disabled"
    else:
        try:
            with rag_service.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            services["rag_service"] = "healthy"
        except Exception:
            logger.exception("Health probe failed: rag_service")
            services["rag_service"] = "unavailable"
            all_ok = False

    return services, all_ok


def _compliance_signals(db: Session) -> tuple[dict[str, str], bool]:
    """Whether screening is trustworthy: sanctions data present and fresh, no open breaker."""
    signals: dict[str, str] = {}
    try:
        max_age = float(config_service.get_setting(db, "lists.max_age_hours"))
        sanctions = [s for s in lists.status(db, max_age) if s["list_type"] == "sanctions"]
        signals["sanctions_list"] = ("missing" if not sanctions else
                                     "stale" if all(s["stale"] for s in sanctions) else "fresh")
    except Exception:
        logger.exception("Health probe failed: sanctions_list")
        signals["sanctions_list"] = "unavailable"
    open_breakers = sorted(dep for dep, st in resilience.states().items() if st["state"] == "open")
    signals["circuit_breakers"] = "open: " + ", ".join(open_breakers) if open_breakers else "closed"
    return signals, signals["sanctions_list"] == "fresh" and not open_breakers


@router.get("/api/health/live", tags=["System"])
def liveness_probe():
    """Liveness probe — 200 while the process is up. Deliberately checks no dependencies."""
    return {"status": "alive"}


@router.get("/api/health/ready", tags=["System"])
def readiness_probe(request: Request, db: Session = Depends(get_db)):
    """Readiness probe — 503 when a hard dependency (DB, RAG) fails. Compliance signals (list
    freshness, open breakers) are reported but do not take the instance out of rotation: it still
    serves, and the gate holds affected decisions for review."""
    services, all_ok = _probe_dependencies(request, db)
    signals, _ = _compliance_signals(db)
    services.update(signals)
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ready" if all_ok else "not_ready",
            "services": services,
            "uptime_seconds": round(time.monotonic() - start_time, 2),
        },
    )


@router.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check(request: Request, db: Session = Depends(get_db)):
    """System health for monitoring: 503 when a dependency is down, sanctions data is missing or
    stale, or a circuit breaker is open."""
    services, deps_ok = _probe_dependencies(request, db)
    signals, compliance_ok = _compliance_signals(db)
    services.update(signals)
    all_ok = deps_ok and compliance_ok
    body = HealthResponse(
        status="healthy" if all_ok else "degraded",
        version="2.4.0",
        services=services,
        uptime_seconds=round(time.monotonic() - start_time, 2),
    )
    return JSONResponse(status_code=200 if all_ok else 503, content=body.model_dump())


@router.get("/", tags=["System"])
def root():
    return {
        "service": "FinShield AI",
        "version": "2.4.0",
        "docs": "/api/docs",
        "health": "/api/health",
    }
