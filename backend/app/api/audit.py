"""FinShield AI — Audit trail: query, verify, signed export (S3.2). Supervisor+ (app.permissions)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app import crypto
from app.auth import get_current_user
from app.core import client_ip_pseudonymised
from app.database import get_db
from app.db_models import AuditLog, User
from app.domain import audit

router = APIRouter()


@router.get("/api/v1/audit", tags=["Audit"])
def list_audit(
    actor: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The tenant's audit entries, newest first, filterable by actor / entity / type / date."""
    q = db.query(AuditLog).filter(AuditLog.tenant_id == current_user.tenant_id)
    for column, value in ((AuditLog.user_id, actor), (AuditLog.action, action),
                          (AuditLog.resource_type, resource_type), (AuditLog.resource_id, resource_id)):
        if value:
            q = q.filter(column == value)
    if date_from:
        q = q.filter(AuditLog.created_at >= date_from)
    if date_to:
        q = q.filter(AuditLog.created_at <= date_to)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset,
            "items": [{**audit.payload(r), "prev_hash": r.prev_hash, "entry_hash": r.entry_hash,
                       "sealed": r.seq is not None} for r in rows]}


@router.get("/api/v1/audit/verify", tags=["Audit"])
def verify_audit(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Seal pending entries, then recompute the tenant's whole chain."""
    return audit.verify(db, current_user.tenant_id)


@router.get("/api/v1/audit/export", tags=["Audit"])
def export_audit(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Signed chain-of-custody bundle; verify offline with scripts/verify_audit_export.py."""
    bundle = audit.export(db, current_user.tenant_id)
    ip_pseudo = client_ip_pseudonymised(request)
    db.add(AuditLog(user_id=current_user.id, action="audit_exported", resource_type="audit",
                    details={"count": bundle["count"], "head": bundle["verification"].get("head_hash")},
                    ip_address=ip_pseudo))
    db.commit()
    return bundle


@router.get("/api/v1/audit/public-key", tags=["Audit"])
def audit_public_key(current_user: User = Depends(get_current_user)):
    """The Ed25519 public key that verifies export signatures."""
    return {"algorithm": "Ed25519", "public_key": crypto.public_key_pem()}
