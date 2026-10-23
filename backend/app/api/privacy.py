"""FinShield AI — Data privacy (GDPR) requests."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    AuditLog,
    User,
)

router = APIRouter()


# ============================================================
# DATA PRIVACY (GDPR)
# ============================================================

class DSARRequest(BaseModel):
    subject_email: str
    request_type: str  # access, erasure


@router.post("/api/v1/privacy/dsar", tags=["Privacy"])
def create_dsar_request(
    req: DSARRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Data Subject Access Request."""
    # In production, this would initiate a DSAR workflow
    # For now, we just log it

    db.add(AuditLog(
        user_id=current_user.id,
        action="dsar_request_created",
        resource_type="dsar",
        details={"subject_email": req.subject_email, "request_type": req.request_type},
    ))
    db.commit()

    return {
        "request_type": req.request_type,
        "subject_email": req.subject_email,
        "status": "received",
        "message": "DSAR request received. Will be processed within 30 days.",
    }


@router.get("/api/v1/privacy/pii-classification", tags=["Privacy"])
def get_pii_classification(
    current_user: User = Depends(get_current_user),
):
    """Get PII field classification."""
    return {
        "pii_fields": [
            "email", "first_name", "last_name", "company",
            "sender_name", "receiver_name",
        ],
        "regulated_data": [
            "transactions", "audit_logs", "cases", "filings",
        ],
        "system_data": [
            "id", "created_at", "updated_at", "status",
        ],
    }
