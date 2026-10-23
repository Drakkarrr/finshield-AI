"""FinShield AI — Circuit breaker state (S2.6). Breakers are driven by real calls, not by clients."""
from fastapi import APIRouter, Depends, HTTPException

from app import resilience
from app.auth import get_current_user
from app.db_models import User

router = APIRouter()

HEALTH_MESSAGES = {
    "green": "All systems operational",
    "yellow": "Degraded mode active - affected decisions are routed to human review",
    "red": "Critical degradation - transactions routing to human review",
}


def _breakers() -> list[dict]:
    known = resilience.states()
    return [{"dependency": dep, **known.get(dep, {"state": "closed", "failure_count": 0,
                                                 "last_state_change_at": None})}
            for dep in resilience.DEPENDENCIES]


@router.get("/api/v1/health/circuit-breakers", tags=["System"])
def get_circuit_breaker_status(current_user: User = Depends(get_current_user)):
    """Live state of the breaker around each real dependency."""
    return {"breakers": _breakers()}


@router.get("/api/v1/health/overall", tags=["System"])
def get_overall_health_status(current_user: User = Depends(get_current_user)):
    """Overall degradation level for the dashboard."""
    breakers = _breakers()
    open_count = sum(1 for b in breakers if b["state"] == "open")
    health = "red" if open_count >= 2 else "yellow" if open_count or any(
        b["state"] == "half_open" for b in breakers) else "green"
    return {
        "health": health,
        "message": HEALTH_MESSAGES[health],
        "breakers_summary": {s: sum(1 for b in breakers if b["state"] == s) for s in ("closed", "half_open", "open")},
    }


# TODO(S3.1): require_role("admin")
@router.post("/api/v1/health/circuit-breakers/{dependency}/reset", tags=["System"])
def reset_circuit_breaker(dependency: str, current_user: User = Depends(get_current_user)):
    """Manually close a breaker after an incident is resolved (audited in S3.1/S3.2)."""
    if dependency not in resilience.DEPENDENCIES:
        raise HTTPException(status_code=404, detail=f"Unknown dependency: {dependency}")
    resilience.reset(dependency)
    return {"dependency": dependency, "state": "closed"}
