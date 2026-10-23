"""FinShield AI — Data privacy (GDPR) and DSAR requests (S3.3)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.db_models import DSARRequest as DSARRequestModel, User
from app.domain.privacy import PrivacyService

router = APIRouter()


# ============================================================
# DATA PRIVACY (GDPR) - S3.3
# ============================================================

class DSARRequestCreate(BaseModel):
    request_type: str  # access, erasure, rectification, portability
    reason: str | None = None


class DSARResponse(BaseModel):
    id: str
    request_type: str
    status: str
    reason: str | None
    requested_at: str
    processed_at: str | None
    records_affected: int | None


@router.post("/api/v1/privacy/dsar", tags=["Privacy"])
def create_dsar_request(
    req: DSARRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Data Subject Access Request."""
    try:
        dsar = PrivacyService.create_dsar_request(
            db=db,
            user_id=current_user.id,
            request_type=req.request_type,
            reason=req.reason,
        )
        return {
            "id": dsar.id,
            "request_type": dsar.request_type,
            "status": dsar.status,
            "requested_at": dsar.requested_at.isoformat(),
            "message": "DSAR request received. Will be processed within 30 days.",
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/v1/privacy/dsar", tags=["Privacy"])
def list_dsar_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List DSAR requests for the current user."""
    requests = (
        db.query(DSARRequestModel)
        .filter(DSARRequestModel.user_id == current_user.id)
        .order_by(DSARRequestModel.requested_at.desc())
        .all()
    )
    
    return {
        "requests": [
            {
                "id": r.id,
                "request_type": r.request_type,
                "status": r.status,
                "reason": r.reason,
                "requested_at": r.requested_at.isoformat(),
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "records_affected": r.records_affected,
            }
            for r in requests
        ],
        "count": len(requests),
    }


@router.get("/api/v1/privacy/dsar/{dsar_id}", tags=["Privacy"])
def get_dsar_request(
    dsar_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific DSAR request."""
    dsar = db.query(DSARRequestModel).filter(DSARRequestModel.id == dsar_id).first()
    if not dsar:
        raise HTTPException(404, "DSAR request not found")
    
    # Users can only see their own requests (admins can see all)
    if dsar.user_id != current_user.id and current_user.role not in ("admin", "super_admin"):
        raise HTTPException(403, "Not authorized to view this request")
    
    return {
        "id": dsar.id,
        "user_id": dsar.user_id,
        "request_type": dsar.request_type,
        "status": dsar.status,
        "reason": dsar.reason,
        "requested_at": dsar.requested_at.isoformat(),
        "processed_at": dsar.processed_at.isoformat() if dsar.processed_at else None,
        "processed_by": dsar.processed_by,
        "records_affected": dsar.records_affected,
        "retention_preserved": dsar.retention_preserved,
        "notes": dsar.notes,
    }


@router.post("/api/v1/privacy/dsar/{dsar_id}/process", tags=["Privacy"])
@require_role("admin", "super_admin")
def process_dsar_request(
    dsar_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process a DSAR request (admin only)."""
    try:
        result = PrivacyService.process_dsar_request(
            db=db,
            dsar_id=dsar_id,
            processed_by=current_user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/v1/privacy/export", tags=["Privacy"])
def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all personal data for the current user."""
    try:
        data = PrivacyService.export_user_data(db, current_user.id)
        return data
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/api/v1/privacy/mask", tags=["Privacy"])
@require_role("admin", "super_admin")
def mask_pii_in_data(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Mask PII fields in provided data (admin only)."""
    masked = PrivacyService.mask_pii(data)
    return {"masked_data": masked}


@router.get("/api/v1/privacy/pii-classification", tags=["Privacy"])
def get_pii_classification(
    current_user: User = Depends(get_current_user),
):
    """Get PII field classification."""
    return {
        "pii_fields": sorted(PrivacyService.PII_FIELDS),
        "regulated_data": [
            "transactions", "audit_logs", "cases", "filings",
        ],
        "system_data": [
            "id", "created_at", "updated_at", "status",
        ],
        "masking_examples": {
            "email": "j***@example.com",
            "first_name": "J***",
            "last_name": "D***",
            "phone": "***-***-1234",
            "ip_address": "192.168.***.***",
        },
    }
