"""FinShield AI — API key management."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    api_key_digest,
    generate_api_key,
    get_current_user,
)
from app.core import client_ip_pseudonymised, logger
from app.database import get_db
from app.db_models import (
    ApiKey,
    AuditLog,
    User,
)

router = APIRouter()


# ============================================================
# API KEY MANAGEMENT
# ============================================================

class ApiKeyCreateRequest(BaseModel):
    name: str

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


@router.post("/api/v1/keys", response_model=dict, status_code=201, tags=["API Keys"])
def create_api_key(
    request: Request,
    req: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new API key for programmatic access."""
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = ApiKey(
        user_id=current_user.id,
        name=req.name,
        key_hash=key_hash,
        key_digest=api_key_digest(raw_key),
        key_prefix=key_prefix,
    )
    db.add(api_key)
    db.commit()

    ip_pseudo = client_ip_pseudonymised(request)
    db.add(AuditLog(
        user_id=current_user.id,
        action="api_key_created",
        resource_type="api_key",
        resource_id=api_key.id,
        details={"name": req.name, "key_prefix": key_prefix},
        ip_address=ip_pseudo
    ))
    db.commit()

    logger.info(f"API key created for user {current_user.email}: {req.name}")

    # Return full key ONLY on creation
    return {
        "id": api_key.id,
        "name": req.name,
        "key": raw_key,
        "key_prefix": key_prefix,
        "created_at": api_key.created_at.isoformat(),
    }


@router.get("/api/v1/keys", response_model=list[ApiKeyResponse], tags=["API Keys"])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all()
    return [
        ApiKeyResponse(
            id=k.id, name=k.name, key_prefix=k.key_prefix,
            is_active=k.is_active, created_at=k.created_at, last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.delete("/api/v1/keys/{key_id}", tags=["API Keys"])
def revoke_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.user_id == current_user.id
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False

    ip_pseudo = client_ip_pseudonymised(request)
    db.add(AuditLog(
        user_id=current_user.id,
        action="api_key_revoked",
        resource_type="api_key",
        resource_id=key_id,
        details={"name": api_key.name},
        ip_address=ip_pseudo
    ))
    db.commit()
    logger.info(f"API key revoked: {key_id}")
    return {"detail": "API key revoked"}
