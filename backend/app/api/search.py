"""FinShield AI — Global search."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    ApiKey,
    Case,
    Transaction,
    User,
)

router = APIRouter()


# ============================================================
# SEARCH
# ============================================================

@router.get("/api/v1/search", tags=["Search"])
def global_search(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Global search across transactions, cases, and API keys."""
    if not q or len(q.strip()) < 2:
        return {"query": q, "transactions": [], "cases": [], "api_keys": []}

    pattern = f"%{q.strip()}%"

    # Search transactions (parties, id, country, type, status)
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.tenant_id == current_user.tenant_id,
            (Transaction.sender_name.ilike(pattern))
            | (Transaction.receiver_name.ilike(pattern))
            | (Transaction.id.ilike(pattern))
            | (Transaction.destination_country.ilike(pattern))
            | (Transaction.transaction_type.ilike(pattern))
            | (Transaction.status.ilike(pattern))
            | (Transaction.currency.ilike(pattern))
        )
        .order_by(Transaction.created_at.desc())
        .limit(10)
        .all()
    )

    # Search cases
    cases = (
        db.query(Case)
        .filter(
            Case.tenant_id == current_user.tenant_id,
            (Case.id.ilike(pattern))
            | (Case.reason.ilike(pattern))
            | (Case.transaction_id.ilike(pattern))
            | (Case.assigned_to.ilike(pattern))
        )
        .order_by(Case.created_at.desc())
        .limit(10)
        .all()
    )

    # Search API keys
    keys = (
        db.query(ApiKey)
        .filter(
            ApiKey.user_id == current_user.id,
            ApiKey.name.ilike(pattern),
            ApiKey.is_active == True,
        )
        .limit(5)
        .all()
    )

    return {
        "query": q,
        "transactions": [
            {"id": t.id, "amount": t.amount, "currency": t.currency, "sender": t.sender_name, "receiver": t.receiver_name, "status": t.status, "created_at": t.created_at.isoformat()}
            for t in txs
        ],
        "cases": [
            {"case_id": c.id, "reason": c.reason, "status": c.status, "priority": c.priority, "created_at": c.created_at.isoformat()}
            for c in cases
        ],
        "api_keys": [
            {"id": k.id, "name": k.name, "key_prefix": k.key_prefix, "is_active": k.is_active}
            for k in keys
        ],
    }
