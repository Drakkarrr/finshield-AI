"""Privacy and DSAR service (S3.3)."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db_models import (
    AuditLog,
    Case,
    CaseComment,
    CaseNote,
    DSARRequest,
    Filing,
    Notification,
    Transaction,
    User,
)


class PrivacyService:
    """Service for privacy operations: DSAR, data export, erasure, PII masking."""

    # PII fields that should be masked
    PII_FIELDS = {
        "email", "first_name", "last_name", "company", "phone",
        "sender_name", "receiver_name", "ip_address",
    }

    @staticmethod
    def mask_pii(data: Any, fields_to_mask: set[str] | None = None) -> Any:
        """Mask PII fields in data structure."""
        fields = fields_to_mask or PrivacyService.PII_FIELDS
        
        if isinstance(data, dict):
            return {
                k: PrivacyService._mask_value(k, v, fields) if k in fields else PrivacyService.mask_pii(v, fields)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [PrivacyService.mask_pii(item, fields) for item in data]
        return data

    @staticmethod
    def _mask_value(key: str, value: Any, fields: set[str]) -> Any:
        """Mask a single value based on its key."""
        if not isinstance(value, str):
            return "***"
        
        if key == "email":
            # Mask email: j***@example.com
            parts = value.split("@")
            if len(parts) == 2:
                return f"{parts[0][0]}***@{parts[1]}"
            return "***"
        elif key in ("first_name", "last_name", "sender_name", "receiver_name"):
            # Mask names: J*** D***
            words = value.split()
            return " ".join(f"{w[0]}***" if w else "" for w in words)
        elif key == "phone":
            # Mask phone: ***-***-1234
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return "***"
        elif key == "ip_address":
            # Mask IP: 192.168.***.***
            parts = value.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.***.***"
            return "***"
        
        return "***"

    @staticmethod
    def export_user_data(db: Session, user_id: str) -> dict:
        """Export all data for a user (DSAR access request)."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Collect all user data
        transactions = db.query(Transaction).filter(Transaction.user_id == user_id).all()
        cases = db.query(Case).filter(Case.user_id == user_id).all()
        notifications = db.query(Notification).filter(Notification.user_id == user_id).all()
        audit_logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).all()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "company": user.company,
                "plan": user.plan,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "transactions": [
                {
                    "id": tx.id,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "transaction_type": tx.transaction_type,
                    "sender_name": tx.sender_name,
                    "receiver_name": tx.receiver_name,
                    "destination_country": tx.destination_country,
                    "status": tx.status,
                    "risk_score": tx.risk_score,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                }
                for tx in transactions
            ],
            "cases": [
                {
                    "id": case.id,
                    "transaction_id": case.transaction_id,
                    "status": case.status,
                    "priority": case.priority,
                    "reason": case.reason,
                    "created_at": case.created_at.isoformat() if case.created_at else None,
                }
                for case in cases
            ],
            "notifications": [
                {
                    "id": notif.id,
                    "type": notif.type,
                    "title": notif.title,
                    "message": notif.message,
                    "is_read": notif.is_read,
                    "created_at": notif.created_at.isoformat() if notif.created_at else None,
                }
                for notif in notifications
            ],
            "audit_logs": [
                {
                    "id": log.id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in audit_logs
            ],
            "exported_at": datetime.utcnow().isoformat(),
            "record_counts": {
                "transactions": len(transactions),
                "cases": len(cases),
                "notifications": len(notifications),
                "audit_logs": len(audit_logs),
            },
        }

    @staticmethod
    def erase_user_data(
        db: Session,
        user_id: str,
        preserve_retention: bool = True,
    ) -> dict:
        """Erase user data while preserving legal retention requirements."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        records_affected = 0
        retention_preserved = []

        # Erase notifications (no retention requirement)
        notif_count = db.query(Notification).filter(Notification.user_id == user_id).delete()
        records_affected += notif_count

        # Erase case comments and notes (no retention requirement)
        user_cases = db.query(Case).filter(Case.user_id == user_id).all()
        for case in user_cases:
            comment_count = db.query(CaseComment).filter(CaseComment.case_id == case.id).delete()
            note_count = db.query(CaseNote).filter(CaseNote.case_id == case.id).delete()
            records_affected += comment_count + note_count

        # For transactions: anonymize PII but preserve transaction records for legal retention
        if preserve_retention:
            transactions = db.query(Transaction).filter(Transaction.user_id == user_id).all()
            for tx in transactions:
                # Anonymize PII fields
                tx.sender_name = f"ANONYMIZED_{tx.id[:8]}"
                tx.receiver_name = f"ANONYMIZED_{tx.id[8:16]}"
                tx.description = None
                records_affected += 1
            retention_preserved.append("transactions")

        # For cases: anonymize but preserve for audit
        if preserve_retention:
            for case in user_cases:
                case.reason = f"ANONYMIZED - Original reason removed per DSAR"
                case.resolution_summary = None
                records_affected += 1
            retention_preserved.append("cases")

        # Anonymize user record (don't delete to preserve audit trail)
        user.email = f"anonymized_{user_id}@deleted.local"
        user.first_name = "ANONYMIZED"
        user.last_name = "USER"
        user.company = None
        user.is_active = False
        records_affected += 1

        db.commit()

        return {
            "user_id": user_id,
            "records_affected": records_affected,
            "retention_preserved": retention_preserved,
            "erased_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def create_dsar_request(
        db: Session,
        user_id: str,
        request_type: str,
        reason: Optional[str] = None,
    ) -> DSARRequest:
        """Create a new DSAR request."""
        if request_type not in ("access", "erasure", "rectification", "portability"):
            raise ValueError(f"Invalid request type: {request_type}")

        dsar = DSARRequest(
            user_id=user_id,
            request_type=request_type,
            reason=reason,
            status="pending",
        )
        db.add(dsar)
        db.commit()
        db.refresh(dsar)
        return dsar

    @staticmethod
    def process_dsar_request(
        db: Session,
        dsar_id: str,
        processed_by: str,
    ) -> dict:
        """Process a DSAR request."""
        dsar = db.query(DSARRequest).filter(DSARRequest.id == dsar_id).first()
        if not dsar:
            raise ValueError(f"DSAR request {dsar_id} not found")

        if dsar.status != "pending":
            raise ValueError(f"DSAR request {dsar_id} is not pending (status: {dsar.status})")

        dsar.status = "processing"
        dsar.processed_by = processed_by
        db.commit()

        try:
            if dsar.request_type == "access":
                # Export user data
                data = PrivacyService.export_user_data(db, dsar.user_id)
                dsar.data_export_path = f"dsar_exports/{dsar.id}.json"
                dsar.records_affected = sum(data["record_counts"].values())
                
                # Save export to file (in production, this would be secure storage)
                export_dir = Path("dsar_exports")
                export_dir.mkdir(exist_ok=True)
                with open(export_dir / f"{dsar.id}.json", "w") as f:
                    json.dump(data, f, indent=2)

            elif dsar.request_type == "erasure":
                # Erase user data
                result = PrivacyService.erase_user_data(db, dsar.user_id)
                dsar.records_affected = result["records_affected"]
                dsar.retention_preserved = bool(result["retention_preserved"])

            dsar.status = "completed"
            dsar.processed_at = datetime.utcnow()
            db.commit()

            return {
                "dsar_id": dsar.id,
                "status": "completed",
                "records_affected": dsar.records_affected,
                "processed_at": dsar.processed_at.isoformat(),
            }

        except Exception as e:
            dsar.status = "denied"
            dsar.notes = f"Processing failed: {str(e)}"
            db.commit()
            raise
