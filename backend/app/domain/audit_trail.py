"""Immutable audit trail service with hash chain (S3.2)."""

import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import AuditLog


class AuditTrailService:
    """Service for immutable audit logging with hash chain."""

    @staticmethod
    def compute_entry_hash(
        entry_id: str,
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        details: Optional[dict],
        ip_address: Optional[str],
        created_at: datetime,
        prev_hash: Optional[str],
        chain_sequence: int,
    ) -> str:
        """Compute SHA-256 hash for an audit log entry."""
        # Serialize all fields in deterministic order
        data = {
            "id": entry_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "created_at": created_at.isoformat(),
            "prev_hash": prev_hash,
            "chain_sequence": chain_sequence,
        }
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @staticmethod
    def get_next_sequence(db: Session) -> int:
        """Get the next chain sequence number."""
        max_seq = db.query(func.max(AuditLog.chain_sequence)).scalar()
        return (max_seq or 0) + 1

    @staticmethod
    def get_last_hash(db: Session) -> Optional[str]:
        """Get the hash of the last audit log entry."""
        last_entry = (
            db.query(AuditLog)
            .order_by(AuditLog.chain_sequence.desc())
            .first()
        )
        return last_entry.entry_hash if last_entry else None

    @staticmethod
    def log_action(
        db: Session,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create an immutable audit log entry with hash chain."""
        # Get next sequence and previous hash
        chain_sequence = AuditTrailService.get_next_sequence(db)
        prev_hash = AuditTrailService.get_last_hash(db)

        # Create entry
        entry_id = f"audit-{chain_sequence}"
        created_at = datetime.utcnow()

        # Compute hash
        entry_hash = AuditTrailService.compute_entry_hash(
            entry_id=entry_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            created_at=created_at,
            prev_hash=prev_hash,
            chain_sequence=chain_sequence,
        )

        # Create audit log entry
        log_entry = AuditLog(
            id=entry_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            chain_sequence=chain_sequence,
            created_at=created_at,
        )

        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        return log_entry

    @staticmethod
    def verify_chain_integrity(db: Session) -> dict:
        """Verify the integrity of the entire audit chain."""
        logs = db.query(AuditLog).order_by(AuditLog.chain_sequence.asc()).all()

        if not logs:
            return {"valid": True, "message": "No audit logs to verify", "count": 0}

        issues = []
        prev_hash = None

        for log in logs:
            # Verify sequence is continuous
            expected_seq = logs.index(log) + 1
            if log.chain_sequence != expected_seq:
                issues.append(f"Sequence gap at {log.id}: expected {expected_seq}, got {log.chain_sequence}")

            # Verify prev_hash matches
            if log.prev_hash != prev_hash:
                issues.append(f"Hash chain broken at {log.id}: prev_hash mismatch")

            # Verify entry hash
            expected_hash = AuditTrailService.compute_entry_hash(
                entry_id=log.id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                created_at=log.created_at,
                prev_hash=log.prev_hash,
                chain_sequence=log.chain_sequence,
            )
            if log.entry_hash != expected_hash:
                issues.append(f"Entry hash invalid at {log.id}")

            prev_hash = log.entry_hash

        return {
            "valid": len(issues) == 0,
            "count": len(logs),
            "issues": issues[:10],  # Limit to first 10 issues
            "message": "Chain integrity verified" if not issues else f"Found {len(issues)} issues",
        }

    @staticmethod
    def export_audit_log(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> list[dict]:
        """Export audit logs with optional filters."""
        query = db.query(AuditLog)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)

        logs = query.order_by(AuditLog.chain_sequence.asc()).all()

        return [
            {
                "id": log.id,
                "sequence": log.chain_sequence,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "prev_hash": log.prev_hash,
                "entry_hash": log.entry_hash,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
