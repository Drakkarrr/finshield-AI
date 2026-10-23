"""FinShield AI — Behavioral baselines and scoring."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config_service, screening_service
from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    AccountBaseline,
    User,
)
from app.domain import behavioral

router = APIRouter()


# ============================================================
# BEHAVIORAL MONITORING
# ============================================================

class BehavioralScoreRequest(BaseModel):
    account_id: str
    amount: float
    transaction_type: str
    destination_country: Optional[str] = None
    receiver_name: Optional[str] = None


@router.post("/api/v1/behavioral/score", tags=["Behavioral"])
def score_transaction_behavior(
    req: BehavioralScoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Score an amount against the account's baseline: the same function screening uses."""
    now = datetime.utcnow()
    since = now - timedelta(days=screening_service.HISTORY_DAYS)
    baseline = behavioral.compute_baseline(screening_service.history(db, current_user.tenant_id, req.account_id, since))
    population = screening_service.population(db, current_user.tenant_id, since)
    cfg = config_service.screening_config(db)
    result = behavioral.score(req.amount, req.destination_country, req.receiver_name, baseline, population,
                              behavioral.BehavioralConfig(cfg.behavioral_trigger_warm, cfg.behavioral_trigger_cold_start,
                                                          cfg.cold_start_days, cfg.min_history_txs))
    return {
        "account_id": req.account_id,
        "anomaly_score": result.score,
        "z_score": result.z_score,
        "is_cold_start": result.cold_start,
        "triggered": result.triggered,
        "trigger_threshold": result.threshold,
        "reason": f"Anomaly score {result.score:.3f} {'>=' if result.triggered else '<'} {result.threshold}",
        "reasons": [r.model_dump() for r in result.reasons],
        "baseline": {
            "avg_amount": baseline.avg_amount,
            "std_dev_amount": baseline.std_dev_amount,
            "history_days": baseline.history_days,
            "total_transactions": baseline.total_transactions,
        } if baseline else None,
    }


@router.post("/api/v1/behavioral/update-baseline", tags=["Behavioral"])
def update_account_baseline(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recompute the account's baseline from its transaction history (keyed on account_id)."""
    baseline = screening_service.refresh_baseline(db, current_user.tenant_id, current_user.id, account_id)
    if baseline is None:
        raise HTTPException(404, "No transactions found for this account")
    db.commit()
    db.refresh(baseline)

    return {
        "account_id": account_id,
        "baseline_updated": True,
        "statistics": {
            "total_transactions": baseline.total_transactions,
            "history_days": baseline.history_days,
            "avg_amount": round(baseline.avg_amount, 2),
            "std_dev_amount": round(baseline.std_dev_amount, 2),
            "is_cold_start": baseline.is_cold_start,
        },
    }


@router.get("/api/v1/behavioral/baseline/{account_id}", tags=["Behavioral"])
def get_account_baseline(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral baseline for an account."""
    baseline = db.query(AccountBaseline).filter(
        AccountBaseline.tenant_id == current_user.tenant_id,
        AccountBaseline.account_id == account_id
    ).first()

    if not baseline:
        return {
            "account_id": account_id,
            "exists": False,
            "baseline": None,
        }

    return {
        "account_id": account_id,
        "exists": True,
        "baseline": {
            "avg_amount": baseline.avg_amount,
            "std_dev_amount": baseline.std_dev_amount,
            "max_amount": baseline.max_amount,
            "min_amount": baseline.min_amount,
            "total_transactions": baseline.total_transactions,
            "history_days": baseline.history_days,
            "is_cold_start": baseline.is_cold_start,
            "typical_countries": baseline.typical_countries,
            "typical_payees": baseline.typical_payees,
            "typical_tx_types": baseline.typical_tx_types,
            "last_computed_at": baseline.last_computed_at.isoformat(),
        },
    }
