"""FinShield AI — Behavioral baselines and scoring."""
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config_service
from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    AccountBaseline,
    Transaction,
    User,
)

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
    """Score a transaction against account's behavioral baseline."""

    # Get or create baseline
    baseline = db.query(AccountBaseline).filter(
        AccountBaseline.user_id == current_user.id,
        AccountBaseline.account_id == req.account_id
    ).first()

    if not baseline:
        # Cold-start: no baseline yet
        return {
            "account_id": req.account_id,
            "anomaly_score": 0.7,  # Higher score for cold-start (more suspicious)
            "is_cold_start": True,
            "triggered": True,  # Cold-start triggers stricter threshold
            "reason": "No behavioral baseline - cold-start policy applied",
            "baseline": None,
        }

    # Calculate z-score for amount
    if baseline.std_dev_amount > 0:
        z_score = abs(req.amount - baseline.avg_amount) / baseline.std_dev_amount
    else:
        z_score = 0.0 if req.amount == baseline.avg_amount else 3.0

    # Convert z-score to anomaly score (0-1 scale)
    # z-score of 0 = anomaly 0, z-score of 3+ = anomaly 1
    anomaly_score = min(1.0, z_score / 3.0)

    # Check for unusual country
    if req.destination_country and baseline.typical_countries:
        if req.destination_country not in baseline.typical_countries:
            anomaly_score = min(1.0, anomaly_score + 0.2)

    # Check for unusual payee
    if req.receiver_name and baseline.typical_payees:
        if req.receiver_name not in baseline.typical_payees:
            anomaly_score = min(1.0, anomaly_score + 0.15)

    # Cold-start adjustment (if < 30 days history, use stricter threshold)
    is_cold_start = baseline.is_cold_start or baseline.history_days < 30
    trigger_threshold = float(config_service.get_setting(
        db, "behavioral.trigger.cold_start" if is_cold_start else "behavioral.trigger.warm"))

    triggered = anomaly_score >= trigger_threshold

    return {
        "account_id": req.account_id,
        "anomaly_score": round(anomaly_score, 3),
        "is_cold_start": is_cold_start,
        "triggered": triggered,
        "trigger_threshold": trigger_threshold,
        "reason": f"Anomaly score {anomaly_score:.3f} {'>=' if triggered else '<'} {trigger_threshold}",
        "baseline": {
            "avg_amount": baseline.avg_amount,
            "std_dev_amount": baseline.std_dev_amount,
            "history_days": baseline.history_days,
            "total_transactions": baseline.total_transactions,
        },
    }


@router.post("/api/v1/behavioral/update-baseline", tags=["Behavioral"])
def update_account_baseline(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recompute behavioral baseline for an account from transaction history."""
    # Get all transactions for this account (using sender_name as proxy for account_id)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.sender_name == account_id,  # Using sender_name as account_id proxy
    ).order_by(Transaction.created_at.asc()).all()

    if not transactions:
        raise HTTPException(404, "No transactions found for this account")

    # Get or create baseline
    baseline = db.query(AccountBaseline).filter(
        AccountBaseline.user_id == current_user.id,
        AccountBaseline.account_id == account_id
    ).first()

    if not baseline:
        baseline = AccountBaseline(
            user_id=current_user.id,
            account_id=account_id,
        )
        db.add(baseline)

    # Compute statistics
    amounts = [tx.amount for tx in transactions]
    avg_amount = sum(amounts) / len(amounts)

    # Standard deviation
    if len(amounts) > 1:
        variance = sum((x - avg_amount) ** 2 for x in amounts) / (len(amounts) - 1)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0

    # Typical patterns
    countries = [tx.destination_country for tx in transactions if tx.destination_country]
    country_counts = {}
    for c in countries:
        country_counts[c] = country_counts.get(c, 0) + 1
    typical_countries = [c for c, count in country_counts.items() if count >= len(transactions) * 0.1]

    payees = [tx.receiver_name for tx in transactions if tx.receiver_name]
    payee_counts = {}
    for p in payees:
        payee_counts[p] = payee_counts.get(p, 0) + 1
    typical_payees = [p for p, count in payee_counts.items() if count >= len(transactions) * 0.1]

    tx_types = [tx.transaction_type for tx in transactions if tx.transaction_type]
    type_counts = {}
    for t in tx_types:
        type_counts[t] = type_counts.get(t, 0) + 1
    typical_tx_types = [t for t, count in type_counts.items() if count >= len(transactions) * 0.1]

    # Update baseline
    baseline.avg_amount = avg_amount
    baseline.std_dev_amount = std_dev
    baseline.max_amount = max(amounts)
    baseline.min_amount = min(amounts)
    baseline.total_transactions = len(transactions)
    baseline.first_transaction_at = transactions[0].created_at
    baseline.last_transaction_at = transactions[-1].created_at
    baseline.history_days = (transactions[-1].created_at - transactions[0].created_at).days
    baseline.typical_countries = typical_countries
    baseline.typical_payees = typical_payees
    baseline.typical_tx_types = typical_tx_types
    baseline.is_cold_start = baseline.history_days < 30
    baseline.last_computed_at = datetime.utcnow()

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
        AccountBaseline.user_id == current_user.id,
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
