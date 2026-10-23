"""FinShield AI — Audit trail API (S3.2)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.db_models import User
from app.domain.audit_trail import AuditTrailService

router = APIRouter()


@router.get("/api/v1/audit/logs", tags=["Audit"])
@require_role("admin", "super_admin")
def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: str | None = None,
    action: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit logs with optional filters (admin only)."""
    query = db.query(AuditTrailService)
    
    # Apply filters
    from app.db_models import AuditLog
    query = db.query(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    logs = query.order_by(AuditLog.chain_sequence.desc()).offset(offset).limit(limit).all()
    
    return {
        "logs": [
            {
                "id": log.id,
                "sequence": log.chain_sequence,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "entry_hash": log.entry_hash,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "count": len(logs),
    }


@router.get("/api/v1/audit/export", tags=["Audit"])
@require_role("admin", "super_admin")
def export_audit_logs(
    user_id: str | None = None,
    action: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export audit logs as JSON (admin only)."""
    logs = AuditTrailService.export_audit_log(
        db=db,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action=action,
    )
    
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "count": len(logs),
        "logs": logs,
    }


@router.get("/api/v1/audit/verify", tags=["Audit"])
@require_role("admin", "super_admin")
def verify_audit_chain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify audit chain integrity (admin only)."""
    result = AuditTrailService.verify_chain_integrity(db)
    
    if not result["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Audit chain integrity check failed: {result['message']}",
        )
    
    return result


@router.get("/api/v1/audit/stats", tags=["Audit"])
@require_role("admin", "super_admin")
def get_audit_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit log statistics (admin only)."""
    from app.db_models import AuditLog
    from sqlalchemy import func
    
    total = db.query(AuditLog).count()
    latest = db.query(AuditLog).order_by(AuditLog.chain_sequence.desc()).first()
    
    # Count by action type
    action_counts = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .all()
    )
    
    return {
        "total_entries": total,
        "latest_sequence": latest.chain_sequence if latest else 0,
        "latest_timestamp": latest.created_at.isoformat() if latest else None,
        "action_breakdown": {action: count for action, count in action_counts},
    }
