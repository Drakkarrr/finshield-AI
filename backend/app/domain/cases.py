"""Case SLA: deadline by severity and the escalation sweep (S4.3). Idempotent and safe to re-run."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import config_service
from app.db_models import AuditLog, Case, Notification
from app.domain import webhooks

OPEN_STATUSES = ("created", "open", "under_review")


def sla_deadline(db: Session, severity: str, now: Optional[datetime] = None) -> datetime:
    hours = config_service.get_setting(db, "cases.sla_hours")
    return (now or datetime.utcnow()) + timedelta(hours=float(hours.get(severity, hours["medium"])))


def sla_sweep(db: Session, tenant_id: str, now: Optional[datetime] = None) -> dict:
    """Escalate breached cases (notification + sla.breached webhook + audit) and notify once about
    cases approaching their deadline. Re-running changes nothing new."""
    now = now or datetime.utcnow()
    soon = now + timedelta(minutes=float(config_service.get_setting(db, "sla.approaching_minutes")))
    open_cases = db.query(Case).filter(Case.tenant_id == tenant_id, Case.status.in_(OPEN_STATUSES),
                                       Case.sla_deadline.isnot(None), Case.escalated_at.is_(None))
    escalated = 0
    for case in open_cases.filter(Case.sla_deadline <= now).all():
        deadline = case.sla_deadline
        case.status, case.escalated_at, case.escalated_by = "escalated", now, "system"
        case.escalation_reason = f"SLA breached. Deadline was {deadline.isoformat() if deadline else '?'}"
        db.add(Notification(tenant_id=tenant_id, user_id=case.user_id, type="sla_breached", title="SLA breached",
                            message=f"Case {case.id} passed its SLA deadline and was escalated.", link="/cases"))
        db.add(AuditLog(tenant_id=tenant_id, user_id=None, action="case_escalated", resource_type="case",
                        resource_id=case.id, details={"reason": "sla_breached", "by": "system"}))
        webhooks.emit(db, tenant_id, "sla.breached", {"case_id": case.id, "severity": case.severity,
                                                       "deadline": deadline.isoformat() if deadline else None})
        escalated += 1
    warned = 0
    for case in open_cases.filter(Case.sla_deadline > now, Case.sla_deadline <= soon).all():
        link = f"/cases?case={case.id}"
        if db.query(Notification).filter(Notification.type == "sla_approaching", Notification.link == link).first():
            continue
        db.add(Notification(tenant_id=tenant_id, user_id=case.user_id, type="sla_approaching", title="SLA approaching",
                            message=f"Case {case.id} reaches its SLA deadline at "
                                    f"{case.sla_deadline.isoformat() if case.sla_deadline else '?'}.",
                            link=link))
        warned += 1
    db.commit()
    return {"escalated": escalated, "approaching_notified": warned}
