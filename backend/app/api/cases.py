"""FinShield AI — Case lifecycle, comments, notes, SLA escalation and aggregation."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.core import logger
from app.database import get_db
from app.db_models import (
    AuditLog,
    Case,
    CaseComment,
    CaseNote,
    Notification,
    Transaction,
    User,
)
from app.domain import cases as case_sla
from app.domain import webhooks
from app.models import (
    CaseCreateRequest,
    CaseResponse,
    CaseStatus,
)

router = APIRouter()


# ============================================================
# CASES ROUTES
# ============================================================

@router.post("/api/v1/cases", response_model=CaseResponse, status_code=201, tags=["Cases"])
def create_case(
    req: CaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new compliance case."""
    # Referential integrity: the transaction must exist and belong to this user
    tx_exists = db.query(Transaction).filter(
        Transaction.id == req.transaction_id, Transaction.tenant_id == current_user.tenant_id
    ).first()
    if not tx_exists:
        raise HTTPException(status_code=404, detail="Transaction not found for this account")

    case_id = f"CASE-{str(uuid.uuid4())[:8].upper()}"
    case = Case(
        id=case_id,
        user_id=current_user.id,
        transaction_id=req.transaction_id,
        status=CaseStatus.CREATED,
        priority=req.priority.value,
        severity=req.priority.value,
        sla_deadline=case_sla.sla_deadline(db, req.priority.value),
        reason=req.reason,
        assigned_to=req.assigned_to,
    )
    db.add(case)
    db.flush()
    webhooks.emit(db, current_user.tenant_id, "case.created",
                  {"case_id": case.id, "transaction_id": case.transaction_id, "priority": case.priority},
                  user_id=current_user.id)
    db.commit()
    db.refresh(case)

    # Notify on new case creation
    notif = Notification(
        user_id=current_user.id,
        type="new_case",
        title="Case created",
        message=f"Case {case_id} opened for transaction {req.transaction_id[:8]}… ({req.priority.value} priority).",
        link="/cases",
    )
    db.add(notif)
    db.commit()

    logger.info(f"Case created: {case_id} by {current_user.email}")

    return CaseResponse(
        case_id=case.id,
        transaction_id=case.transaction_id,
        status=case.status,
        priority=case.priority,
        reason=case.reason,
        assigned_to=case.assigned_to,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/api/v1/cases/{case_id}", response_model=CaseResponse, tags=["Cases"])
def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific case."""
    case = db.query(Case).filter(
        Case.id == case_id, Case.tenant_id == current_user.tenant_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(
        case_id=case.id, transaction_id=case.transaction_id,
        status=case.status, priority=case.priority, reason=case.reason,
        assigned_to=case.assigned_to, created_at=case.created_at, updated_at=case.updated_at,
    )


@router.get("/api/v1/cases", response_model=list[CaseResponse], tags=["Cases"])
def list_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all cases for the current user."""
    cases = db.query(Case).filter(Case.tenant_id == current_user.tenant_id).order_by(Case.created_at.desc()).all()
    return [
        CaseResponse(
            case_id=c.id, transaction_id=c.transaction_id,
            status=c.status, priority=c.priority, reason=c.reason,
            assigned_to=c.assigned_to, created_at=c.created_at, updated_at=c.updated_at,
        )
        for c in cases
    ]


# ============================================================
# CASE MANAGEMENT
# ============================================================

class CaseUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    resolution: Optional[str] = None  # confirmed_suspicious, false_positive, filed_sar, closed_no_action
    resolution_summary: Optional[str] = None


class CaseCommentRequest(BaseModel):
    body: str


@router.patch("/api/v1/cases/{case_id}", tags=["Cases"])
def update_case(
    case_id: str,
    req: CaseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update case status, assignment, or priority."""
    case = db.query(Case).filter(Case.id == case_id, Case.tenant_id == current_user.tenant_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    valid_statuses = ["created", "open", "under_review", "in_progress", "escalated", "resolved", "closed"]
    if req.status is not None:
        if req.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        case.status = req.status
    if req.assigned_to is not None:
        case.assigned_to = req.assigned_to
    if req.priority is not None:
        case.priority = req.priority
    if req.resolution is not None:
        case.resolution = req.resolution
        case.resolved_at = datetime.utcnow()
    if req.resolution_summary is not None:
        case.resolution_summary = req.resolution_summary

    db.add(AuditLog(user_id=current_user.id, action="case_updated", resource_type="case", resource_id=case_id,
                    details={"status": case.status, "assigned_to": case.assigned_to}))
    event = {"case_id": case.id, "status": case.status, "resolution": case.resolution}
    webhooks.emit(db, current_user.tenant_id, "case.updated", event, user_id=current_user.id)
    if req.status in ("resolved", "closed"):
        webhooks.emit(db, current_user.tenant_id, "case.resolved", event, user_id=current_user.id)
    db.commit()
    db.refresh(case)

    return CaseResponse(
        case_id=case.id, transaction_id=case.transaction_id,
        status=case.status, priority=case.priority, reason=case.reason,
        assigned_to=case.assigned_to, created_at=case.created_at, updated_at=case.updated_at,
    )


@router.get("/api/v1/cases/{case_id}/comments", tags=["Cases"])
def list_case_comments(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List comments on a case."""
    case = db.query(Case).filter(Case.id == case_id, Case.tenant_id == current_user.tenant_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    comments = db.query(CaseComment).filter(CaseComment.case_id == case_id).order_by(CaseComment.created_at.asc()).all()
    return [
        {"id": c.id, "body": c.body, "user_id": c.user_id, "created_at": c.created_at.isoformat()}
        for c in comments
    ]


@router.post("/api/v1/cases/{case_id}/comments", tags=["Cases"])
def add_case_comment(
    case_id: str,
    req: CaseCommentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a case."""
    case = db.query(Case).filter(Case.id == case_id, Case.tenant_id == current_user.tenant_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="Comment body cannot be empty")

    comment = CaseComment(case_id=case_id, user_id=current_user.id, body=req.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id, "body": comment.body, "user_id": comment.user_id, "created_at": comment.created_at.isoformat()}


# Investigator Notes (ephemeral, not audit-logged)
class CaseNoteRequest(BaseModel):
    note: str


@router.get("/api/v1/cases/{case_id}/notes", tags=["Cases"])
def list_case_notes(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List investigator notes on a case (ephemeral, not audit-logged)."""
    case = db.query(Case).filter(Case.id == case_id, Case.tenant_id == current_user.tenant_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    notes = db.query(CaseNote).filter(CaseNote.case_id == case_id).order_by(CaseNote.created_at.asc()).all()
    return [
        {
            "id": n.id,
            "note": n.note,
            "user_id": n.user_id,
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat(),
        }
        for n in notes
    ]


@router.post("/api/v1/cases/{case_id}/notes", tags=["Cases"])
def add_case_note(
    case_id: str,
    req: CaseNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add an investigator note to a case (ephemeral, not audit-logged)."""
    case = db.query(Case).filter(Case.id == case_id, Case.tenant_id == current_user.tenant_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not req.note.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")

    note = CaseNote(case_id=case_id, user_id=current_user.id, note=req.note)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "note": note.note,
        "user_id": note.user_id,
        "created_at": note.created_at.isoformat(),
    }


# SLA Escalation
@router.post("/api/v1/cases/check-sla", tags=["Cases"])
def check_sla_escalation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the SLA sweep for the caller's tenant now (the worker also runs it every 5 minutes)."""
    return case_sla.sla_sweep(db, current_user.tenant_id)


# Case Aggregation
@router.post("/api/v1/cases/aggregate", tags=["Cases"])
def aggregate_case(
    transaction_id: str,
    reason: str,
    priority: str = "medium",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a case or attach to existing open case for the same transaction account."""
    # Get transaction to find account
    tx = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.tenant_id == current_user.tenant_id
    ).first()
    if not tx:
        raise HTTPException(404, "Transaction not found")

    # Check for existing open case for this transaction's sender
    # In a real system, you'd match on account_id, but we're using sender_name as a proxy
    existing_case = db.query(Case).filter(
        Case.tenant_id == current_user.tenant_id,
        Case.status.in_(["open", "under_review", "created"]),
        Case.transaction_id.in_(
            db.query(Transaction.id).filter(
                Transaction.sender_name == tx.sender_name,
                Transaction.tenant_id == current_user.tenant_id
            )
        )
    ).first()

    if existing_case:
        # Attach to existing case (just add a comment noting the new transaction)
        comment = CaseComment(
            case_id=existing_case.id,
            user_id=current_user.id,
            body=f"[Auto-aggregated] Related transaction: {tx.id} - {reason}"
        )
        db.add(comment)
        db.commit()

        return {
            "aggregated": True,
            "case_id": existing_case.id,
            "message": f"Transaction attached to existing case {existing_case.id}",
        }
    else:
        # Create new case
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        new_case = Case(
            id=case_id,
            user_id=current_user.id,
            transaction_id=tx.id,
            status="created",
            priority=priority,
            severity=priority,  # Map priority to severity for SLA
            reason=reason,
        )

        new_case.sla_deadline = case_sla.sla_deadline(db, priority)

        db.add(new_case)
        db.flush()
        webhooks.emit(db, current_user.tenant_id, "case.created",
                      {"case_id": new_case.id, "transaction_id": tx.id, "priority": priority}, user_id=current_user.id)
        db.commit()
        db.refresh(new_case)

        return {
            "aggregated": False,
            "case_id": new_case.id,
            "message": "New case created",
        }


@router.delete("/api/v1/cases/{case_id}", tags=["Cases"])
def delete_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a case and its comments."""
    case = db.query(Case).filter(
        Case.id == case_id, Case.tenant_id == current_user.tenant_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.query(CaseComment).filter(CaseComment.case_id == case_id).delete()
    db.delete(case)
    db.commit()
    return {"deleted": case_id}
