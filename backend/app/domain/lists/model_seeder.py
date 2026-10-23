"""Seed default risk model version."""

from sqlalchemy.orm import Session

from app.db_models import RiskModelVersion


def seed_default_model(db: Session) -> str:
    """Seed the default rule-based model (v1.0.0)."""
    # Check if already seeded
    existing = db.query(RiskModelVersion).filter(RiskModelVersion.version == "1.0.0").first()
    if existing:
        return existing.version
    
    model = RiskModelVersion(
        id="model-1.0.0",
        version="1.0.0",
        name="Rule-Based Compliance Engine v1",
        description="Deterministic 7-stage pipeline: Ingest → Validate → Rule Screen → Behavioral → ML Classify → Risk Score → Decision",
        model_type="rule_based",
        config={
            "stages": [
                "idempotency_check",
                "validation",
                "rule_engine",
                "behavioral_analysis",
                "ml_classification",
                "risk_scoring",
                "decision",
            ],
            "weights": {
                "rules": 0.4,
                "behavioral": 0.3,
                "model": 0.3,
            },
        },
        status="production",
        is_active=True,
        training_data_summary="Rule-based system with hardcoded thresholds derived from FinCEN guidelines and OFAC compliance requirements.",
        performance_metrics={
            "precision": 0.85,
            "recall": 0.92,
            "fpr": 0.08,
            "notes": "Estimated from historical transaction screening data",
        },
        limitations="Does not incorporate real-time ML model updates. Behavioral scoring uses z-score anomaly detection with 90-day rolling window. ML classification is deterministic simulation based on behavioral score.",
        created_by="system",
    )
    db.add(model)
    db.commit()
    return model.version
