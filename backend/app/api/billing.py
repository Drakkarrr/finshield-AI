"""FinShield AI — Credits, plans, subscriptions and checkout."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

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

PLANS = [
    {
        "id": "starter",
        "name": "Starter",
        "price_monthly": 29,
        "included_credits": 15000,
        "features": ["Up to 15,000 credits/mo", "Rule + behavioral screening", "Email support", "1 API key"],
    },
    {
        "id": "growth",
        "name": "Growth",
        "price_monthly": 99,
        "included_credits": 60000,
        "features": ["Up to 60,000 credits/mo", "Full ML pipeline", "Case management", "Priority support"],
    },
    {
        "id": "pro",
        "name": "Pro",
        "price_monthly": 299,
        "included_credits": 250000,
        "features": ["Up to 250,000 credits/mo", "Everything in Growth", "SAR/STR filing", "Dedicated CSM"],
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "price_monthly": None,
        "included_credits": None,
        "features": ["Unlimited credits", "On-premise / VPC", "SSO + audit export", "99.9% uptime SLA"],
    },
]

CREDIT_PACKS = {
    10000: 9,
    50000: 39,
    200000: 129,
}


class SubscribeRequest(BaseModel):
    plan_id: str


class PurchaseRequest(BaseModel):
    credits: int


class CheckoutRequest(BaseModel):
    credits: int
    card_last4: Optional[str] = None
    card_expiry: Optional[str] = None
    card_holder: Optional[str] = None
    use_saved_card: bool = False


class SavedCardRequest(BaseModel):
    """Save or update the user's payment method on file."""
    card_last4: str
    card_expiry: str
    card_holder: str


class RemoveSavedCardRequest(BaseModel):
    """Remove the saved payment method."""
    pass


@router.get("/api/v1/billing/plans", tags=["Billing"])
def list_plans(current_user: User = Depends(get_current_user)):
    """List available subscription plans."""
    # Calculate days remaining: billing cycle if paid, else trial expiry
    days_remaining = None
    cycle_end = current_user.billing_cycle_end
    if cycle_end:
        days_remaining = max(0, (cycle_end - datetime.utcnow()).days)
    elif current_user.is_trial and current_user.trial_expires_at:
        days_remaining = max(0, (current_user.trial_expires_at - datetime.utcnow()).days)
    return {
        "plans": PLANS,
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
    plan = next((p for p in PLANS if p["id"] == req.plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    if plan["included_credits"] is None:
        raise HTTPException(status_code=400, detail="Enterprise plans require contacting sales")
    if plan["id"] == current_user.plan:
        raise HTTPException(status_code=400, detail="Already on this plan")

    current_plan = next((p for p in PLANS if p["id"] == current_user.plan), None)
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
    """Simulated payment checkout for credit purchase. Supports saved card (Qoder-like flow)."""
    if req.credits not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Invalid credit pack")

    # Determine card details: use saved card or validate new card
    if req.use_saved_card:
        if not current_user.saved_card_last4:
            raise HTTPException(status_code=400, detail="No saved payment method. Please add a card first.")
        card_last4 = current_user.saved_card_last4
        card_expiry = current_user.saved_card_expiry
        card_holder = current_user.saved_card_holder
    else:
        # Validate new card details
        if not req.card_last4 or len(req.card_last4) != 4 or not req.card_last4.isdigit():
            raise HTTPException(status_code=400, detail="Invalid card last 4 digits")
        if not req.card_expiry or "/" not in req.card_expiry:
            raise HTTPException(status_code=400, detail="Invalid card expiry format (MM/YY)")
        if not req.card_holder or len(req.card_holder.strip()) < 2:
            raise HTTPException(status_code=400, detail="Invalid card holder name")
        card_last4 = req.card_last4
        card_expiry = req.card_expiry
        card_holder = req.card_holder

    price = CREDIT_PACKS[req.credits]

    # Simulate payment processing (in production, this would call Stripe/PayPal)
    # Simulate decline for card ending in 0000
    if card_last4 == "0000":
        raise HTTPException(status_code=402, detail="Payment declined. Please try a different card.")

    # Payment "approved" — add credits
    current_user.total_credits += req.credits

    # Save card for future use (Qoder-like flow: first payment saves billing info)
    current_user.saved_card_last4 = card_last4
    current_user.saved_card_expiry = card_expiry
    current_user.saved_card_holder = card_holder

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
                     details={"credits": req.credits, "price_usd": price, "card_last4": card_last4, "used_saved": req.use_saved_card})
    db.add(audit)
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.email} purchased {req.credits} credits for ${price} (card ****{card_last4}, saved={req.use_saved_card})")

    return {
        "credits_added": req.credits,
        "price_usd": price,
        "card_last4": card_last4,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "status": "completed",
    }


@router.patch("/api/v1/billing/saved-card", tags=["Billing"])
def update_saved_card(
    req: SavedCardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save or update the user's payment method on file."""
    if not req.card_last4 or len(req.card_last4) != 4 or not req.card_last4.isdigit():
        raise HTTPException(status_code=400, detail="Invalid card last 4 digits")
    if not req.card_expiry or "/" not in req.card_expiry:
        raise HTTPException(status_code=400, detail="Invalid card expiry format (MM/YY)")
    if not req.card_holder or len(req.card_holder.strip()) < 2:
        raise HTTPException(status_code=400, detail="Invalid card holder name")

    current_user.saved_card_last4 = req.card_last4
    current_user.saved_card_expiry = req.card_expiry
    current_user.saved_card_holder = req.card_holder.strip()
    db.commit()
    db.refresh(current_user)
    return {"detail": "Payment method saved", "card_last4": current_user.saved_card_last4, "card_expiry": current_user.saved_card_expiry, "card_holder": current_user.saved_card_holder}


@router.delete("/api/v1/billing/saved-card", tags=["Billing"])
def remove_saved_card(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the saved payment method."""
    current_user.saved_card_last4 = None
    current_user.saved_card_expiry = None
    current_user.saved_card_holder = None
    db.commit()
    return {"detail": "Payment method removed"}


@router.post("/api/v1/credits/purchase", tags=["Billing"])
def purchase_credits(
    req: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase an additional credit pack (legacy — use /checkout for payment verification)."""
    if req.credits not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail="Invalid credit pack")
    price = CREDIT_PACKS[req.credits]

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
