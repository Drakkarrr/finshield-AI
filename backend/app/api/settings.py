"""FinShield AI — Runtime settings and feature flags (S1.4)."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config_service
from app.auth import get_current_user
from app.database import get_db
from app.db_models import FeatureFlag, Setting, User

router = APIRouter()


class SettingUpdate(BaseModel):
    value: Any


class FlagUpdate(BaseModel):
    enabled: bool


def _rows(db: Session, model) -> dict:
    """Effective override per key for the caller's tenant: tenant scope wins over global."""
    tenant = db.info.get("tenant_id") or config_service.GLOBAL
    rows = db.query(model).filter(model.scope.in_({tenant, config_service.GLOBAL})).all()
    return {r.key: r for r in sorted(rows, key=lambda r: r.scope == tenant)}


@router.get("/api/v1/settings", tags=["Settings"])
def list_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every runtime setting with its effective value, default and provenance."""
    rows = _rows(db, Setting)
    return [
        {
            "key": key,
            "value": rows[key].value if key in rows else default,
            "default": default,
            "description": description,
            "source": "override" if key in rows else "default",
            "updated_by": rows[key].updated_by if key in rows else None,
            "updated_at": rows[key].updated_at.isoformat() if key in rows and rows[key].updated_at else None,
        }
        for key, (default, _validate, description) in config_service.SETTINGS.items()
    ]


@router.put("/api/v1/settings/{key}", tags=["Settings"])
def update_setting(
    key: str,
    req: SettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change a setting at runtime. Validated per key; audit-logged with before/after and actor."""
    try:
        value = config_service.set_setting(db, key, req.value, current_user.id)
    except config_service.UnknownKey:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}") from None
    except config_service.InvalidValue as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return {"key": key, "value": value}


@router.get("/api/v1/flags", tags=["Settings"])
def list_flags(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every feature flag with its effective state and provenance."""
    rows = _rows(db, FeatureFlag)
    return [
        {
            "key": key,
            "enabled": bool(rows[key].enabled) if key in rows else default,
            "default": default,
            "description": description,
            "source": "override" if key in rows else "default",
            "updated_by": rows[key].updated_by if key in rows else None,
        }
        for key, (default, description) in config_service.FLAGS.items()
    ]


@router.put("/api/v1/flags/{key}", tags=["Settings"])
def update_flag(
    key: str,
    req: FlagUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a feature flag at runtime; audit-logged with before/after and actor."""
    try:
        enabled = config_service.set_flag(db, key, req.enabled, current_user.id)
    except config_service.UnknownKey:
        raise HTTPException(status_code=404, detail=f"Unknown flag: {key}") from None
    return {"key": key, "enabled": enabled}
