"""Runtime configuration: settings and feature flags, editable without a redeploy (S1.4).

Defaults live here, typed. The `settings` / `feature_flags` tables hold overrides (seeded by
migration 0002 with these same values). Reads go through a 30 s per-process TTL cache, cleared on
every write in this process; other replicas pick a change up within the TTL.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db_models import AuditLog, FeatureFlag, RuleConfig, Setting

CACHE_TTL_S = 30.0
GLOBAL = "global"


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


def _unit(v: Any) -> bool:
    return _number(v) and v <= 1


def _weights(v: Any) -> bool:
    return (isinstance(v, dict) and set(v) == {"rules", "behavioral", "model"}
            and all(_unit(x) for x in v.values()) and abs(sum(v.values()) - 1.0) < 1e-6)


def _bands(v: Any) -> bool:
    keys = ("block", "block_if_rule", "flag", "review")
    return (isinstance(v, dict) and set(v) == set(keys) and all(_unit(v[k]) for k in keys)
            and v["block"] >= v["block_if_rule"] and v["block"] >= v["flag"] >= v["review"])


def _credit_cost(v: Any) -> bool:
    return isinstance(v, dict) and set(v) == {"rule_only", "behavioral", "full_ml"} and all(_number(x) for x in v.values())


def _credit_packs(v: Any) -> bool:
    return isinstance(v, dict) and bool(v) and all(k.isdigit() and _number(p) for k, p in v.items())


def _sla_hours(v: Any) -> bool:
    return isinstance(v, dict) and set(v) == {"low", "medium", "high", "critical"} and all(_number(x) and x > 0 for x in v.values())


def _bool(v: Any) -> bool:
    return isinstance(v, bool)


def _pii_fields(v: Any) -> bool:
    return isinstance(v, dict) and all(isinstance(k, str) and isinstance(f, list) for k, f in v.items())


def _roles(v: Any) -> bool:
    return isinstance(v, list) and all(r in ("analyst", "investigator", "supervisor", "admin") for r in v)


def _plans(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(p, dict) and {"id", "name", "price_monthly", "included_credits"} <= set(p) for p in v)


PLANS_DEFAULT = [
    {
        "id": "starter",
        "name": "Starter",
        "price_monthly": 29,
        "included_credits": 15000,
        "features": ["Up to 15,000 credits/mo", "Rule + behavioral screening", "Email support", "1 API key"],
    },
    {
        "id": "growth",
        "name": "Growth",
        "price_monthly": 99,
        "included_credits": 60000,
        "features": ["Up to 60,000 credits/mo", "Full ML pipeline", "Case management", "Priority support"],
    },
    {
        "id": "pro",
        "name": "Pro",
        "price_monthly": 299,
        "included_credits": 250000,
        "features": ["Up to 250,000 credits/mo", "Everything in Growth", "SAR/STR filing", "Dedicated CSM"],
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "price_monthly": None,
        "included_credits": None,
        "features": ["Unlimited credits", "On-premise / VPC (planned)", "SSO + audit export (planned)", "99.9% uptime SLA (planned)"],
    },
]

# key -> (default, validator, description)
SETTINGS: dict[str, tuple[Any, Callable[[Any], bool], str]] = {
    "rules.threshold.wire": (10000.0, _number, "RULE-003 review threshold for wire transfers"),
    "rules.threshold.international": (50000.0, _number, "RULE-003 review threshold for other types"),
    "behavioral.trigger.cold_start": (0.5, _unit, "Anomaly score that triggers review for accounts < 30 days old"),
    "behavioral.trigger.warm": (0.65, _unit, "Anomaly score that triggers review for established accounts"),
    "behavioral.cold_start_days": (30, _number, "Accounts with less history than this are cold-start"),
    "behavioral.min_history_txs": (5, _number, "Fewer prior transactions than this is also cold-start"),
    "lists.fuzzy_threshold": (0.88, _unit, "Minimum name similarity (0-1) for a fuzzy sanctions/PEP hit"),
    "lists.max_age_hours": (48, _number, "A list source older than this is reported stale"),
    "risk.weights": ({"rules": 0.5, "behavioral": 0.3, "model": 0.2}, _weights, "Risk blend weights (sum to 1)"),
    "decision.bands": ({"block": 0.8, "block_if_rule": 0.6, "flag": 0.5, "review": 0.3}, _bands,
                       "Score-based decision bands, used only when no rule action fired"),
    "billing.credit_cost": ({"rule_only": 0.2, "behavioral": 0.5, "full_ml": 1.0}, _credit_cost,
                            "Credits consumed per screening, by pipeline depth"),
    "billing.credit_packs": ({"10000": 9, "50000": 39, "200000": 129}, _credit_packs,
                             "One-off credit packs: credits -> price in USD"),
    "billing.plans": (PLANS_DEFAULT, _plans, "Subscription plans"),
    "privacy.pii_fields": ({
        "users": ["email", "first_name", "last_name", "company", "timezone"],
        "transactions": ["sender_name", "receiver_name", "account_id", "description"],
        "filings": ["narrative", "structured_data"],
        "case_comments": ["body"],
        "case_notes": ["note"],
    }, _pii_fields, "Personal-data fields per table (DSAR scope, masking)"),
    "privacy.mask_roles": (["analyst"], _roles, "Roles that see party names and account ids masked"),
    "privacy.dsar_due_days": (30, _number, "Days to answer a data-subject request (GDPR Art. 12(3))"),
    "privacy.retention_years": (5, _number, "AML record-keeping window; erasure retains newer records"),
    "webhooks.max_attempts": (6, _number, "Delivery attempts before an event moves to the dead-letter queue"),
    "webhooks.backoff_base_seconds": (30, _number, "First retry delay; doubles per attempt, plus jitter"),
    "webhooks.timeout_seconds": (10, _number, "Per-attempt HTTP timeout"),
    "webhooks.allow_http": (False, _bool, "Permit plain-http subscriber URLs (development only)"),
    "webhooks.allow_private_targets": (False, _bool, "Permit private/loopback subscriber addresses (SSRF guard off)"),
    "sla.approaching_minutes": (60, _number, "Notify when a case is this close to its SLA deadline"),
    "cases.sla_hours": ({"low": 72, "medium": 24, "high": 4, "critical": 1}, _sla_hours,
                        "Case SLA deadline in hours, by severity"),
    "filings.reminder_days": (7, _number, "Remind about filings due within this many days"),
}

FLAGS: dict[str, tuple[bool, str]] = {
    "screening.behavioral": (True, "Run the behavioral stage"),
    "screening.ml": (True, "Run the model stage"),
    "screening.rag": (True, "Run RAG retrieval when the RAG service is configured"),
}

_cache: dict[tuple[str, str], tuple[float, Any]] = {}


class UnknownKey(KeyError):
    pass


class InvalidValue(ValueError):
    pass


def invalidate() -> None:
    _cache.clear()


def _cached(kind: str, key: str, load: Callable[[], Any]) -> Any:
    hit = _cache.get((kind, key))
    now = time.monotonic()
    if hit and hit[0] > now:
        return hit[1]
    value = load()
    _cache[(kind, key)] = (now + CACHE_TTL_S, value)
    return value


def _scope(db: Session) -> str:
    """The bound tenant (S3.4); unbound sessions (system jobs) read the global scope."""
    return db.info.get("tenant_id") or GLOBAL


def get_setting(db: Session, key: str) -> Any:
    """Tenant override, else the global value, else the code default."""
    if key not in SETTINGS:
        raise UnknownKey(key)
    scope = _scope(db)

    def load() -> Any:
        rows = {r.scope: r.value for r in
                db.query(Setting).filter(Setting.key == key, Setting.scope.in_({scope, GLOBAL}))}
        return rows.get(scope, rows.get(GLOBAL, SETTINGS[key][0]))

    return _cached("setting", f"{scope}:{key}", load)


def get_flag(db: Session, key: str) -> bool:
    if key not in FLAGS:
        raise UnknownKey(key)
    scope = _scope(db)

    def load() -> bool:
        rows = {r.scope: r.enabled for r in
                db.query(FeatureFlag).filter(FeatureFlag.key == key, FeatureFlag.scope.in_({scope, GLOBAL}))}
        return bool(rows.get(scope, rows.get(GLOBAL, FLAGS[key][0])))

    return _cached("flag", f"{scope}:{key}", load)


def set_setting(db: Session, key: str, value: Any, actor_id: str) -> Any:
    if key not in SETTINGS:
        raise UnknownKey(key)
    if not SETTINGS[key][1](value):
        raise InvalidValue(f"invalid value for {key}: {SETTINGS[key][2]}")
    before = get_setting(db, key)
    scope = _scope(db)
    row = db.query(Setting).filter(Setting.key == key, Setting.scope == scope).first()
    if row is None:
        row = Setting(key=key, scope=scope)
        db.add(row)
    row.value = value
    row.updated_by = actor_id
    row.updated_at = datetime.utcnow()
    db.add(AuditLog(user_id=actor_id, action="setting_changed", resource_type="setting", resource_id=key,
                    details={"before": before, "after": value}))
    db.commit()
    invalidate()
    return value


def set_flag(db: Session, key: str, enabled: bool, actor_id: str) -> bool:
    if key not in FLAGS:
        raise UnknownKey(key)
    before = get_flag(db, key)
    scope = _scope(db)
    row = db.query(FeatureFlag).filter(FeatureFlag.key == key, FeatureFlag.scope == scope).first()
    if row is None:
        row = FeatureFlag(key=key, scope=scope)
        db.add(row)
    row.enabled = enabled
    row.updated_by = actor_id
    row.updated_at = datetime.utcnow()
    db.add(AuditLog(user_id=actor_id, action="flag_changed", resource_type="feature_flag", resource_id=key,
                    details={"before": before, "after": enabled}))
    db.commit()
    invalidate()
    return enabled


@dataclass(frozen=True)
class ScreeningConfig:
    """Everything the engine needs from runtime config, resolved once per request."""
    threshold_wire: float
    threshold_international: float
    weights: dict
    bands: dict
    credit_cost: dict
    behavioral_enabled: bool
    ml_enabled: bool
    behavioral_trigger_warm: float = 0.65
    behavioral_trigger_cold_start: float = 0.5
    cold_start_days: int = 30
    min_history_txs: int = 5
    list_fuzzy_threshold: float = 0.88

    @classmethod
    def defaults(cls) -> "ScreeningConfig":
        return cls(
            threshold_wire=SETTINGS["rules.threshold.wire"][0],
            threshold_international=SETTINGS["rules.threshold.international"][0],
            weights=SETTINGS["risk.weights"][0],
            bands=SETTINGS["decision.bands"][0],
            credit_cost=SETTINGS["billing.credit_cost"][0],
            behavioral_enabled=True,
            ml_enabled=True,
            behavioral_trigger_warm=SETTINGS["behavioral.trigger.warm"][0],
            behavioral_trigger_cold_start=SETTINGS["behavioral.trigger.cold_start"][0],
            cold_start_days=SETTINGS["behavioral.cold_start_days"][0],
            min_history_txs=SETTINGS["behavioral.min_history_txs"][0],
            list_fuzzy_threshold=SETTINGS["lists.fuzzy_threshold"][0],
        )


def screening_config(db: Session) -> ScreeningConfig:
    return ScreeningConfig(
        threshold_wire=float(get_setting(db, "rules.threshold.wire")),
        threshold_international=float(get_setting(db, "rules.threshold.international")),
        weights=get_setting(db, "risk.weights"),
        bands=get_setting(db, "decision.bands"),
        credit_cost=get_setting(db, "billing.credit_cost"),
        behavioral_enabled=get_flag(db, "screening.behavioral"),
        ml_enabled=get_flag(db, "screening.ml"),
        behavioral_trigger_warm=float(get_setting(db, "behavioral.trigger.warm")),
        behavioral_trigger_cold_start=float(get_setting(db, "behavioral.trigger.cold_start")),
        cold_start_days=int(get_setting(db, "behavioral.cold_start_days")),
        min_history_txs=int(get_setting(db, "behavioral.min_history_txs")),
        list_fuzzy_threshold=float(get_setting(db, "lists.fuzzy_threshold")),
    )


def override_is_active(rc: RuleConfig, now: datetime) -> bool:
    """A rule override applies only inside its effective window. Outside it the built-in rule
    runs with defaults; the rule itself is never skipped, so a lapsed override cannot silently
    switch off sanctions screening."""
    if rc.effective_from is not None and now < rc.effective_from:
        return False
    if rc.effective_to is not None and now >= rc.effective_to:
        return False
    return True


def rule_overrides(db: Session, tenant_id: str, now: datetime | None = None) -> dict[str, dict]:
    """The tenant's rule overrides that are in effect at `now`, in the shape the engine expects."""
    now = now or datetime.utcnow()
    return {
        rc.rule_id: {
            "enabled": rc.enabled,
            "custom_parameters": rc.custom_parameters,
            "priority": rc.priority if rc.priority is not None else 100,
            "version": rc.version,
        }
        for rc in db.query(RuleConfig).filter(RuleConfig.tenant_id == tenant_id).all()
        if override_is_active(rc, now)
    }
