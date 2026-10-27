"""FinShield AI — Four-eyes approval workflow for detection changes (S7.4)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.db_models import AuditLog, ChangeRequest, User
from app.domain.models_registry import registry
from app.permissions import has_role

router = APIRouter()


class ChangeRequestOut(BaseModel):
    id: str
    tenant_id: str
    change_type: str
    resource_id: str
    proposed_by: str
    proposed_at: str
    approved_by: Optional[str]
    approved_at: Optional[str]
    status: str
    payload: dict
    reason: Optional[str]


def _out(cr: ChangeRequest) -> ChangeRequestOut:
    return ChangeRequestOut(
        id=cr.id,
        tenant_id=cr.tenant_id,
        change_type=cr.change_type,
        resource_id=cr.resource_id,
        proposed_by=cr.proposed_by,
        proposed_at=cr.proposed_at.isoformat(),
        approved_by=cr.approved_by,
        approved_at=cr.approved_at.isoformat() if cr.approved_at else None,
        status=cr.status,
        payload=cr.payload,
        reason=cr.reason,
    )


@router.get("/api/v1/change-requests", tags=["Change Requests"])
def list_change_requests(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List change requests for the tenant. Supervisors and admins can see all; others see only their own."""
    query = db.query(ChangeRequest).filter(ChangeRequest.tenant_id == current_user.tenant_id)
    if not has_role(current_user, "supervisor"):
        query = query.filter(ChangeRequest.proposed_by == current_user.id)
    if status:
        query = query.filter(ChangeRequest.status == status)
    return [_out(cr) for cr in query.order_by(ChangeRequest.proposed_at.desc()).all()]


@router.get("/api/v1/change-requests/{request_id}", tags=["Change Requests"])
def get_change_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single change request."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == request_id,
        ChangeRequest.tenant_id == current_user.tenant_id,
    ).first()
    if not cr:
        raise HTTPException(404, "Change request not found")
    if not has_role(current_user, "supervisor") and cr.proposed_by != current_user.id:
        raise HTTPException(403, "You can only view your own change requests")
    return _out(cr)


class ApproveRejectRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/api/v1/change-requests/{request_id}/approve", tags=["Change Requests"])
def approve_change_request(
    request_id: str,
    req: ApproveRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a pending change request. Must be a different supervisor or admin than the proposer."""
    if not has_role(current_user, "supervisor"):
        raise HTTPException(403, "Only supervisors and admins can approve change requests")

    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == request_id,
        ChangeRequest.tenant_id == current_user.tenant_id,
    ).first()
    if not cr:
        raise HTTPException(404, "Change request not found")
    if cr.status != "pending":
        raise HTTPException(409, f"Change request is already {cr.status}")
    if cr.proposed_by == current_user.id:
        raise HTTPException(422, "Cannot approve your own change request")

    cr.approved_by = current_user.id
    cr.approved_at = datetime.utcnow()
    cr.status = "approved"

    db.add(AuditLog(
        user_id=current_user.id,
        action="change_request_approved",
        resource_type="change_request",
        resource_id=cr.id,
        details={
            "change_type": cr.change_type,
            "resource_id": cr.resource_id,
            "proposed_by": cr.proposed_by,
        },
    ))

    # Execute the approved change
    if cr.change_type == "model_promote":
        try:
            registry.promote(db, cr.resource_id, current_user.id)
        except LookupError:
            raise HTTPException(404, "Model version not found") from None
    elif cr.change_type in ("rule_disable", "rule_override"):
        from app.db_models import RuleConfig
        config = db.query(RuleConfig).filter(
            RuleConfig.tenant_id == current_user.tenant_id,
            RuleConfig.rule_id == cr.resource_id,
        ).first()
        before = {
            "enabled": config.enabled if config else True,
            "custom_parameters": config.custom_parameters if config else None,
            "priority": config.priority if config else 100,
            "version": config.version if config else 0,
        }
        if not config:
            config = RuleConfig(user_id=current_user.id, rule_id=cr.resource_id, enabled=True, priority=100, version=0)
            db.add(config)
        # Apply the payload
        if "enabled" in cr.payload:
            config.enabled = cr.payload["enabled"]
        if "custom_parameters" in cr.payload:
            config.custom_parameters = cr.payload["custom_parameters"]
        if "priority" in cr.payload:
            config.priority = cr.payload["priority"]
        # The window is part of what was approved: a disable approved "until Friday" must lapse on
        # Friday, not become permanent. Stored as ISO strings (model_dump(mode="json")).
        for field in ("effective_from", "effective_to"):
            if field in cr.payload:
                value = cr.payload[field]
                setattr(config, field, datetime.fromisoformat(value) if value else None)
        config.version = (config.version or 0) + 1
        after = {
            "enabled": config.enabled,
            "custom_parameters": config.custom_parameters,
            "priority": config.priority,
            "version": config.version,
        }
        db.add(AuditLog(
            user_id=current_user.id,
            action="rule_updated",
            resource_type="rule",
            resource_id=cr.resource_id,
            details={"change_request_id": cr.id, "before": before, "after": after},
        ))

    db.commit()

    return _out(cr)


@router.post("/api/v1/change-requests/{request_id}/reject", tags=["Change Requests"])
def reject_change_request(
    request_id: str,
    req: ApproveRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a pending change request."""
    if not has_role(current_user, "supervisor"):
        raise HTTPException(403, "Only supervisors and admins can reject change requests")

    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == request_id,
        ChangeRequest.tenant_id == current_user.tenant_id,
    ).first()
    if not cr:
        raise HTTPException(404, "Change request not found")
    if cr.status != "pending":
        raise HTTPException(409, f"Change request is already {cr.status}")

    cr.approved_by = current_user.id
    cr.approved_at = datetime.utcnow()
    cr.status = "rejected"

    db.add(AuditLog(
        user_id=current_user.id,
        action="change_request_rejected",
        resource_type="change_request",
        resource_id=cr.id,
        details={
            "change_type": cr.change_type,
            "resource_id": cr.resource_id,
            "proposed_by": cr.proposed_by,
        },
    ))
    db.commit()

    return _out(cr)
