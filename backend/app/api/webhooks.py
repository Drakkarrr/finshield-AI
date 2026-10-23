"""FinShield AI — Webhooks (S4.2): subscriptions, delivery log, dead-letter replay.

Events are emitted by the platform at real lifecycle points (app.domain.webhooks.EVENT_TYPES); there
is no client-triggered dispatch. See app/domain/webhooks.py for the signature scheme.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crypto
from app.auth import get_current_user
from app.database import get_db
from app.db_models import AuditLog, User, WebhookEvent, WebhookSubscription
from app.domain import webhooks

router = APIRouter()


class SubscriptionCreate(BaseModel):
    url: str = Field(min_length=8)
    events: list[str] = Field(default_factory=lambda: ["*"])


def _sub(s: WebhookSubscription) -> dict:
    return {"id": s.id, "url": s.url, "events": s.events, "active": s.active, "created_by": s.created_by,
            "created_at": s.created_at.isoformat() if s.created_at else None}


def _event(e: WebhookEvent) -> dict:
    return {"id": e.id, "subscription_id": e.subscription_id, "event_type": e.event_type, "payload": e.payload,
            "status": e.status, "attempts": e.attempts, "response_code": e.response_code,
            "last_error": e.last_error, "next_retry_at": e.next_retry_at.isoformat() if e.next_retry_at else None,
            "attempt_log": e.attempt_log or [], "created_at": e.created_at.isoformat() if e.created_at else None,
            "delivered_at": e.delivered_at.isoformat() if e.delivered_at else None}


@router.get("/api/v1/webhooks/subscriptions", tags=["Webhooks"])
def list_subscriptions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(WebhookSubscription).filter(WebhookSubscription.tenant_id == current_user.tenant_id).all()
    return [_sub(s) for s in rows]


@router.post("/api/v1/webhooks/subscriptions", status_code=201, tags=["Webhooks"])
def create_subscription(req: SubscriptionCreate, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Subscribe an endpoint. The signing secret is returned ONCE; it is stored encrypted."""
    unknown = sorted(set(req.events) - set(webhooks.EVENT_TYPES) - {"*"})
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown event types: {unknown}")
    try:
        webhooks.check_target(db, req.url)
    except webhooks.TargetNotAllowed as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    secret = webhooks.new_secret()
    sub = WebhookSubscription(url=req.url, events=req.events, secret_enc=crypto.encrypt_json(secret), active=True,
                              created_by=current_user.id)
    db.add(sub)
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action="webhook_subscribed", resource_type="webhook_subscription",
                    resource_id=sub.id, details={"events": req.events}))
    db.commit()
    return {**_sub(sub), "secret": secret, "event_types": list(webhooks.EVENT_TYPES)}


@router.delete("/api/v1/webhooks/subscriptions/{subscription_id}", tags=["Webhooks"])
def delete_subscription(subscription_id: str, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    sub = db.query(WebhookSubscription).filter(WebhookSubscription.id == subscription_id,
                                               WebhookSubscription.tenant_id == current_user.tenant_id).first()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.active = False  # kept so the delivery log still resolves
    db.add(AuditLog(user_id=current_user.id, action="webhook_unsubscribed", resource_type="webhook_subscription",
                    resource_id=sub.id))
    db.commit()
    return {"id": sub.id, "active": False}


@router.get("/api/v1/webhooks", tags=["Webhooks"])
def list_webhook_events(
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delivery log, newest first; status=dead_letter lists the dead-letter queue."""
    q = db.query(WebhookEvent).filter(WebhookEvent.tenant_id == current_user.tenant_id)
    if status:
        q = q.filter(WebhookEvent.status == status)
    if event_type:
        q = q.filter(WebhookEvent.event_type == event_type)
    total = q.count()
    rows = q.order_by(WebhookEvent.created_at.desc(), WebhookEvent.id).offset(offset).limit(limit).all()
    return {"total": total, "items": [_event(e) for e in rows]}


@router.post("/api/v1/webhooks/{event_id}/retry", tags=["Webhooks"])
def retry_webhook_event(event_id: str, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Replay a dead-lettered (or failed) delivery now."""
    ev = db.query(WebhookEvent).filter(WebhookEvent.id == event_id,
                                       WebhookEvent.tenant_id == current_user.tenant_id).first()
    if ev is None:
        raise HTTPException(status_code=404, detail="Webhook event not found")
    if ev.status not in ("dead_letter", "failed"):
        raise HTTPException(status_code=409, detail=f"Event is {ev.status}; only failed or dead_letter can be replayed")
    ev.status, ev.next_retry_at = "pending", None
    ev.attempt_log = [*(ev.attempt_log or []), {"replayed_by": current_user.id}]
    db.add(AuditLog(user_id=current_user.id, action="webhook_replayed", resource_type="webhook_event",
                    resource_id=ev.id))
    db.info.setdefault(webhooks.PENDING_KEY, []).append(ev.id)
    db.commit()
    db.refresh(ev)
    return _event(ev)
