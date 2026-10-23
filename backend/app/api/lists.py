"""FinShield AI — Sanctions / PEP list freshness (S2.3)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import config_service
from app.auth import get_current_user
from app.database import get_db
from app.db_models import User
from app.domain.lists import provider as lists

router = APIRouter()


@router.get("/api/v1/lists/status", tags=["Lists"])
def list_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Last import per source, its version and size, and whether it is stale."""
    max_age = float(config_service.get_setting(db, "lists.max_age_hours"))
    sources = lists.status(db, max_age)
    return {
        "max_age_hours": max_age,
        "sources": sources,
        "sanctions_loaded": any(s["list_type"] == "sanctions" for s in sources),
        "pep_loaded": any(s["list_type"] == "pep" for s in sources),
        "high_risk_countries": sorted(lists.high_risk_countries(db)),
    }
