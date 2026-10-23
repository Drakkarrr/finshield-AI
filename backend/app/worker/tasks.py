"""FinShield AI — Celery tasks (S4.1, S4.3)."""
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.db_models import (
    AuditLog,
    Case,
    DSARRequest,
    Notification,
    User,
)

logger = get_task_logger(__name__)


def get_db() -> Session:
    """Get database session for task."""
    return SessionLocal()


# ============================================================
# SLA MANAGEMENT (S4.3)
# ============================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def sla_sweep(self):
    """Check for cases approaching or exceeding SLA deadlines."""
    db = get_db()
    try:
        now = datetime.utcnow()
        
        # Find cases with SLA deadlines in next 2 hours
        upcoming = db.query(Case).filter(
            Case.status.in_(["open", "under_review"]),
            Case.sla_deadline.isnot(None),
            Case.sla_deadline <= now + timedelta(hours=2),
            Case.sla_deadline > now,
        ).all()
        
        for case in upcoming:
            hours_left = (case.sla_deadline - now).total_seconds() / 3600
            logger.info(f"Case {case.id} SLA due in {hours_left:.1f} hours")
            
            # Send notification to assigned user
            if case.assigned_to:
                notif = Notification(
                    user_id=case.assigned_to,
                    type="sla_warning",
                    title=f"SLA warning: Case {case.id[:8]}",
                    message=f"Case will breach SLA in {hours_left:.1f} hours",
                    link=f"/cases/{case.id}",
                )
                db.add(notif)
        
        # Find cases that have breached SLA
        breached = db.query(Case).filter(
            Case.status.in_(["open", "under_review"]),
            Case.sla_deadline.isnot(None),
            Case.sla_deadline < now,
        ).all()
        
        for case in breached:
            logger.warning(f"Case {case.id} SLA BREACHED")
            
            # Auto-escalate if not already escalated
            if case.status != "escalated":
                case.status = "escalated"
                case.escalated_at = now
                case.escalation_reason = "SLA deadline breached (automated)"
                
                # Notify assigned user
                if case.assigned_to:
                    notif = Notification(
                        user_id=case.assigned_to,
                        type="sla_breach",
                        title=f"SLA breached: Case {case.id[:8]}",
                        message="Case has been auto-escalated due to SLA breach",
                        link=f"/cases/{case.id}",
                    )
                    db.add(notif)
        
        db.commit()
        return {"upcoming": len(upcoming), "breached": len(breached)}
    
    except Exception as exc:
        logger.error(f"SLA sweep failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# BEHAVIORAL BASELINE RECOMPUTE (S4.3)
# ============================================================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def recompute_behavioral_baselines(self):
    """Recompute behavioral baselines for all active users (daily job)."""
    db = get_db()
    try:
        from app.domain.behavioral.monitor import BehavioralMonitor
        
        monitor = BehavioralMonitor(db)
        active_users = db.query(User).filter(User.is_active == True).all()
        
        recomputed = 0
        for user in active_users:
            try:
                monitor.recompute_baseline(user.id)
                recomputed += 1
            except Exception as e:
                logger.warning(f"Failed to recompute baseline for user {user.id}: {e}")
        
        db.commit()
        logger.info(f"Recomputed baselines for {recomputed} users")
        return {"recomputed": recomputed}
    
    except Exception as exc:
        logger.error(f"Baseline recompute failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# DSAR PROCESSING (S4.3)
# ============================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_pending_dsar_requests(self):
    """Process pending DSAR (Data Subject Access Requests)."""
    db = get_db()
    try:
        from app.domain.privacy import PrivacyService
        
        privacy_service = PrivacyService(db)
        
        pending = db.query(DSARRequest).filter(
            DSARRequest.status == "received"
        ).all()
        
        processed = 0
        for request in pending:
            try:
                privacy_service.process_dsar_request(request.id)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process DSAR {request.id}: {e}")
                request.status = "failed"
                request.notes = f"Processing failed: {str(e)}"
        
        db.commit()
        logger.info(f"Processed {processed} DSAR requests")
        return {"processed": processed}
    
    except Exception as exc:
        logger.error(f"DSAR processing failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# AUDIT CHAIN VERIFICATION (S4.3)
# ============================================================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def verify_audit_chain_integrity(self):
    """Verify audit log hash chain integrity."""
    db = get_db()
    try:
        from app.api.audit import verify_chain
        
        result = verify_chain(db)
        
        if not result["valid"]:
            logger.error(f"Audit chain integrity check FAILED: {result['errors']}")
            
            # Create critical notification for admins
            admins = db.query(User).filter(User.role.in_(["admin", "super_admin"])).all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    type="security_alert",
                    title="Audit chain integrity breach",
                    message=f"Chain verification failed with {len(result['errors'])} errors",
                    link="/admin/audit",
                )
                db.add(notif)
            
            db.commit()
        else:
            logger.info(f"Audit chain verified: {result['total_entries']} entries, integrity OK")
        
        return result
    
    except Exception as exc:
        logger.error(f"Chain verification failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# WEBHOOK DELIVERY (S4.2)
# ============================================================

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600,
)
def deliver_webhook(self, webhook_id: str, event_type: str, payload: dict):
    """Deliver webhook to subscriber with HMAC signing and retry logic."""
    import hashlib
    import hmac
    
    import httpx
    
    db = get_db()
    try:
        # Import here to avoid circular dependency
        from app.db_models import WebhookSubscription
        
        webhook = db.query(WebhookSubscription).filter(
            WebhookSubscription.id == webhook_id
        ).first()
        
        if not webhook or not webhook.is_active:
            logger.warning(f"Webhook {webhook_id} not found or inactive")
            return {"status": "skipped", "reason": "not_found_or_inactive"}
        
        # Sign payload with HMAC
        payload_bytes = str(payload).encode("utf-8")
        signature = hmac.new(
            webhook.secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Event": event_type,
        }
        
        # Deliver webhook
        response = httpx.post(
            webhook.url,
            json=payload,
            headers=headers,
            timeout=10.0,
        )
        
        # Update delivery status
        webhook.last_delivered_at = datetime.utcnow()
        webhook.delivery_count += 1
        
        if response.status_code >= 200 and response.status_code < 300:
            webhook.consecutive_failures = 0
            logger.info(f"Webhook {webhook_id} delivered successfully")
            return {"status": "delivered", "code": response.status_code}
        else:
            webhook.consecutive_failures += 1
            logger.warning(f"Webhook {webhook_id} delivery failed: {response.status_code}")
            
            # Deactivate after 10 consecutive failures
            if webhook.consecutive_failures >= 10:
                webhook.is_active = False
                logger.error(f"Webhook {webhook_id} deactivated after 10 failures")
            
            db.commit()
            raise Exception(f"Delivery failed with status {response.status_code}")
    
    except Exception as exc:
        logger.error(f"Webhook delivery error: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# FILING REMINDERS (S4.3)
# ============================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_filing_reminders(self):
    """Send reminders for pending filings approaching deadlines."""
    db = get_db()
    try:
        from app.db_models import Filing
        
        # Find filings that are draft or under_review for more than 3 days
        cutoff_date = datetime.utcnow() - timedelta(days=3)
        
        pending_filings = db.query(Filing).filter(
            Filing.status.in_(["draft", "under_review"]),
            Filing.created_at < cutoff_date,
        ).all()
        
        reminded = 0
        for filing in pending_filings:
            # Check if we already sent a reminder in the last 24 hours
            last_reminder = db.query(AuditLog).filter(
                AuditLog.resource_type == "filing",
                AuditLog.resource_id == filing.id,
                AuditLog.action == "filing_reminder_sent",
                AuditLog.created_at > datetime.utcnow() - timedelta(hours=24),
            ).first()
            
            if not last_reminder:
                # Send notification to filing user
                notif = Notification(
                    user_id=filing.user_id,
                    type="filing_reminder",
                    title=f"Filing reminder: {filing.filing_type}",
                    message=f"Your {filing.filing_type} filing has been pending for review. Please complete or submit.",
                    link=f"/filings/{filing.id}",
                )
                db.add(notif)
                
                # Log reminder
                audit = AuditLog(
                    user_id=filing.user_id,
                    action="filing_reminder_sent",
                    resource_type="filing",
                    resource_id=filing.id,
                )
                db.add(audit)
                reminded += 1
        
        db.commit()
        logger.info(f"Sent {reminded} filing reminders")
        return {"reminded": reminded}
    
    except Exception as exc:
        logger.error(f"Filing reminders failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# SANCTIONS LIST REFRESH (S4.3)
# ============================================================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def refresh_sanctions_lists(self):
    """Refresh sanctions/PEP lists from external sources (weekly job)."""
    db = get_db()
    try:
        from app.db_models import SanctionsEntry, PEPEntry
        from app.domain.lists.ofac_importer import seed_sample_sanctions
        
        # In production, this would fetch from OFAC, UN, EU, etc.
        # For now, we just log that the job ran and check list counts
        
        sanctions_count = db.query(SanctionsEntry).count()
        pep_count = db.query(PEPEntry).count()
        
        logger.info(f"List refresh check: {sanctions_count} sanctions entries, {pep_count} PEP entries")
        
        # If lists are empty, seed sample data
        if sanctions_count == 0:
            imported = seed_sample_sanctions(db)
            logger.info(f"Seeded {imported} sample sanctions entries")
            return {"sanctions_count": imported, "pep_count": pep_count, "seeded": True}
        
        return {
            "sanctions_count": sanctions_count,
            "pep_count": pep_count,
            "seeded": False,
        }
    
    except Exception as exc:
        logger.error(f"List refresh failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    
    finally:
        db.close()


# ============================================================
# HEALTH CHECK
# ============================================================

@shared_task
def health_check():
    """Simple health check task to verify worker is alive."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "finshield-worker",
    }
