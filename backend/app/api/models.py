"""FinShield AI — Risk model versions: list, register (shadow), promote (S2.5, S7.4)."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.db_models import AuditLog, ChangeRequest, ModelVersion, User
from app.domain.models_registry import registry

router = APIRouter()


class ModelRegisterRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str
    params: dict[str, Any]
    model_card: dict[str, Any]


def _out(row: ModelVersion) -> dict:
    return {"id": row.id, "label": row.label, "name": row.name, "version": row.version, "kind": row.kind,
            "status": row.status, "params": row.params, "feature_list": row.feature_list, "metrics": row.metrics,
            "model_card": row.model_card, "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "activated_at": row.activated_at.isoformat() if row.activated_at else None}


@router.get("/api/v1/models", tags=["Models"])
def list_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every model version, newest first."""
    rows = db.query(ModelVersion).order_by(ModelVersion.created_at.desc(), ModelVersion.version.desc()).all()
    return [_out(r) for r in rows]


@router.post("/api/v1/models", status_code=201, tags=["Models"])
def register_model(req: ModelRegisterRequest, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Register a new version. It starts in shadow: scored on every eligible screening and stored
    on the transaction, but it never affects a decision until promoted."""
    try:
        row = registry.register(db, req.name, req.params, req.model_card, current_user.id)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=422, detail=f"invalid model params: {e}") from None
    return _out(row)


@router.post("/api/v1/models/{version_id}/promote", tags=["Models"])
def promote_model(version_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Propose a model promotion. Requires approval from a different supervisor or admin (S7.4)."""
    row = db.query(ModelVersion).filter(ModelVersion.id == version_id).first()
    if not row or row.kind != "risk":
        raise HTTPException(status_code=404, detail="Model version not found")

    # Check if there's already a pending promotion for this version
    existing = db.query(ChangeRequest).filter(
        ChangeRequest.tenant_id == current_user.tenant_id,
        ChangeRequest.change_type == "model_promote",
        ChangeRequest.resource_id == version_id,
        ChangeRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A promotion request is already pending for this version")

    # Create a change request
    cr = ChangeRequest(
        tenant_id=current_user.tenant_id,
        change_type="model_promote",
        resource_id=version_id,
        proposed_by=current_user.id,
        payload={"model_version_id": version_id, "label": row.label},
    )
    db.add(cr)
    db.add(AuditLog(
        user_id=current_user.id,
        action="change_request_proposed",
        resource_type="change_request",
        resource_id=version_id,
        details={"change_type": "model_promote", "model_version_id": version_id},
    ))
    db.commit()
    db.refresh(cr)

    return {
        "change_request_id": cr.id,
        "status": "pending",
        "message": "Model promotion proposed. Requires approval from a different supervisor or admin.",
    }
