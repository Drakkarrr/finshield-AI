"""FinShield AI — Liveness, readiness, health and service root."""
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import logger, start_time
from app.database import get_db
from app.models import (
    HealthResponse,
)
from app.observability import get_metrics

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


@router.get("/api/health/live", tags=["System"])
def liveness_probe():
    """Liveness probe — 200 while the process is up. Deliberately checks no dependencies."""
    return {"status": "alive"}


@router.get("/api/health/ready", tags=["System"])
def readiness_probe(request: Request, db: Session = Depends(get_db)):
    """Readiness probe — 503 with a per-dependency body when any probe fails."""
    services, all_ok = _probe_dependencies(request, db)
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
    """System health: same shape as before, but every service entry is a real probe result."""
    services, all_ok = _probe_dependencies(request, db)
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


@router.get("/api/health/worker", tags=["System"])
def worker_health():
    """Worker health check — verifies Celery worker is responsive (S4.1)."""
    try:
        from app.worker import celery_app
        
        # Ping worker with health_check task
        result = celery_app.send_task("app.worker.tasks.health_check")
        response = result.get(timeout=5.0)
        
        return {
            "status": "healthy",
            "worker": response.get("worker", "unknown"),
            "timestamp": response.get("timestamp"),
        }
    except Exception as e:
        logger.exception("worker_health_check_failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            },
        )


@router.get("/metrics", tags=["System"])
def prometheus_metrics():
    """Prometheus metrics endpoint (S4.4)."""
    metrics_text, content_type = get_metrics()
    return Response(content=metrics_text, media_type=content_type)
