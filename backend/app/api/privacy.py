"""FinShield AI — Data-subject requests (S3.3). Supervisor+ (app.permissions)."""
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import config_service, crypto
from app.auth import get_current_user
from app.database import get_db
from app.db_models import AuditLog, PrivacyRequest, User
from app.domain import privacy

router = APIRouter()


class PrivacyRequestCreate(BaseModel):
    subject_type: Literal["customer", "user"] = "customer"
    subject_ref: str = Field(min_length=1, description="Customer name or account id, or a user's email")
    request_type: Literal["access", "erasure"]
    legal_basis_notes: Optional[str] = None


class DSARRequest(BaseModel):
    subject_email: str
    request_type: Literal["access", "erasure"]


def _out(r: PrivacyRequest, with_outcome: bool = False) -> dict:
    out = {"id": r.id, "subject_type": r.subject_type, "subject_ref_masked": privacy.mask_name(
        crypto.decrypt_json(r.subject_ref_enc)), "request_type": r.request_type, "status": r.status,
        "received_at": r.received_at.isoformat(), "due_at": r.due_at.isoformat(),
        "overdue": r.status == "received" and r.due_at < datetime.utcnow(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None, "handled_by": r.handled_by,
        "legal_basis_notes": r.legal_basis_notes}
    if with_outcome:
        out["outcome"] = crypto.decrypt_json(r.outcome_enc) if r.outcome_enc else None
    return out


def _create(db: Session, user: User, subject_type: str, subject_ref: str, request_type: str,
            notes: Optional[str]) -> PrivacyRequest:
    now = datetime.utcnow()
    req = PrivacyRequest(subject_type=subject_type, subject_ref_enc=crypto.encrypt_json(subject_ref),
                         subject_ref_hash=crypto.pseudonym(subject_ref) or "", request_type=request_type,
                         status="received", received_at=now, legal_basis_notes=notes,
                         due_at=now + timedelta(days=float(config_service.get_setting(db, "privacy.dsar_due_days"))))
    db.add(req)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="privacy_request_received", resource_type="privacy_request",
                    resource_id=req.id, details={"type": request_type, "subject_type": subject_type,
                                                 "subject": req.subject_ref_hash}))
    db.commit()
    db.refresh(req)
    return req


@router.post("/api/v1/privacy/requests", status_code=201, tags=["Privacy"])
def create_privacy_request(req: PrivacyRequestCreate, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    """Log a data-subject request; due date from privacy.dsar_due_days."""
    return _out(_create(db, current_user, req.subject_type, req.subject_ref, req.request_type, req.legal_basis_notes))


@router.post("/api/v1/privacy/dsar", tags=["Privacy"])
def create_dsar_request(req: DSARRequest, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Log a request about a platform user identified by email (see /privacy/requests for customers)."""
    return _out(_create(db, current_user, "user", req.subject_email, req.request_type, None))


@router.get("/api/v1/privacy/requests", tags=["Privacy"])
def list_privacy_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The tenant's requests, oldest due first; `overdue` flags missed deadlines."""
    rows = (db.query(PrivacyRequest).filter(PrivacyRequest.tenant_id == current_user.tenant_id)
            .order_by(PrivacyRequest.due_at).all())
    return [_out(r) for r in rows]


@router.get("/api/v1/privacy/requests/{request_id}", tags=["Privacy"])
def get_privacy_request(request_id: str, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    row = db.query(PrivacyRequest).filter(PrivacyRequest.id == request_id,
                                          PrivacyRequest.tenant_id == current_user.tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    return _out(row, with_outcome=True)


@router.post("/api/v1/privacy/requests/{request_id}/execute", tags=["Privacy"])
def execute_privacy_request(request_id: str, current_user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """Run the request: an access export, or an erasure that retains what regulation requires."""
    row = db.query(PrivacyRequest).filter(PrivacyRequest.id == request_id,
                                          PrivacyRequest.tenant_id == current_user.tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Privacy request not found")
    if row.status != "received":
        raise HTTPException(status_code=409, detail=f"Request already {row.status}")
    subject = crypto.decrypt_json(row.subject_ref_enc)
    if row.request_type == "access":
        outcome = privacy.access_export(db, current_user.tenant_id, row.subject_type, subject)
    else:
        outcome = privacy.erase(db, current_user.tenant_id, row.subject_type, subject)
    row.outcome_enc = crypto.encrypt_json(outcome)
    row.status = "completed"
    row.completed_at = datetime.utcnow()
    row.handled_by = current_user.id
    db.add(AuditLog(user_id=current_user.id, action="privacy_request_completed", resource_type="privacy_request",
                    resource_id=row.id, details={"type": row.request_type, "subject": row.subject_ref_hash,
                                                 "erased": len(outcome.get("erased", [])),
                                                 "retained": len(outcome.get("retained", []))}))
    db.commit()
    return _out(row, with_outcome=True)


@router.get("/api/v1/privacy/pii-classification", tags=["Privacy"])
def get_pii_classification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Personal-data fields, masked roles and retention, from runtime config."""
    return privacy.classification(db)
