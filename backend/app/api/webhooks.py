"""FinShield AI — Webhook subscriptions API (S4.2)."""
import hashlib
import hmac
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.db_models import AuditLog, User, WebhookSubscription

router = APIRouter()


# ============================================================
# MODELS
# ============================================================

class WebhookCreateRequest(BaseModel):
    url: str
    event_types: list[str]  # ["transaction.blocked", "case.escalated", etc.]


class WebhookResponse(BaseModel):
    id: str
    url: str
    event_types: list[str]
    is_active: bool
    consecutive_failures: int
    delivery_count: int
    last_delivered_at: Optional[str]
    created_at: str


class WebhookReplayRequest(BaseModel):
    webhook_id: str


# ============================================================
# WEBHOOK SUBSCRIPTION MANAGEMENT
# ============================================================

@router.post("/api/v1/webhooks", response_model=WebhookResponse, tags=["Webhooks"])
def create_webhook(
    req: WebhookCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new webhook subscription."""
    # Validate URL
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")
    
    # Validate event types
    valid_events = {
        "transaction.blocked",
        "transaction.flagged",
        "transaction.approved",
        "case.created",
        "case.escalated",
        "case.resolved",
        "filing.submitted",
        "filing.accepted",
        "credit.low",
        "plan.changed",
    }
    
    for event_type in req.event_types:
        if event_type not in valid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type: {event_type}. Valid types: {', '.join(sorted(valid_events))}",
            )
    
    # Generate HMAC secret
    secret = secrets.token_urlsafe(32)
    
    webhook = WebhookSubscription(
        user_id=current_user.id,
        url=req.url,
        secret=secret,
        event_types=req.event_types,
    )
    db.add(webhook)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="webhook_created",
        resource_type="webhook",
        resource_id=webhook.id,
        details={"url": req.url, "event_types": req.event_types},
    )
    db.add(audit)
    db.commit()
    db.refresh(webhook)
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        event_types=webhook.event_types,
        is_active=webhook.is_active,
        consecutive_failures=webhook.consecutive_failures,
        delivery_count=webhook.delivery_count,
        last_delivered_at=webhook.last_delivered_at.isoformat() if webhook.last_delivered_at else None,
        created_at=webhook.created_at.isoformat(),
    )


@router.get("/api/v1/webhooks", tags=["Webhooks"])
def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all webhook subscriptions for the current user."""
    webhooks = db.query(WebhookSubscription).filter(
        WebhookSubscription.user_id == current_user.id
    ).all()
    
    return {
        "webhooks": [
            WebhookResponse(
                id=w.id,
                url=w.url,
                event_types=w.event_types,
                is_active=w.is_active,
                consecutive_failures=w.consecutive_failures,
                delivery_count=w.delivery_count,
                last_delivered_at=w.last_delivered_at.isoformat() if w.last_delivered_at else None,
                created_at=w.created_at.isoformat(),
            )
            for w in webhooks
        ]
    }


@router.get("/api/v1/webhooks/{webhook_id}", response_model=WebhookResponse, tags=["Webhooks"])
def get_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific webhook subscription."""
    webhook = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == webhook_id,
        WebhookSubscription.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        event_types=webhook.event_types,
        is_active=webhook.is_active,
        consecutive_failures=webhook.consecutive_failures,
        delivery_count=webhook.delivery_count,
        last_delivered_at=webhook.last_delivered_at.isoformat() if webhook.last_delivered_at else None,
        created_at=webhook.created_at.isoformat(),
    )


@router.delete("/api/v1/webhooks/{webhook_id}", tags=["Webhooks"])
def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a webhook subscription."""
    webhook = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == webhook_id,
        WebhookSubscription.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="webhook_deleted",
        resource_type="webhook",
        resource_id=webhook_id,
    )
    db.add(audit)
    
    db.delete(webhook)
    db.commit()
    
    return {"detail": "Webhook deleted"}


@router.post("/api/v1/webhooks/{webhook_id}/replay", tags=["Webhooks"])
def replay_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset webhook failure counter and reactivate."""
    webhook = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == webhook_id,
        WebhookSubscription.user_id == current_user.id,
    ).first()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    webhook.consecutive_failures = 0
    webhook.is_active = True
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="webhook_replayed",
        resource_type="webhook",
        resource_id=webhook_id,
    )
    db.add(audit)
    db.commit()
    
    return {
        "detail": "Webhook reactivated",
        "consecutive_failures": webhook.consecutive_failures,
        "is_active": webhook.is_active,
    }


# ============================================================
# WEBHOOK EVENT EMITTER
# ============================================================

def emit_webhook_event(db: Session, event_type: str, payload: dict):
    """Emit a webhook event to all subscribed users (S4.2)."""
    from app.worker.tasks import deliver_webhook
    
    # Find all active webhooks subscribed to this event type
    webhooks = db.query(WebhookSubscription).filter(
        WebhookSubscription.is_active == True,
    ).all()
    
    delivered = 0
    for webhook in webhooks:
        if event_type in webhook.event_types:
            # Queue webhook delivery task
            deliver_webhook.delay(webhook.id, event_type, payload)
            delivered += 1
    
    return {"delivered": delivered, "event_type": event_type}
