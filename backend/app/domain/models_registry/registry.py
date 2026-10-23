"""Model versions in the database: load the active/shadow model, register, promote (S2.5).

Promotion is a data change, never a deploy. The partial unique index on model_versions guarantees
one active version per kind even under concurrent promotions.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import AuditLog, ModelVersion
from app.domain.models_registry.risk_model import FEATURES, V1_PARAMS, WeightedLogisticModel

KIND = "risk"
CACHE_TTL_S = 30.0
_cache: dict[str, tuple[float, Optional[WeightedLogisticModel]]] = {}

# Used only when the registry holds no active version (e.g. a test database built without the
# 0003 seed); the decision still names this version so it stays attributable.
BUILTIN = WeightedLogisticModel("weighted-logistic@1", V1_PARAMS)

V1_MODEL_CARD = {
    "intended_use": "Independent risk signal for AML transaction screening, blended with hard-rule and "
                    "behavioral scores. Advisory: it cannot override a triggered hard rule.",
    "derivation": "Expert-defined weights. NOT trained: no labelled dataset exists for this deployment.",
    "features": {
        "amount_log": "log10(amount + 1) / 7, capped at 1",
        "country_risk": "1 if the destination is in the high-risk country list",
        "counterparty_risk": "closest sanctions/PEP name similarity above 0.6, rescaled to 0-1",
        "rag_signal": "highest RAG sanctions-corpus similarity",
        "velocity": "account transactions in the last 24h / 10, capped at 1",
        "type_risk": "fixed risk per transaction type (crypto 1.0 ... card 0.1)",
    },
    "known_limitations": [
        "Weights are not fitted to outcomes; precision/recall are unknown until the eval harness "
        "(S2.7) and reviewer feedback provide labels.",
        "Name similarity is Latin-script only (no transliteration of other scripts).",
        "Type risk is a static prior, not learned.",
    ],
    "validation": "Scenario suite in backend/tests/eval (S2.7); no production outcome data yet.",
    "approval": {"approved_by": None, "approved_at": None, "status": "pending review"},
}


def invalidate() -> None:
    _cache.clear()


def _load(db: Session, status: str) -> Optional[WeightedLogisticModel]:
    hit = _cache.get(status)
    now = time.monotonic()
    if hit and hit[0] > now:
        return hit[1]
    row = (db.query(ModelVersion).filter(ModelVersion.kind == KIND, ModelVersion.status == status)
           .order_by(ModelVersion.version.desc()).first())
    model = WeightedLogisticModel(row.label, row.params) if row is not None else None
    _cache[status] = (now + CACHE_TTL_S, model)
    return model


def active_model(db: Session) -> WeightedLogisticModel:
    return _load(db, "active") or BUILTIN


def shadow_model(db: Session) -> Optional[WeightedLogisticModel]:
    return _load(db, "shadow")


def validate_params(params: dict) -> None:
    """Raises ValueError unless params define a usable weighted-logistic model."""
    WeightedLogisticModel("validation", params)
    labels = params.get("labels") or {}
    if not (0 <= float(labels.get("medium_risk", -1)) <= float(labels.get("high_risk", -1)) <= 1):
        raise ValueError("labels must satisfy 0 <= medium_risk <= high_risk <= 1")


def register(db: Session, name: str, params: dict, model_card: dict, actor_id: str) -> ModelVersion:
    """Add a new version in shadow status (never active on creation)."""
    validate_params(params)
    next_version = (db.query(func.max(ModelVersion.version)).filter(ModelVersion.name == name).scalar() or 0) + 1
    row = ModelVersion(name=name, version=next_version, kind=KIND, status="shadow", params=params,
                       feature_list=list(FEATURES), model_card=model_card, created_by=actor_id)
    db.add(row)
    # Only one shadow at a time keeps the comparison unambiguous.
    for other in db.query(ModelVersion).filter(ModelVersion.kind == KIND, ModelVersion.status == "shadow").all():
        other.status = "retired"
    db.flush()
    db.add(AuditLog(user_id=actor_id, action="model_registered", resource_type="model_version",
                    resource_id=row.id, details={"label": row.label, "status": "shadow"}))
    db.commit()
    invalidate()
    return row


def promote(db: Session, version_id: str, actor_id: str) -> ModelVersion:
    row = db.get(ModelVersion, version_id)
    if row is None or row.kind != KIND:
        raise LookupError(version_id)
    previous = db.query(ModelVersion).filter(ModelVersion.kind == KIND, ModelVersion.status == "active").first()
    if previous is not None and previous.id != row.id:
        previous.status = "retired"
        db.flush()  # free the one-active slot before taking it
    row.status = "active"
    row.activated_at = datetime.utcnow()
    db.add(AuditLog(user_id=actor_id, action="model_promoted", resource_type="model_version", resource_id=row.id,
                    details={"label": row.label, "previous": previous.label if previous else None}))
    db.commit()
    invalidate()
    return row
