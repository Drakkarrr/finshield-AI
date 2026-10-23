"""FinShield AI — Notifications and notification preferences."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
)
from app.database import get_db
from app.db_models import (
    Notification,
    NotificationPreference,
    User,
)

router = APIRouter()


# ============================================================
# NOTIFICATIONS
# ============================================================

@router.get("/api/v1/notifications", tags=["Notifications"])
def list_notifications(
    limit: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications for the current user."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    notifs = query.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).count()
    return {
        "notifications": [
            {"id": n.id, "type": n.type, "title": n.title, "message": n.message, "is_read": n.is_read, "link": n.link, "created_at": n.created_at.isoformat()}
            for n in notifs
        ],
        "unread_count": unread_count,
    }


@router.patch("/api/v1/notifications/{notif_id}/read", tags=["Notifications"])
def mark_notification_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notif_id, Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"detail": "Marked as read"}


@router.post("/api/v1/notifications/read-all", tags=["Notifications"])
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"detail": "All notifications marked as read"}


# ============================================================
# NOTIFICATION PREFERENCES
# ============================================================

@router.get("/api/v1/notifications/preferences", tags=["Notifications"])
def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get notification preferences."""
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not prefs:
        # Create defaults
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return {
        "email_blocked_tx": prefs.email_blocked_tx,
        "email_new_cases": prefs.email_new_cases,
        "email_daily_summary": prefs.email_daily_summary,
        "email_weekly_report": prefs.email_weekly_report,
        "email_system_downtime": prefs.email_system_downtime,
        "email_credit_alerts": prefs.email_credit_alerts,
    }


class NotificationPreferencesUpdate(BaseModel):
    email_blocked_tx: Optional[bool] = None
    email_new_cases: Optional[bool] = None
    email_daily_summary: Optional[bool] = None
    email_weekly_report: Optional[bool] = None
    email_system_downtime: Optional[bool] = None
    email_credit_alerts: Optional[bool] = None


@router.put("/api/v1/notifications/preferences", tags=["Notifications"])
def update_notification_preferences(
    req: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update notification preferences."""
    prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)
    db.commit()
    return {"detail": "Preferences updated"}
