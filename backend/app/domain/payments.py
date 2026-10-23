"""Payments through Stripe Checkout (S6.1, ruling D8).

Card data never reaches FinShield: the browser goes to a Stripe-hosted page. Credits are granted
only when Stripe's signed webhook says the session is paid, and exactly once per session (row lock
on the payment, status check, amount check).

PAYMENTS_MODE selects the behaviour:
  simulated (default, local development): checkout grants credits immediately and says so in the
            response and the audit entry. Never use it in production.
  stripe:   needs STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET. STRIPE_API_BASE points the client
            at stripe-mock for tests. APP_BASE_URL is where Stripe sends the browser back.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core import logger
from app.database import rls_bypass
from app.db_models import AuditLog, Notification, Payment, User


class PaymentError(Exception):
    """The request cannot be processed (bad signature, unknown session, amount mismatch...)."""


def mode() -> str:
    return os.getenv("PAYMENTS_MODE", "simulated").strip().lower()


def stripe_enabled() -> bool:
    return mode() == "stripe"


def _stripe() -> Any:
    import stripe

    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise PaymentError("PAYMENTS_MODE=stripe but STRIPE_SECRET_KEY is not set")
    stripe.api_key = key
    if os.getenv("STRIPE_API_BASE"):
        stripe.api_base = os.environ["STRIPE_API_BASE"]
    return stripe


def create_checkout(db: Session, user: User, credits: int, price_usd: float) -> dict:
    """Open a Stripe Checkout Session for a credit pack and record it as a pending payment."""
    stripe = _stripe()
    base = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
    amount_cents = int(round(price_usd * 100))
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"quantity": 1, "price_data": {
            "currency": "usd", "unit_amount": amount_cents,
            "product_data": {"name": f"FinShield {credits:,} screening credits"}}}],
        client_reference_id=user.id,
        customer_email=user.email,
        metadata={"tenant_id": user.tenant_id, "user_id": user.id, "credits": str(credits)},
        success_url=f"{base}/settings?tab=billing&checkout=success",
        cancel_url=f"{base}/settings?tab=billing&checkout=cancelled",
    )
    db.add(Payment(tenant_id=user.tenant_id, user_id=user.id, provider="stripe", provider_ref=session.id,
                   credits=credits, amount_cents=amount_cents, currency="usd", status="pending"))
    db.add(AuditLog(user_id=user.id, action="checkout_started", resource_type="payment", resource_id=session.id,
                    details={"credits": credits, "amount_cents": amount_cents, "provider": "stripe"}))
    db.commit()
    return {"checkout_url": session.url, "session_id": session.id}


def handle_webhook(db: Session, payload: bytes, signature: str) -> dict:
    """Verify a Stripe webhook and apply it. Unknown event types are acknowledged and ignored."""
    stripe = _stripe()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise PaymentError("STRIPE_WEBHOOK_SECRET is not set")
    try:  # verify the signature over the raw bytes, then parse plain JSON (no SDK object model)
        stripe.WebhookSignature.verify_header(payload.decode("utf-8"), signature, secret, tolerance=300)
        event = json.loads(payload)
    except (ValueError, UnicodeDecodeError, stripe.SignatureVerificationError) as exc:
        raise PaymentError(f"invalid webhook: {type(exc).__name__}") from exc
    session = event["data"]["object"]
    if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if session.get("payment_status") != "paid":
            return {"event": event["type"], "result": "awaiting_payment"}
        return fulfil(db, session["id"], session.get("amount_total"))
    if event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        with rls_bypass(db):  # provider callback: no user, the payment row names the tenant
            payment = db.query(Payment).filter(Payment.provider_ref == session["id"]).with_for_update().first()
            if payment is not None and payment.status == "pending":
                payment.status = "expired"
        return {"event": event["type"], "result": "expired"}
    return {"event": event["type"], "result": "ignored"}


def fulfil(db: Session, session_id: str, amount_total: int | None) -> dict:
    """Grant the credits of a paid session once. Safe to call again for the same session."""
    with rls_bypass(db):
        payment = db.query(Payment).filter(Payment.provider_ref == session_id).with_for_update().first()
        if payment is None:
            raise PaymentError(f"unknown checkout session {session_id}")
        if payment.status == "completed":
            return {"result": "already_fulfilled", "payment_id": payment.id}
        if amount_total is not None and amount_total != payment.amount_cents:
            logger.error("payment %s amount mismatch: paid %s, expected %s", payment.id, amount_total,
                         payment.amount_cents)
            raise PaymentError("amount does not match the checkout")
        user = db.get(User, payment.user_id)
        if user is None:
            raise PaymentError("payment user no longer exists")
        user.total_credits = (user.total_credits or 0) + payment.credits
        payment.status, payment.completed_at = "completed", datetime.utcnow()
        db.add(Notification(tenant_id=payment.tenant_id, user_id=user.id, type="credit_alert",
                            title="Credits purchased", link="/settings?tab=billing",
                            message=f"{payment.credits:,} credits added (${payment.amount_cents / 100:,.2f})."))
        db.add(AuditLog(tenant_id=payment.tenant_id, user_id=user.id, action="credits_purchased",
                        resource_type="payment", resource_id=session_id,
                        details={"credits": payment.credits, "amount_cents": payment.amount_cents,
                                 "provider": "stripe"}))
        result = {"result": "fulfilled", "payment_id": payment.id, "credits": payment.credits}
    return result
