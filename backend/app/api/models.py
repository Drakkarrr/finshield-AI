"""FinShield AI — Risk model versioning and shadow mode API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.db_models import RiskModelVersion, User

router = APIRouter()


@router.get("/api/v1/models", tags=["Models"])
def list_models(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all risk model versions."""
    query = db.query(RiskModelVersion)
    if status:
        query = query.filter(RiskModelVersion.status == status)
    
    models = query.order_by(RiskModelVersion.created_at.desc()).all()
    
    return {
        "models": [
            {
                "id": m.id,
                "version": m.version,
                "name": m.name,
                "description": m.description,
                "model_type": m.model_type,
                "status": m.status,
                "is_active": m.is_active,
                "shadow_of": m.shadow_of,
                "shadow_percentage": m.shadow_percentage,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "activated_at": m.activated_at.isoformat() if m.activated_at else None,
            }
            for m in models
        ],
        "count": len(models),
    }


@router.get("/api/v1/models/{version}", tags=["Models"])
def get_model(
    version: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific model version with full model card."""
    model = db.query(RiskModelVersion).filter(RiskModelVersion.version == version).first()
    if not model:
        raise HTTPException(404, f"Model version {version} not found")
    
    return {
        "id": model.id,
        "version": model.version,
        "name": model.name,
        "description": model.description,
        "model_type": model.model_type,
        "config": model.config,
        "status": model.status,
        "is_active": model.is_active,
        "shadow_of": model.shadow_of,
        "shadow_percentage": model.shadow_percentage,
        "model_card": {
            "training_data_summary": model.training_data_summary,
            "performance_metrics": model.performance_metrics,
            "limitations": model.limitations,
        },
        "created_by": model.created_by,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "activated_at": model.activated_at.isoformat() if model.activated_at else None,
        "deprecated_at": model.deprecated_at.isoformat() if model.deprecated_at else None,
    }


@router.post("/api/v1/models", tags=["Models"])
def create_model(
    version: str,
    name: str,
    model_type: str,
    description: str | None = None,
    config: dict | None = None,
    training_data_summary: str | None = None,
    performance_metrics: dict | None = None,
    limitations: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new risk model version."""
    # Check if version already exists
    existing = db.query(RiskModelVersion).filter(RiskModelVersion.version == version).first()
    if existing:
        raise HTTPException(400, f"Model version {version} already exists")
    
    model = RiskModelVersion(
        id=f"model-{version}",
        version=version,
        name=name,
        description=description,
        model_type=model_type,
        config=config or {},
        status="development",
        is_active=False,
        training_data_summary=training_data_summary,
        performance_metrics=performance_metrics,
        limitations=limitations,
        created_by=current_user.id,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    
    return {
        "success": True,
        "version": model.version,
        "status": model.status,
        "message": f"Model {version} created in development status",
    }


@router.post("/api/v1/models/{version}/activate", tags=["Models"])
def activate_model(
    version: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate a model version (set as production)."""
    model = db.query(RiskModelVersion).filter(RiskModelVersion.version == version).first()
    if not model:
        raise HTTPException(404, f"Model version {version} not found")
    
    # Deactivate all other production models
    db.query(RiskModelVersion).filter(
        RiskModelVersion.status == "production",
        RiskModelVersion.version != version,
    ).update({
        "status": "deprecated",
        "is_active": False,
        "deprecated_at": datetime.utcnow(),
    })
    
    # Activate this model
    model.status = "production"
    model.is_active = True
    model.activated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "version": model.version,
        "status": model.status,
        "message": f"Model {version} activated as production",
    }


@router.post("/api/v1/models/{version}/shadow", tags=["Models"])
def enable_shadow_mode(
    version: str,
    shadow_of: str,
    shadow_percentage: float = 10.0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable shadow mode for a model version."""
    model = db.query(RiskModelVersion).filter(RiskModelVersion.version == version).first()
    if not model:
        raise HTTPException(404, f"Model version {version} not found")
    
    # Verify the production model exists
    prod_model = db.query(RiskModelVersion).filter(RiskModelVersion.version == shadow_of).first()
    if not prod_model:
        raise HTTPException(404, f"Production model {shadow_of} not found")
    
    if prod_model.status != "production":
        raise HTTPException(400, f"Model {shadow_of} is not in production status")
    
    model.shadow_of = shadow_of
    model.shadow_percentage = min(max(shadow_percentage, 0.0), 100.0)
    model.status = "shadow"
    model.is_active = True
    
    db.commit()
    
    return {
        "success": True,
        "version": model.version,
        "shadow_of": model.shadow_of,
        "shadow_percentage": model.shadow_percentage,
        "message": f"Shadow mode enabled: {version} will process {shadow_percentage}% of traffic alongside {shadow_of}",
    }


@router.post("/api/v1/models/{version}/deactivate", tags=["Models"])
def deactivate_model(
    version: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate a model version."""
    model = db.query(RiskModelVersion).filter(RiskModelVersion.version == version).first()
    if not model:
        raise HTTPException(404, f"Model version {version} not found")
    
    model.status = "deprecated"
    model.is_active = False
    model.deprecated_at = datetime.utcnow()
    model.shadow_of = None
    model.shadow_percentage = 0.0
    
    db.commit()
    
    return {
        "success": True,
        "version": model.version,
        "status": model.status,
        "message": f"Model {version} deactivated",
    }
