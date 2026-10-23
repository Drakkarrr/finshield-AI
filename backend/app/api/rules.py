"""FinShield AI — Hard-rule configuration, simulation and hit reporting."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.core import engine
from app.database import get_db
from app.db_models import (
    AuditLog,
    RuleConfig,
    Transaction,
    User,
)

router = APIRouter()


# ============================================================
# RULE MANAGEMENT
# ============================================================

class RuleUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    custom_parameters: Optional[dict] = None


@router.patch("/api/v1/rules/{rule_id}", tags=["Rules"])
def update_rule(
    rule_id: str,
    req: RuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle or customize a compliance rule for the current user."""
    # Verify rule exists
    definitions = engine.rule_definitions()
    rule_def = next((r for r in definitions if r["rule_id"] == rule_id), None)
    if not rule_def:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Get or create user-specific config
    config = db.query(RuleConfig).filter(
        RuleConfig.user_id == current_user.id, RuleConfig.rule_id == rule_id
    ).first()
    if not config:
        config = RuleConfig(user_id=current_user.id, rule_id=rule_id)
        db.add(config)

    if req.enabled is not None:
        config.enabled = req.enabled
    if req.custom_parameters is not None:
        config.custom_parameters = req.custom_parameters

    db.commit()
    db.refresh(config)

    audit = AuditLog(user_id=current_user.id, action="rule_updated",
                     resource_type="rule", resource_id=rule_id,
                     details={"enabled": config.enabled, "custom_parameters": config.custom_parameters})
    db.add(audit)
    db.commit()

    return {
        "rule_id": rule_id,
        "enabled": config.enabled,
        "custom_parameters": config.custom_parameters,
        "detail": f"Rule {rule_id} updated",
    }


@router.get("/api/v1/rules", tags=["Rules"])
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List rules with user-specific overrides applied."""
    definitions = engine.rule_definitions()
    # Apply user-specific overrides
    user_configs = db.query(RuleConfig).filter(RuleConfig.user_id == current_user.id).all()
    config_map = {c.rule_id: c for c in user_configs}

    for rule in definitions:
        config = config_map.get(rule["rule_id"])
        if config:
            rule["enabled"] = config.enabled
            # is_customized only when parameters were actually changed (not just an on/off toggle)
            if config.custom_parameters:
                rule["parameters"] = {**rule["parameters"], **config.custom_parameters}
                rule["is_customized"] = True
            else:
                rule["is_customized"] = False
        else:
            rule["is_customized"] = False

    return definitions


# Rule Simulation
class RuleSimulateRequest(BaseModel):
    rule_id: str
    days: int = 30  # Simulate against last N days of transactions


@router.post("/api/v1/rules/simulate", tags=["Rules"])
def simulate_rule(
    req: RuleSimulateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulate a rule against historical transaction data."""
    # Get rule definition
    definitions = engine.rule_definitions()
    rule_def = next((r for r in definitions if r["rule_id"] == req.rule_id), None)
    if not rule_def:
        raise HTTPException(404, "Rule not found")

    # Get transactions from last N days
    cutoff = datetime.utcnow() - timedelta(days=req.days)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.created_at >= cutoff
    ).all()

    # Simulate rule against each transaction
    triggered_count = 0
    would_block = 0
    would_flag = 0

    for tx in transactions:
        # Run rule evaluation
        tx_data = {
            "amount": tx.amount,
            "currency": tx.currency,
            "transaction_type": tx.transaction_type,
            "sender_name": tx.sender_name,
            "receiver_name": tx.receiver_name,
            "destination_country": tx.destination_country,
            "description": tx.description,
        }

        result = engine.evaluate_rule(rule_def, tx_data)
        if result["triggered"]:
            triggered_count += 1
            if rule_def["action"] == "block":
                would_block += 1
            elif rule_def["action"] == "flag":
                would_flag += 1

    return {
        "rule_id": req.rule_id,
        "rule_name": rule_def["name"],
        "days_simulated": req.days,
        "transactions_tested": len(transactions),
        "triggered_count": triggered_count,
        "would_block": would_block,
        "would_flag": would_flag,
        "trigger_rate": round(triggered_count / max(1, len(transactions)) * 100, 2),
    }


# Rule Hit Reporting
@router.get("/api/v1/rules/{rule_id}/stats", tags=["Rules"])
def get_rule_stats(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get hit statistics for a specific rule."""
    config = db.query(RuleConfig).filter(
        RuleConfig.rule_id == rule_id,
        RuleConfig.user_id == current_user.id
    ).first()

    if not config:
        # Return default stats if no config exists
        return {
            "rule_id": rule_id,
            "hit_count": 0,
            "false_positive_count": 0,
            "last_hit_at": None,
            "false_positive_rate": 0.0,
        }

    fp_rate = 0.0
    if config.hit_count > 0:
        fp_rate = round(config.false_positive_count / config.hit_count * 100, 2)

    return {
        "rule_id": rule_id,
        "hit_count": config.hit_count,
        "false_positive_count": config.false_positive_count,
        "last_hit_at": config.last_hit_at.isoformat() if config.last_hit_at else None,
        "false_positive_rate": fp_rate,
    }


@router.post("/api/v1/rules/{rule_id}/record-hit", tags=["Rules"])
def record_rule_hit(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a rule hit (called by compliance engine)."""
    config = db.query(RuleConfig).filter(
        RuleConfig.rule_id == rule_id,
        RuleConfig.user_id == current_user.id
    ).first()

    if not config:
        # Create config if it doesn't exist
        config = RuleConfig(
            user_id=current_user.id,
            rule_id=rule_id,
            hit_count=1,
            last_hit_at=datetime.utcnow(),
        )
        db.add(config)
    else:
        config.hit_count += 1
        config.last_hit_at = datetime.utcnow()

    db.commit()
    return {"recorded": True, "hit_count": config.hit_count}


@router.post("/api/v1/rules/{rule_id}/record-false-positive", tags=["Rules"])
def record_false_positive(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a false positive for a rule."""
    config = db.query(RuleConfig).filter(
        RuleConfig.rule_id == rule_id,
        RuleConfig.user_id == current_user.id
    ).first()

    if not config:
        raise HTTPException(404, "Rule config not found")

    config.false_positive_count += 1
    db.commit()

    return {"recorded": True, "false_positive_count": config.false_positive_count}
