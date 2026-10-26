"""FinShield AI — SAR/STR filings."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import permissions
from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    AuditLog,
    Case,
    Filing,
    FilingVersion,
    Transaction,
    User,
)
from app.domain import webhooks

router = APIRouter()


# ============================================================
# SAR/STR FILING ROUTES
# ============================================================

class FilingCreate(BaseModel):
    case_id: str
    filing_type: str  # SAR or STR
    narrative: Optional[str] = None


class FilingUpdate(BaseModel):
    narrative: Optional[str] = None
    status: Optional[str] = None  # draft, under_review, submitted, confirmed, rejected
    reference_number: Optional[str] = None
    amendment_reason: Optional[str] = None  # Required when amending submitted/confirmed filings


class FilingResponse(BaseModel):
    id: str
    case_id: str
    filing_type: str
    status: str
    deadline: Optional[str]
    narrative: Optional[str]
    structured_data: Optional[dict]
    reference_number: Optional[str]
    submitted_at: Optional[str]
    submitted_by: Optional[str]
    confirmed_at: Optional[str]
    confirmed_by: Optional[str]
    created_at: str
    updated_at: str


@router.post("/api/v1/filings", response_model=FilingResponse, status_code=201, tags=["Filings"])
def create_filing(
    filing: FilingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new SAR/STR filing draft for a case."""
    # Verify case exists and belongs to user
    case = db.query(Case).filter(Case.id == filing.case_id, Case.tenant_id == current_user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    # Verify case is resolved as suspicious
    if case.resolution not in ["confirmed_suspicious", "filed_sar"]:
        raise HTTPException(400, "Case must be resolved as suspicious before filing")

    # Calculate deadline (30 days from now for FinCEN SAR)
    deadline = datetime.utcnow() + timedelta(days=30)

    # Auto-populate structured data from case
    transaction = db.query(Transaction).filter(Transaction.id == case.transaction_id).first()
    structured_data = {
        "transaction_id": transaction.id,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "sender_name": transaction.sender_name,
        "receiver_name": transaction.receiver_name,
        "destination_country": transaction.destination_country,
        "transaction_date": transaction.created_at.isoformat(),
        "case_id": case.id,
        "case_reason": case.reason,
    }

    db_filing = Filing(
        case_id=filing.case_id,
        user_id=current_user.id,
        filing_type=filing.filing_type,
        status="draft",
        deadline=deadline,
        narrative=filing.narrative or "",
        structured_data=structured_data,
    )
    db.add(db_filing)
    db.commit()
    db.refresh(db_filing)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="filing_created",
        resource_type="filing",
        resource_id=db_filing.id,
        details={"filing_type": filing.filing_type, "case_id": filing.case_id},
    ))
    db.commit()

    return FilingResponse(
        id=db_filing.id,
        case_id=db_filing.case_id,
        filing_type=db_filing.filing_type,
        status=db_filing.status,
        deadline=db_filing.deadline.isoformat() if db_filing.deadline else None,
        narrative=db_filing.narrative,
        structured_data=db_filing.structured_data,
        reference_number=db_filing.reference_number,
        submitted_at=db_filing.submitted_at.isoformat() if db_filing.submitted_at else None,
        submitted_by=db_filing.submitted_by,
        confirmed_at=db_filing.confirmed_at.isoformat() if db_filing.confirmed_at else None,
        confirmed_by=db_filing.confirmed_by,
        created_at=db_filing.created_at.isoformat(),
        updated_at=db_filing.updated_at.isoformat(),
    )


@router.get("/api/v1/filings", response_model=list[FilingResponse], tags=["Filings"])
def list_filings(
    status: Optional[str] = None,
    filing_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all filings for the current user."""
    query = db.query(Filing).filter(Filing.tenant_id == current_user.tenant_id)

    if status:
        query = query.filter(Filing.status == status)
    if filing_type:
        query = query.filter(Filing.filing_type == filing_type)

    filings = query.order_by(Filing.created_at.desc()).all()

    return [
        FilingResponse(
            id=f.id,
            case_id=f.case_id,
            filing_type=f.filing_type,
            status=f.status,
            deadline=f.deadline.isoformat() if f.deadline else None,
            narrative=f.narrative,
            structured_data=f.structured_data,
            reference_number=f.reference_number,
            submitted_at=f.submitted_at.isoformat() if f.submitted_at else None,
            submitted_by=f.submitted_by,
            confirmed_at=f.confirmed_at.isoformat() if f.confirmed_at else None,
            confirmed_by=f.confirmed_by,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
        )
        for f in filings
    ]


@router.get("/api/v1/filings/{filing_id}", response_model=FilingResponse, tags=["Filings"])
def get_filing(
    filing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific filing by ID."""
    filing = db.query(Filing).filter(Filing.id == filing_id, Filing.tenant_id == current_user.tenant_id).first()
    if not filing:
        raise HTTPException(404, "Filing not found")

    return FilingResponse(
        id=filing.id,
        case_id=filing.case_id,
        filing_type=filing.filing_type,
        status=filing.status,
        deadline=filing.deadline.isoformat() if filing.deadline else None,
        narrative=filing.narrative,
        structured_data=filing.structured_data,
        reference_number=filing.reference_number,
        submitted_at=filing.submitted_at.isoformat() if filing.submitted_at else None,
        submitted_by=filing.submitted_by,
        confirmed_at=filing.confirmed_at.isoformat() if filing.confirmed_at else None,
        confirmed_by=filing.confirmed_by,
        created_at=filing.created_at.isoformat(),
        updated_at=filing.updated_at.isoformat(),
    )


@router.patch("/api/v1/filings/{filing_id}", response_model=FilingResponse, tags=["Filings"])
def update_filing(
    filing_id: str,
    update: FilingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a filing (narrative, status, reference number).

    S7.3: For submitted/confirmed filings, narrative changes create a new version instead of modifying in place.
    Requires amendment_reason for amendments.
    """
    filing = db.query(Filing).filter(Filing.id == filing_id, Filing.tenant_id == current_user.tenant_id).first()
    if not filing:
        raise HTTPException(404, "Filing not found")

    # Track if we create a version (to avoid double-audit)
    version_created = False
    old_status = filing.status

    # S7.3: If filing is submitted/confirmed and narrative is being changed, create a version
    if filing.status in ("submitted", "confirmed") and update.narrative is not None and update.narrative != filing.narrative:
        # Require amendment_reason
        if not update.amendment_reason:
            raise HTTPException(400, "amendment_reason is required when amending submitted/confirmed filings")

        # Get the latest version number for this filing
        latest_version = db.query(FilingVersion).filter(
            FilingVersion.filing_id == filing_id
        ).order_by(FilingVersion.version_number.desc()).first()

        next_version_num = (latest_version.version_number + 1) if latest_version else 1

        # Create a new version record
        version = FilingVersion(
            filing_id=filing_id,
            tenant_id=current_user.tenant_id,
            version_number=next_version_num,
            narrative=update.narrative,
            changed_by=current_user.id,
            change_reason=update.amendment_reason,
        )
        db.add(version)
        version_created = True

        # Update the filing's narrative
        filing.narrative = update.narrative

        # Audit the version creation
        db.add(AuditLog(
            user_id=current_user.id,
            action="filing_version_created",
            resource_type="filing",
            resource_id=filing.id,
            details={"version_number": next_version_num, "fields": ["narrative"], "reason": update.amendment_reason},
        ))
    else:
        # Normal update path (not submitted/confirmed, or no narrative change)
        if update.narrative is not None:
            filing.narrative = update.narrative

    if update.status is not None:
        if update.status in ("submitted", "confirmed"):
            permissions.require(current_user, "supervisor")  # submission to a regulator is an approval

        filing.status = update.status

        # S7.3: Snapshot narrative as version 1 when filing becomes submitted
        if update.status == "submitted" and old_status != "submitted":
            filing.submitted_at = datetime.utcnow()
            filing.submitted_by = current_user.id

            # Create version 1 snapshot
            version = FilingVersion(
                filing_id=filing.id,
                tenant_id=current_user.tenant_id,
                version_number=1,
                narrative=filing.narrative,
                changed_by=current_user.id,
                change_reason="Initial submission snapshot",
            )
            db.add(version)
            version_created = True

            db.add(AuditLog(
                user_id=current_user.id,
                action="filing_version_created",
                resource_type="filing",
                resource_id=filing.id,
                details={"version_number": 1, "fields": ["narrative"], "reason": "Initial submission snapshot"},
            ))

            webhooks.emit(db, current_user.tenant_id, "filing.submitted",
                          {"filing_id": filing.id, "case_id": filing.case_id, "filing_type": filing.filing_type},
                          user_id=current_user.id)

        # Track confirmation
        if update.status == "confirmed" and old_status != "confirmed":
            filing.confirmed_at = datetime.utcnow()
            filing.confirmed_by = current_user.id

    if update.reference_number is not None:
        filing.reference_number = update.reference_number

    filing.updated_at = datetime.utcnow()

    # Audit log (only if we didn't already audit a version creation)
    if not version_created:
        db.add(AuditLog(
            user_id=current_user.id,
            action="filing_updated",
            resource_type="filing",
            resource_id=filing.id,
            # field names and status only: the narrative may name people and the log cannot be edited
            details={"fields": sorted(update.model_dump(exclude_unset=True)), "status": update.status},
        ))

    db.commit()
    db.refresh(filing)

    return FilingResponse(
        id=filing.id,
        case_id=filing.case_id,
        filing_type=filing.filing_type,
        status=filing.status,
        deadline=filing.deadline.isoformat() if filing.deadline else None,
        narrative=filing.narrative,
        structured_data=filing.structured_data,
        reference_number=filing.reference_number,
        submitted_at=filing.submitted_at.isoformat() if filing.submitted_at else None,
        submitted_by=filing.submitted_by,
        confirmed_at=filing.confirmed_at.isoformat() if filing.confirmed_at else None,
        confirmed_by=filing.confirmed_by,
        created_at=filing.created_at.isoformat(),
        updated_at=filing.updated_at.isoformat(),
    )


@router.get("/api/v1/filings/{filing_id}/versions", tags=["Filings"])
def get_filing_versions(
    filing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the version history for a filing (S7.3)."""
    filing = db.query(Filing).filter(Filing.id == filing_id, Filing.tenant_id == current_user.tenant_id).first()
    if not filing:
        raise HTTPException(404, "Filing not found")

    versions = db.query(FilingVersion).filter(
        FilingVersion.filing_id == filing_id,
        FilingVersion.tenant_id == current_user.tenant_id
    ).order_by(FilingVersion.version_number.desc()).all()

    return [
        {
            "id": v.id,
            "filing_id": v.filing_id,
            "version_number": v.version_number,
            "narrative": v.narrative,
            "changed_by": v.changed_by,
            "changed_at": v.changed_at.isoformat(),
            "change_reason": v.change_reason,
        }
        for v in versions
    ]


@router.delete("/api/v1/filings/{filing_id}", tags=["Filings"])
def delete_filing(
    filing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a draft filing."""
    filing = db.query(Filing).filter(Filing.id == filing_id, Filing.tenant_id == current_user.tenant_id).first()
    if not filing:
        raise HTTPException(404, "Filing not found")

    if filing.status != "draft":
        raise HTTPException(400, "Only draft filings can be deleted")

    db.delete(filing)
    db.add(AuditLog(
        user_id=current_user.id,
        action="filing_deleted",
        resource_type="filing",
        resource_id=filing_id,
    ))
    db.commit()

    return {"deleted": filing_id}
