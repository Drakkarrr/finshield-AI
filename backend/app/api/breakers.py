"""FinShield AI — Circuit breaker state."""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    AuditLog,
    CircuitBreaker,
    User,
)

router = APIRouter()


# ============================================================
# CIRCUIT BREAKER & DEGRADED MODE
# ============================================================

def get_or_create_breaker(db: Session, dependency: str) -> CircuitBreaker:
    """Get or create circuit breaker for a dependency."""
    breaker = db.query(CircuitBreaker).filter(CircuitBreaker.dependency == dependency).first()
    if not breaker:
        breaker = CircuitBreaker(dependency=dependency)
        db.add(breaker)
        db.commit()
        db.refresh(breaker)
    return breaker


@router.get("/api/v1/health/circuit-breakers", tags=["System"])
def get_circuit_breaker_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get circuit breaker status for all dependencies."""
    breakers = db.query(CircuitBreaker).all()

    # Ensure all critical dependencies have breakers
    critical_deps = ["model_server", "pgvector", "redis", "notification_service"]
    for dep in critical_deps:
        if not any(b.dependency == dep for b in breakers):
            breaker = get_or_create_breaker(db, dep)
            breakers.append(breaker)

    return {
        "breakers": [
            {
                "dependency": b.dependency,
                "state": b.state,
                "failure_count": b.failure_count,
                "success_count": b.success_count,
                "last_failure_at": b.last_failure_at.isoformat() if b.last_failure_at else None,
                "last_state_change_at": b.last_state_change_at.isoformat() if b.last_state_change_at else None,
                "failure_threshold": b.failure_threshold,
                "cooldown_seconds": b.cooldown_seconds,
            }
            for b in breakers
        ],
        "overall_health": get_overall_health(breakers),
    }


def get_overall_health(breakers: list) -> str:
    """Determine overall system health from circuit breakers."""
    if not breakers:
        return "green"

    states = [b.state for b in breakers]

    if any(s == "open" for s in states):
        return "red"  # Critical degradation
    elif any(s == "half_open" for s in states):
        return "yellow"  # Degraded mode
    else:
        return "green"  # All healthy


@router.post("/api/v1/health/circuit-breakers/{dependency}/record-failure", tags=["System"])
def record_circuit_breaker_failure(
    dependency: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a failure for a circuit breaker."""
    breaker = get_or_create_breaker(db, dependency)

    now = datetime.utcnow()
    breaker.failure_count += 1
    breaker.last_failure_at = now

    # Check if we should open the circuit
    if breaker.state == "closed" and breaker.failure_count >= breaker.failure_threshold:
        breaker.state = "open"
        breaker.last_state_change_at = now
        # Audit log
        db.add(AuditLog(
            user_id=current_user.id,
            action="circuit_breaker_opened",
            resource_type="circuit_breaker",
            resource_id=breaker.id,
            details={"dependency": dependency, "failure_count": breaker.failure_count},
        ))
    elif breaker.state == "half_open":
        # Failure in half-open -> reopen
        breaker.state = "open"
        breaker.last_state_change_at = now
        breaker.failure_count = 1  # Reset counter

    db.commit()

    return {
        "dependency": dependency,
        "state": breaker.state,
        "failure_count": breaker.failure_count,
    }


@router.post("/api/v1/health/circuit-breakers/{dependency}/record-success", tags=["System"])
def record_circuit_breaker_success(
    dependency: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a success for a circuit breaker."""
    breaker = get_or_create_breaker(db, dependency)

    now = datetime.utcnow()
    breaker.success_count += 1

    # Check if we should close the circuit
    if breaker.state == "half_open":
        breaker.success_count += 1
        if breaker.success_count >= breaker.half_open_max_calls:
            breaker.state = "closed"
            breaker.failure_count = 0
            breaker.success_count = 0
            breaker.last_state_change_at = now
            # Audit log
            db.add(AuditLog(
                user_id=current_user.id,
                action="circuit_breaker_closed",
                resource_type="circuit_breaker",
                resource_id=breaker.id,
                details={"dependency": dependency},
            ))
    elif breaker.state == "closed":
        # Reset failure count on success
        breaker.failure_count = max(0, breaker.failure_count - 1)

    db.commit()

    return {
        "dependency": dependency,
        "state": breaker.state,
        "success_count": breaker.success_count,
    }


@router.post("/api/v1/health/circuit-breakers/{dependency}/check-half-open", tags=["System"])
def check_half_open_transition(
    dependency: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if an open circuit breaker should transition to half-open."""
    breaker = get_or_create_breaker(db, dependency)

    if breaker.state != "open":
        return {"dependency": dependency, "state": breaker.state, "transitioned": False}

    now = datetime.utcnow()
    if breaker.last_state_change_at:
        elapsed = (now - breaker.last_state_change_at).total_seconds()
        if elapsed >= breaker.cooldown_seconds:
            breaker.state = "half_open"
            breaker.success_count = 0
            breaker.last_state_change_at = now
            db.commit()

            # Audit log
            db.add(AuditLog(
                user_id=current_user.id,
                action="circuit_breaker_half_open",
                resource_type="circuit_breaker",
                resource_id=breaker.id,
                details={"dependency": dependency, "cooldown_elapsed": elapsed},
            ))
            db.commit()

            return {"dependency": dependency, "state": "half_open", "transitioned": True}

    return {"dependency": dependency, "state": breaker.state, "transitioned": False}


@router.get("/api/v1/health/overall", tags=["System"])
def get_overall_health_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get overall system health status for dashboard."""
    breakers = db.query(CircuitBreaker).all()

    # Ensure all critical dependencies have breakers
    critical_deps = ["model_server", "pgvector", "redis", "notification_service"]
    for dep in critical_deps:
        if not any(b.dependency == dep for b in breakers):
            breaker = get_or_create_breaker(db, dep)
            breakers.append(breaker)

    health = get_overall_health(breakers)

    health_messages = {
        "green": "All systems operational",
        "yellow": "Degraded mode active - some dependencies unavailable",
        "red": "Critical degradation - transactions routing to human review",
    }

    return {
        "health": health,
        "message": health_messages.get(health, "Unknown"),
        "breakers_summary": {
            "closed": sum(1 for b in breakers if b.state == "closed"),
            "half_open": sum(1 for b in breakers if b.state == "half_open"),
            "open": sum(1 for b in breakers if b.state == "open"),
        },
    }
