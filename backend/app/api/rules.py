"""FinShield AI — Hard-rule configuration, simulation and hit reporting."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import config_service
from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    AuditLog,
    RuleConfig,
    Transaction,
    User,
)
from app.domain.lists import provider as lists
from app.domain.screening import rules as rule_engine

router = APIRouter()


def _definitions(db: Session) -> list[dict]:
    return rule_engine.rule_definitions(config_service.screening_config(db), lists.high_risk_countries(db),
                                        lists.snapshot(db))


# ============================================================
# RULE MANAGEMENT
# ============================================================

class RuleUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    custom_parameters: Optional[dict] = None
    priority: Optional[int] = Field(default=None, ge=0, le=10000)  # lower runs first
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


def _config_snapshot(config: RuleConfig) -> dict:
    return {
        "enabled": config.enabled,
        "custom_parameters": config.custom_parameters,
        "priority": config.priority,
        "version": config.version,
        "effective_from": config.effective_from.isoformat() if config.effective_from else None,
        "effective_to": config.effective_to.isoformat() if config.effective_to else None,
    }


@router.patch("/api/v1/rules/{rule_id}", tags=["Rules"])
def update_rule(
    rule_id: str,
    req: RuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle or customize a compliance rule for the current user. Every change bumps the
    override's version and is audit-logged with before/after values."""
    definitions = _definitions(db)
    if not any(r["rule_id"] == rule_id for r in definitions):
        raise HTTPException(status_code=404, detail="Rule not found")

    config = db.query(RuleConfig).filter(
        RuleConfig.tenant_id == current_user.tenant_id, RuleConfig.rule_id == rule_id
    ).first()
    if not config:
        config = RuleConfig(user_id=current_user.id, rule_id=rule_id, enabled=True, priority=100, version=0)
        db.add(config)
        before = None
    else:
        before = _config_snapshot(config)

    changes = req.model_dump(exclude_unset=True)
    window_from = changes.get("effective_from", config.effective_from)
    window_to = changes.get("effective_to", config.effective_to)
    if window_from and window_to and window_to <= window_from:
        raise HTTPException(status_code=422, detail="effective_to must be after effective_from")
    for field, value in changes.items():
        setattr(config, field, value)
    config.version = (config.version or 0) + 1

    db.add(AuditLog(user_id=current_user.id, action="rule_updated",
                    resource_type="rule", resource_id=rule_id,
                    details={"before": before, "after": _config_snapshot(config)}))
    db.commit()
    db.refresh(config)

    return {
        "rule_id": rule_id,
        "enabled": config.enabled,
        "custom_parameters": config.custom_parameters,
        "priority": config.priority,
        "version": config.version,
        "effective_from": config.effective_from.isoformat() if config.effective_from else None,
        "effective_to": config.effective_to.isoformat() if config.effective_to else None,
        "detail": f"Rule {rule_id} updated",
    }


@router.get("/api/v1/rules", tags=["Rules"])
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List rules with the user's overrides applied, in execution (priority) order."""
    definitions = _definitions(db)
    now = datetime.utcnow()
    config_map = {c.rule_id: c for c in db.query(RuleConfig).filter(RuleConfig.tenant_id == current_user.tenant_id).all()}

    for rule in definitions:
        config = config_map.get(rule["rule_id"])
        active = config is not None and config_service.override_is_active(config, now)
        rule["priority"] = config.priority if config is not None and config.priority is not None else 100
        rule["version"] = config.version if config is not None else 0
        rule["effective_from"] = config.effective_from.isoformat() if config and config.effective_from else None
        rule["effective_to"] = config.effective_to.isoformat() if config and config.effective_to else None
        rule["override_active"] = active
        # is_customized only when parameters were actually changed (not just an on/off toggle)
        rule["is_customized"] = bool(active and config.custom_parameters)
        if active:
            rule["enabled"] = config.enabled
            if config.custom_parameters:
                rule["parameters"] = {**rule["parameters"], **config.custom_parameters}

    return sorted(definitions, key=lambda r: (r["priority"], r["rule_id"]))


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
    screening_cfg = config_service.screening_config(db)
    watchlist = lists.snapshot(db)
    countries = lists.high_risk_countries(db)
    definitions = rule_engine.rule_definitions(screening_cfg, countries, watchlist)
    rule_def = next((r for r in definitions if r["rule_id"] == req.rule_id), None)
    if not rule_def:
        raise HTTPException(404, "Rule not found")

    # Get transactions from last N days
    cutoff = datetime.utcnow() - timedelta(days=req.days)
    transactions = db.query(Transaction).filter(
        Transaction.tenant_id == current_user.tenant_id,
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

        result = rule_engine.evaluate_rule(rule_def, tx_data, screening_cfg, watchlist, countries)
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
        RuleConfig.tenant_id == current_user.tenant_id
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
        RuleConfig.tenant_id == current_user.tenant_id
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
        RuleConfig.tenant_id == current_user.tenant_id
    ).first()

    if not config:
        raise HTTPException(404, "Rule config not found")

    config.false_positive_count += 1
    db.commit()

    return {"recorded": True, "false_positive_count": config.false_positive_count}
