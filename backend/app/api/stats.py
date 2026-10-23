"""FinShield AI — Dashboard statistics."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    Case,
    Transaction,
    User,
)

router = APIRouter()


# ============================================================
# ANALYTICS / STATS
# ============================================================

@router.get("/api/v1/stats", tags=["Analytics"])
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate dashboard metrics computed from the user's real data."""
    base = db.query(Transaction).filter(Transaction.tenant_id == current_user.tenant_id)
    total = base.count()
    blocked = base.filter(Transaction.status == "blocked").count()
    flagged = base.filter(Transaction.status == "flagged").count()
    in_review = base.filter(Transaction.status == "in_review").count()
    approved = base.filter(Transaction.status == "approved").count()

    open_cases = (
        db.query(Case)
        .filter(Case.tenant_id == current_user.tenant_id, Case.status.notin_(["resolved", "closed"]))
        .count()
    )

    # Average risk score across all screened transactions
    avg_risk = db.query(func.avg(Transaction.risk_score)).filter(
        Transaction.tenant_id == current_user.tenant_id
    ).scalar() or 0.0

    return {
        "total_transactions": total,
        "approved": approved,
        "flagged": flagged,
        "blocked": blocked,
        "in_review": in_review,
        "open_cases": open_cases,
        "avg_risk_score": round(float(avg_risk), 4),
        "credits_used": round(current_user.used_credits),
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
    }
