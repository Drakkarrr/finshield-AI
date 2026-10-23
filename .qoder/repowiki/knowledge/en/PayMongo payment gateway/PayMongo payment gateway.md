---
kind: external_dependency
name: PayMongo payment gateway
slug: paymongo
category: external_dependency
category_hints:
    - vendor_identity
scope:
    - '**'
source_files:
    - DEPLOYMENT.md
---

### Identity
PayMongo (paymongo.com) — Philippine payment gateway supporting cards, GCash, Maya.

### Planned integration
- Checkout via `POST /checkout_sessions` on `https://api.paymongo.com/v1` with Basic auth (`PAYMONGO_SECRET_KEY`).
- Payment verification via `GET /payment_intents/{id}`.
- Webhook endpoint expected at `/api/webhooks/paymongo` listening for `payment_intent.succeeded` / `payment_intent.payment_failed`.
- Currency: PHP centavos; USD price converted at ~50 rate before multiplying by 100.

### Status
- Code snippet is provided in `DEPLOYMENT.md` but no `backend/app/payment.py` exists in the tree; not yet wired into `main.py`.