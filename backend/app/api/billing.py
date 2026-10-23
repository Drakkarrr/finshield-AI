"""FinShield AI — Credits, plans, subscriptions and checkout."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config_service
from app.auth import (
    get_current_user,
)
from app.core import logger
from app.database import get_db
from app.db_models import (
    AuditLog,
    Notification,
    User,
)
from app.models import (
    CreditsResponse,
)

router = APIRouter()


# ============================================================
# ACCOUNT ROUTES
# ============================================================

@router.get("/api/v1/credits", response_model=CreditsResponse, tags=["Account"])
def get_credits(current_user: User = Depends(get_current_user)):
    """Get current credit balance."""
    return CreditsResponse(
        total_credits=current_user.total_credits,
        used_credits=round(current_user.used_credits),
        remaining_credits=current_user.total_credits - round(current_user.used_credits),
        plan=current_user.plan,
    )


# ============================================================
# BILLING & SUBSCRIPTION
# ============================================================

def _plans(db: Session) -> list[dict]:
    return config_service.get_setting(db, "billing.plans")


def _credit_packs(db: Session) -> dict[int, float]:
    """Runtime setting stores JSON (string keys); callers look packs up by credit count."""
    return {int(k): v for k, v in config_service.get_setting(db, "billing.credit_packs").items()}


class SubscribeRequest(BaseModel):
    plan_id: str


class PurchaseRequest(BaseModel):
    credits: int


class CheckoutRequest(BaseModel):
    credits: int
    card_last4: str
    card_expiry: str
    card_holder: str


@router.get("/api/v1/billing/plans", tags=["Billing"])
def list_plans(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List available subscription plans."""
    # Calculate days remaining: billing cycle if paid, else trial expiry
    days_remaining = None
    cycle_end = current_user.billing_cycle_end
    if cycle_end:
        days_remaining = max(0, (cycle_end - datetime.utcnow()).days)
    elif current_user.is_trial and current_user.trial_expires_at:
        days_remaining = max(0, (current_user.trial_expires_at - datetime.utcnow()).days)
    return {
        "plans": _plans(db),
        "current_plan": current_user.plan,
        "billing_cycle_start": current_user.billing_cycle_start.isoformat() if current_user.billing_cycle_start else None,
        "billing_cycle_end": cycle_end.isoformat() if cycle_end else None,
        "days_remaining": days_remaining,
        "pending_plan_change": current_user.pending_plan_change,
        "is_trial": current_user.is_trial,
        "trial_expires_at": current_user.trial_expires_at.isoformat() if current_user.trial_expires_at else None,
    }


@router.post("/api/v1/billing/subscribe", tags=["Billing"])
def subscribe(
    req: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the account's subscription plan with real-world constraints."""
    plan = next((p for p in _plans(db) if p["id"] == req.plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    if plan["included_credits"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans require contacting sales")
    if plan["id"] == current_user.plan:
        raise HTTPException(status_code=400, detail="Already on this plan")

    current_plan = next((p for p in _plans(db) if p["id"] == current_user.plan), None)
    current_price = current_plan["price_monthly"] if current_plan else 0
    new_price = plan["price_monthly"]
    is_upgrade = new_price > (current_price or 0)

    # Initialize billing cycle if not set
    now = datetime.utcnow()
    if not current_user.billing_cycle_start:
        current_user.billing_cycle_start = now
        current_user.billing_cycle_end = now + timedelta(days=30)

    proration = 0
    if is_upgrade:
        # Upgrades take effect immediately with proration
        cycle_total_days = (current_user.billing_cycle_end - current_user.billing_cycle_start).days or 30
        days_left = max(1, (current_user.billing_cycle_end - now).days)
        proration = round((new_price - (current_price or 0)) * (days_left / cycle_total_days), 2)

        current_user.plan = plan["id"]
        current_user.is_trial = False
        current_user.trial_expires_at = None
        # Top up credits to new plan allowance
        if plan["included_credits"] > current_user.total_credits:
            current_user.total_credits = plan["included_credits"]

        # Create notification
        notif = Notification(
            user_id=current_user.id,
            type="plan_change",
            title="Plan upgraded",
            message=f"Upgraded to {plan['name']}. Prorated charge: ${proration}. Credits adjusted.",
            link="/settings?tab=billing",
        )
        db.add(notif)
    else:
        # Downgrades take effect at end of billing cycle
        current_user.pending_plan_change = plan["id"]

        notif = Notification(
            user_id=current_user.id,
            type="plan_change",
            title="Downgrade scheduled",
            message=f"Your plan will change to {plan['name']} at the end of your current billing cycle ({current_user.billing_cycle_end.strftime('%b %d, %Y')}).",
            link="/settings?tab=billing",
        )
        db.add(notif)

    audit = AuditLog(user_id=current_user.id, action="plan_subscribed",
                     resource_type="billing",
                     details={"plan": plan["id"], "is_upgrade": is_upgrade, "proration": proration if is_upgrade else None})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} {'upgraded' if is_upgrade else 'scheduled downgrade'} to plan: {plan['id']}")

    return {
        "plan": plan["id"],
        "is_upgrade": is_upgrade,
        "effective": "immediately" if is_upgrade else f"at end of cycle ({current_user.billing_cycle_end.strftime('%b %d, %Y') if current_user.billing_cycle_end else 'N/A'})",
        "proration_usd": proration if is_upgrade else 0,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "pending_plan_change": current_user.pending_plan_change,
        "message": f"{'Upgraded' if is_upgrade else 'Downgrade scheduled'} to {plan['name']}" + (f" (prorated ${proration})" if is_upgrade else ""),
    }


@router.post("/api/v1/credits/checkout", tags=["Billing"])
def checkout_credits(
    req: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulated payment checkout for credit purchase. Card data is not stored (S3.5)."""
    credit_packs = _credit_packs(db)
    if req.credits not in credit_packs:
        raise HTTPException(status_code=400, detail="Invalid credit pack")

    # Validate card details (not stored)
    if not req.card_last4 or len(req.card_last4) != 4 or not req.card_last4.isdigit():
        raise HTTPException(status_code=400, detail="Invalid card last 4 digits")
    if not req.card_expiry or "/" not in req.card_expiry:
        raise HTTPException(status_code=400, detail="Invalid card expiry format (MM/YY)")
    if not req.card_holder or len(req.card_holder.strip()) < 2:
        raise HTTPException(status_code=400, detail="Invalid card holder name")
    
    card_last4 = req.card_last4
    price = credit_packs[req.credits]

    # Simulate payment processing (in production, this would call Stripe/PayPal)
    # Simulate decline for card ending in 0000
    if card_last4 == "0000":
        raise HTTPException(status_code=402, detail="Payment declined. Please try a different card.")

    # Payment "approved" — add credits
    current_user.total_credits += req.credits

    # Create notification
    notif = Notification(
        user_id=current_user.id,
        type="credit_alert",
        title="Credits purchased",
        message=f"{req.credits:,} credits added for ${price}. Card ending in {card_last4}.",
        link="/settings?tab=billing",
    )
    db.add(notif)

    audit = AuditLog(user_id=current_user.id, action="credits_purchased",
                     resource_type="billing",
                     details={"credits": req.credits, "price_usd": price, "card_last4": card_last4})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} purchased {req.credits} credits for ${price} (card ****{card_last4})")

    return {
        "credits_added": req.credits,
        "price_usd": price,
        "card_last4": card_last4,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "status": "completed",
    }


@router.post("/api/v1/credits/purchase", tags=["Billing"])
def purchase_credits(
    req: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase an additional credit pack (legacy — use /checkout for payment verification)."""
    credit_packs = _credit_packs(db)
    if req.credits not in credit_packs:
        raise HTTPException(status_code=400, detail="Invalid credit pack")
    price = credit_packs[req.credits]

    current_user.total_credits += req.credits
    audit = AuditLog(user_id=current_user.id, action="credits_purchased",
                     resource_type="billing",
                     details={"credits": req.credits, "price_usd": price})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} purchased {req.credits} credits")

    return {
        "credits_added": req.credits,
        "price_usd": price,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
    }


# ============================================================
# STRIPE WEBHOOKS
# ============================================================

@router.post("/api/v1/billing/webhooks/stripe", tags=["Billing"])
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Stripe webhook events.
    
    Processes:
    - checkout.session.completed: Credit purchase completed
    - customer.subscription.updated: Subscription status changed
    - payment_intent.payment_failed: Payment failed
    """
    from app.stripe_service import (
        is_stripe_enabled,
        verify_webhook_signature,
        handle_checkout_completed,
        handle_subscription_updated,
    )
    
    if not is_stripe_enabled():
        raise HTTPException(status_code=400, detail="Stripe not enabled")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    
    try:
        event = verify_webhook_signature(payload, sig_header)
    except Exception as e:
        logger.error(f"Stripe webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    event_type = event["type"]
    
    if event_type == "checkout.session.completed":
        result = handle_checkout_completed(event)
        user_id = result["user_id"]
        credits = result["credits"]
        
        # Find user and add credits
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_credits += credits
            audit = AuditLog(
                user_id=user.id,
                action="stripe_checkout_completed",
                resource_type="billing",
                details={"credits": credits, "amount": result["amount"]},
            )
            db.add(audit)
            db.commit()
            logger.info(f"Stripe: Added {credits} credits to user {user.email}")
    
    elif event_type == "customer.subscription.updated":
        result = handle_subscription_updated(event)
        user_id = result["user_id"]
        status = result["status"]
        
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            audit = AuditLog(
                user_id=user.id,
                action="stripe_subscription_updated",
                resource_type="billing",
                details={"status": status, "plan_id": result.get("plan_id")},
            )
            db.add(audit)
            db.commit()
            logger.info(f"Stripe: Subscription updated for user {user.email}, status={status}")
    
    else:
        logger.info(f"Stripe webhook: Unhandled event type {event_type}")
    
    return {"status": "ok"}

