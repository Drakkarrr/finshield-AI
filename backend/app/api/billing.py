"""FinShield AI — Credits, plans, subscriptions and checkout."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
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
    Payment,
    User,
)
from app.domain import payments
from app.models import (
    CreditsResponse,
)

router = APIRouter()
# Called by the payment provider, not a user: authenticated by the webhook signature instead.
provider_router = APIRouter()


def _refuse_unpaid_grants() -> None:
    """With a real payment provider, nothing may add credits without a confirmed payment."""
    if payments.stripe_enabled():
        raise HTTPException(status_code=409, detail="Credits are sold through Stripe Checkout: "
                                                    "use POST /api/v1/credits/checkout")


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
    """No card fields: card data is never accepted or stored (S3.5). Stripe Checkout (S6.1) takes
    payment on Stripe's page; extra fields sent by older clients are ignored."""
    credits: int
    use_saved_card: bool = False


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
        "credit_packs": [{"credits": k, "price_usd": v} for k, v in sorted(_credit_packs(db).items())],
        "payments_mode": payments.mode(),  # "stripe" or "simulated" (development: no real payment)
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
    if payments.stripe_enabled():  # plan billing through Stripe is not built yet; credit packs are
        raise HTTPException(status_code=501, detail="Plan changes are not billed through Stripe yet; "
                                                    "buy credit packs via checkout or contact sales")
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
    """Buy a credit pack. With PAYMENTS_MODE=stripe this returns a Stripe Checkout URL and the
    credits arrive with Stripe's webhook; in simulated mode (development) they are added at once."""
    credit_packs = _credit_packs(db)
    if req.credits not in credit_packs:
        raise HTTPException(status_code=400, detail="Invalid credit pack")
    # Card data is never stored (S3.5); Stripe's hosted page collects it (S6.1, ruling D8).
    if req.use_saved_card:
        raise HTTPException(status_code=501, detail="Saved cards were removed; Stripe Checkout collects card details")
    price = credit_packs[req.credits]
    if payments.stripe_enabled():
        try:
            return {**payments.create_checkout(db, current_user, req.credits, price), "mode": "stripe"}
        except payments.PaymentError as exc:
            logger.error(f"checkout unavailable: {exc}")
            raise HTTPException(status_code=503, detail="Payments are temporarily unavailable") from exc

    # SIMULATED payment (development only): no provider, credits granted immediately.
    current_user.total_credits += req.credits
    ref = f"sim_{uuid.uuid4().hex}"
    db.add(Payment(tenant_id=current_user.tenant_id, user_id=current_user.id, provider="simulated",
                   provider_ref=ref, credits=req.credits, amount_cents=int(round(price * 100)), currency="usd",
                   status="completed", completed_at=datetime.utcnow()))
    db.add(Notification(user_id=current_user.id, type="credit_alert", title="Credits purchased",
                        message=f"{req.credits:,} credits added for ${price} (simulated payment).",
                        link="/settings?tab=billing"))
    db.add(AuditLog(user_id=current_user.id, action="credits_purchased", resource_type="payment", resource_id=ref,
                    details={"credits": req.credits, "price_usd": price, "simulated_payment": True}))
    db.commit()
    db.refresh(current_user)
    logger.info(f"User {current_user.id} purchased {req.credits} credits for ${price} (simulated payment)")

    return {
        "mode": "simulated",
        "credits_added": req.credits,
        "price_usd": price,
        "total_credits": current_user.total_credits,
        "credits_remaining": current_user.total_credits - round(current_user.used_credits),
        "status": "completed",
    }


@provider_router.post("/api/v1/billing/webhooks/stripe", tags=["Billing"], include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe event receiver. Authenticated by the Stripe-Signature header (STRIPE_WEBHOOK_SECRET)."""
    if not payments.stripe_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        body = await request.body()  # the signature covers the raw bytes
        return await run_in_threadpool(payments.handle_webhook, db, body, request.headers.get("stripe-signature", ""))
    except payments.PaymentError as exc:
        logger.warning(f"stripe webhook rejected: {exc}")
        raise HTTPException(status_code=400, detail="Webhook rejected") from exc


@router.patch("/api/v1/billing/saved-card", tags=["Billing"])
def update_saved_card(current_user: User = Depends(get_current_user)):
    """Removed: storing card metadata with no payment provider is pure liability (S3.5)."""
    raise HTTPException(status_code=501, detail="Saved cards were removed; Stripe Checkout replaces them (S6.1)")


@router.delete("/api/v1/billing/saved-card", tags=["Billing"])
def remove_saved_card(current_user: User = Depends(get_current_user)):
    """Removed with the saved-card columns (S3.5)."""
    raise HTTPException(status_code=501, detail="Saved cards were removed; Stripe Checkout replaces them (S6.1)")


@router.post("/api/v1/credits/purchase", tags=["Billing"])
def purchase_credits(
    req: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purchase an additional credit pack (legacy — use /checkout for payment verification)."""
    _refuse_unpaid_grants()
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
