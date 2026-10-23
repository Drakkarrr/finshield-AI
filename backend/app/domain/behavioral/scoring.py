"""Behavioral scoring domain logic (S2.1).

Extracted from api/behavioral.py so the compliance engine can call it
directly during screening, not just via the HTTP endpoint.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import AccountBaseline


@dataclass
class BehavioralResult:
    """Result of behavioral scoring."""
    anomaly_score: float
    is_cold_start: bool
    triggered: bool
    trigger_threshold: float
    reasons: list[str] = field(default_factory=list)
    baseline: Optional[dict] = None


def score_behavioral(
    db: Session,
    user_id: str,
    account_id: str,
    amount: float,
    transaction_type: str,
    destination_country: Optional[str] = None,
    receiver_name: Optional[str] = None,
    cold_start_threshold: float = 0.5,
    warm_threshold: float = 0.7,
) -> BehavioralResult:
    """Score a transaction against the account's behavioral baseline.

    Returns a BehavioralResult with anomaly_score, reasons[], and baseline info.
    If no baseline exists, returns cold-start result with higher suspicion.
    """
    reasons: list[str] = []

    baseline = db.query(AccountBaseline).filter(
        AccountBaseline.user_id == user_id,
        AccountBaseline.account_id == account_id,
    ).first()

    if not baseline:
        return BehavioralResult(
            anomaly_score=cold_start_threshold,
            is_cold_start=True,
            triggered=True,
            trigger_threshold=cold_start_threshold,
            reasons=["No behavioral baseline — cold-start policy applied"],
            baseline=None,
        )

    anomaly_score = 0.0

    # Z-score for amount
    if baseline.std_dev_amount > 0:
        z_score = abs(amount - baseline.avg_amount) / baseline.std_dev_amount
    else:
        z_score = 0.0 if amount == baseline.avg_amount else 3.0

    amount_anomaly = min(1.0, z_score / 3.0)
    anomaly_score += amount_anomaly
    if amount_anomaly > 0.3:
        reasons.append(f"Amount z-score {z_score:.2f} (anomaly {amount_anomaly:.2f})")

    # Unusual country
    if destination_country and baseline.typical_countries:
        if destination_country not in baseline.typical_countries:
            anomaly_score += 0.2
            reasons.append(f"Unusual destination country: {destination_country}")

    # Unusual payee
    if receiver_name and baseline.typical_payees:
        if receiver_name not in baseline.typical_payees:
            anomaly_score += 0.15
            reasons.append(f"Unusual payee: {receiver_name}")

    anomaly_score = min(1.0, anomaly_score)

    # Cold-start adjustment
    is_cold_start = baseline.is_cold_start or baseline.history_days < 30
    trigger_threshold = cold_start_threshold if is_cold_start else warm_threshold
    triggered = anomaly_score >= trigger_threshold

    if is_cold_start:
        reasons.append(f"Cold-start account ({baseline.history_days}d history)")

    return BehavioralResult(
        anomaly_score=round(anomaly_score, 4),
        is_cold_start=is_cold_start,
        triggered=triggered,
        trigger_threshold=trigger_threshold,
        reasons=reasons,
        baseline={
            "avg_amount": baseline.avg_amount,
            "std_dev_amount": baseline.std_dev_amount,
            "history_days": baseline.history_days,
            "total_transactions": baseline.total_transactions,
        },
    )
