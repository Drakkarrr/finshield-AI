"""FinShield AI — Webhook events."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    User,
    WebhookEvent,
)

router = APIRouter()


# ============================================================
# WEBHOOK EVENTS
# ============================================================

class WebhookRequest(BaseModel):
    event_type: str
    payload: dict


@router.post("/api/v1/webhooks/dispatch", tags=["Webhooks"])
def dispatch_webhook_event(
    req: WebhookRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dispatch a webhook event (queued for delivery)."""
    event = WebhookEvent(
        user_id=current_user.id,
        event_type=req.event_type,
        payload=req.payload,
        status="pending",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # In production, this would trigger async delivery via Celery
    # For now, we just queue it

    return {
        "event_id": event.id,
        "event_type": event.event_type,
        "status": event.status,
        "message": "Event queued for delivery",
    }


@router.get("/api/v1/webhooks", tags=["Webhooks"])
def list_webhook_events(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List webhook events for the current user."""
    query = db.query(WebhookEvent).filter(WebhookEvent.tenant_id == current_user.tenant_id)

    if status:
        query = query.filter(WebhookEvent.status == status)

    events = query.order_by(WebhookEvent.created_at.desc()).limit(100).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "status": e.status,
            "attempts": e.attempts,
            "last_attempt_at": e.last_attempt_at.isoformat() if e.last_attempt_at else None,
            "last_error": e.last_error,
            "created_at": e.created_at.isoformat(),
            "delivered_at": e.delivered_at.isoformat() if e.delivered_at else None,
        }
        for e in events
    ]


@router.post("/api/v1/webhooks/{event_id}/retry", tags=["Webhooks"])
def retry_webhook_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed webhook event."""
    event = db.query(WebhookEvent).filter(
        WebhookEvent.id == event_id,
        WebhookEvent.tenant_id == current_user.tenant_id
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    if event.status not in ["failed", "dead_letter"]:
        raise HTTPException(400, "Only failed events can be retried")

    event.status = "pending"
    event.attempts = 0
    event.last_error = None
    event.next_retry_at = None
    db.commit()

    return {"event_id": event_id, "status": "pending", "message": "Event queued for retry"}
