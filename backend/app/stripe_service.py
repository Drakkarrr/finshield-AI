"""FinShield AI — Stripe payment integration.

This module provides Stripe payment processing for credit purchases and subscriptions.
Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET environment variables to enable.

For production deployment:
1. Install stripe: pip install stripe
2. Set STRIPE_SECRET_KEY=sk_live_... or sk_test_...
3. Set STRIPE_WEBHOOK_SECRET=whsec_...
4. Configure webhook endpoint in Stripe dashboard: POST /api/v1/billing/webhooks/stripe
"""
import os
from typing import Optional

from app.core import logger

# Stripe is optional - only import if available and configured
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None  # type: ignore
    STRIPE_AVAILABLE = False
    logger.warning("Stripe SDK not installed. Payment features disabled. Install with: pip install stripe")


def is_stripe_enabled() -> bool:
    """Check if Stripe is configured and available."""
    return STRIPE_AVAILABLE and bool(os.getenv("STRIPE_SECRET_KEY"))


def _get_stripe_key() -> Optional[str]:
    return os.getenv("STRIPE_SECRET_KEY")


def create_checkout_session(
    user_id: str,
    email: str,
    credits: int,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Stripe Checkout Session for credit purchase.
    
    Returns: {"session_id": "...", "url": "..."}
    """
    if not is_stripe_enabled():
        raise RuntimeError("Stripe is not enabled. Set STRIPE_SECRET_KEY environment variable.")
    
    stripe.api_key = _get_stripe_key()
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"FinShield {credits} Credits",
                        "description": f"Purchase {credits} transaction screening credits",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            mode="payment",
            customer_email=email,
            client_reference_id=user_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "credits": str(credits),
            },
        )
        
        return {
            "session_id": session.id,
            "url": session.url,
        }
    except Exception as e:
        logger.exception("Failed to create Stripe checkout session")
        raise RuntimeError(f"Stripe error: {str(e)}")


def create_subscription(
    user_id: str,
    email: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Create a Stripe Checkout Session for subscription.
    
    Returns: {"session_id": "...", "url": "..."}
    """
    if not is_stripe_enabled():
        raise RuntimeError("Stripe is not enabled.")
    
    stripe.api_key = _get_stripe_key()
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            customer_email=email,
            client_reference_id=user_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
            },
        )
        
        return {
            "session_id": session.id,
            "url": session.url,
        }
    except Exception as e:
        logger.exception("Failed to create Stripe subscription session")
        raise RuntimeError(f"Stripe error: {str(e)}")


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature and return event.
    
    Returns the event dict if valid, raises if invalid.
    """
    if not is_stripe_enabled():
        raise RuntimeError("Stripe is not enabled.")
    
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured.")
    
    stripe.api_key = _get_stripe_key()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except ValueError as e:
        logger.error(f"Invalid Stripe payload: {e}")
        raise
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid Stripe signature: {e}")
        raise


def handle_checkout_completed(event: dict) -> dict:
    """Handle checkout.session.completed event.
    
    Returns: {"user_id": "...", "credits": ..., "amount": ...}
    """
    session = event["data"]["object"]
    user_id = session["metadata"]["user_id"]
    credits = int(session["metadata"].get("credits", 0))
    amount = session["amount_total"]
    
    logger.info(f"Stripe checkout completed: user={user_id}, credits={credits}, amount={amount}")
    
    return {
        "user_id": user_id,
        "credits": credits,
        "amount": amount,
    }


def handle_subscription_updated(event: dict) -> dict:
    """Handle customer.subscription.updated event.
    
    Returns: {"user_id": "...", "status": "...", "plan_id": "..."}
    """
    subscription = event["data"]["object"]
    user_id = subscription["metadata"]["user_id"]
    status = subscription["status"]
    plan_id = subscription["items"]["data"][0]["price"]["id"] if subscription.get("items") else None
    
    logger.info(f"Stripe subscription updated: user={user_id}, status={status}")
    
    return {
        "user_id": user_id,
        "status": status,
        "plan_id": plan_id,
    }


def create_refund(payment_intent_id: str, amount_cents: Optional[int] = None) -> dict:
    """Create a refund for a payment.
    
    If amount_cents is None, refunds the full amount.
    Returns: {"refund_id": "...", "amount": ...}
    """
    if not is_stripe_enabled():
        raise RuntimeError("Stripe is not enabled.")
    
    stripe.api_key = _get_stripe_key()
    
    try:
        refund_params = {"payment_intent": payment_intent_id}
        if amount_cents:
            refund_params["amount"] = amount_cents
        
        refund = stripe.Refund.create(**refund_params)
        
        logger.info(f"Stripe refund created: {refund.id}, amount={refund.amount}")
        
        return {
            "refund_id": refund.id,
            "amount": refund.amount,
        }
    except Exception as e:
        logger.exception("Failed to create Stripe refund")
        raise RuntimeError(f"Stripe error: {str(e)}")
