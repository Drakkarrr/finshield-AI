"""S6.1 payments: Stripe Checkout with webhook-confirmed, exactly-once credit grants; no card data."""
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect

from app.database import engine
from app.main import app

PASSWORD = "SecurePass123!"
WEBHOOK_SECRET = "whsec_test_only_not_a_secret"
WEBHOOK = "/api/v1/billing/webhooks/stripe"


def _client(token: str | None = None) -> AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


async def _owner(ac: AsyncClient) -> str:
    r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@pay.io", "password": PASSWORD,
                                                  "first_name": "P", "last_name": "Y", "company": "pay"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _signed(event: dict, secret: str = WEBHOOK_SECRET) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    t = int(time.time())
    v1 = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={t},v1={v1}", "Content-Type": "application/json"}


def _completed(session_id: str, amount: int, status: str = "paid") -> dict:
    return {"id": f"evt_{uuid.uuid4().hex[:8]}", "object": "event", "type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "object": "checkout.session", "payment_status": status,
                                "amount_total": amount}}}


@pytest.fixture
def stripe_mode(monkeypatch):
    import stripe

    monkeypatch.setenv("PAYMENTS_MODE", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_only_not_a_secret")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    created = []

    def fake_create(**kwargs):
        created.append(kwargs)
        sid = f"cs_test_{uuid.uuid4().hex[:12]}"
        return SimpleNamespace(id=sid, url=f"https://checkout.stripe.com/c/pay/{sid}")

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_create))
    return created


async def _pack(c: AsyncClient) -> tuple[int, float]:
    plans = (await c.get("/api/v1/billing/plans")).json()
    packs = plans["credit_packs"]
    return packs[0]["credits"], packs[0]["price_usd"]


async def test_no_card_columns_exist_anywhere():
    names = [(t, c["name"]) for t in inspect(engine).get_table_names() for c in inspect(engine).get_columns(t)]
    suspicious = [n for n in names if any(w in n[1].lower() for w in ("card", "cvv", "cvc", "expiry", "pan_"))]
    assert suspicious == [("model_versions", "model_card")]  # an ML model card, not payment data


async def test_stripe_checkout_grants_credits_only_on_a_signed_webhook_and_only_once(stripe_mode):
    async with _client() as anon:
        token = await _owner(anon)
    async with _client(token) as c:
        credits, price = await _pack(c)
        before = (await c.get("/api/v1/credits")).json()["total_credits"]
        r = await c.post("/api/v1/credits/checkout", json={"credits": credits})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mode"] == "stripe" and body["checkout_url"].startswith("https://checkout.stripe.com/")
        sent = stripe_mode[-1]
        assert sent["line_items"][0]["price_data"]["unit_amount"] == round(price * 100)
        assert "card" not in json.dumps(sent).lower()  # nothing card-related leaves FinShield either
        assert (await c.get("/api/v1/credits")).json()["total_credits"] == before  # not paid yet

        async with _client() as stripe_server:
            unsigned = json.dumps(_completed(body["session_id"], round(price * 100))).encode()
            assert (await stripe_server.post(WEBHOOK, content=unsigned,
                                             headers={"Stripe-Signature": "t=1,v1=bad"})).status_code == 400
            pending, hdr = _signed(_completed(body["session_id"], round(price * 100), status="unpaid"))
            assert (await stripe_server.post(WEBHOOK, content=pending, headers=hdr)).json()["result"] == "awaiting_payment"
            paid, hdr = _signed(_completed(body["session_id"], round(price * 100)))
            first = await stripe_server.post(WEBHOOK, content=paid, headers=hdr)
            assert first.status_code == 200 and first.json()["result"] == "fulfilled", first.text
            again = await stripe_server.post(WEBHOOK, content=paid, headers=hdr)  # Stripe retries deliveries
            assert again.json()["result"] == "already_fulfilled"
        assert (await c.get("/api/v1/credits")).json()["total_credits"] == before + credits


async def test_webhook_rejects_amount_mismatch_and_unknown_sessions(stripe_mode):
    async with _client() as anon:
        token = await _owner(anon)
    async with _client(token) as c:
        credits, price = await _pack(c)
        sid = (await c.post("/api/v1/credits/checkout", json={"credits": credits})).json()["session_id"]
    async with _client() as stripe_server:
        wrong, hdr = _signed(_completed(sid, round(price * 100) - 1))
        assert (await stripe_server.post(WEBHOOK, content=wrong, headers=hdr)).status_code == 400
        unknown, hdr = _signed(_completed("cs_test_unknown", 100))
        assert (await stripe_server.post(WEBHOOK, content=unknown, headers=hdr)).status_code == 400
        other, hdr = _signed(_completed(sid, round(price * 100)), secret="whsec_attacker")
        assert (await stripe_server.post(WEBHOOK, content=other, headers=hdr)).status_code == 400


async def test_stripe_mode_closes_every_unpaid_credit_path(stripe_mode):
    async with _client() as anon:
        token = await _owner(anon)
    async with _client(token) as c:
        credits, _ = await _pack(c)
        assert (await c.post("/api/v1/credits/purchase", json={"credits": credits})).status_code == 409
        assert (await c.post("/api/v1/billing/subscribe", json={"plan_id": "growth"})).status_code == 501


async def test_simulated_mode_says_so_and_records_the_payment(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "simulated")
    async with _client() as anon:
        token = await _owner(anon)
    async with _client(token) as c:
        credits, _ = await _pack(c)
        r = await c.post("/api/v1/credits/checkout", json={"credits": credits})
        assert r.status_code == 200 and r.json()["mode"] == "simulated"
    async with _client() as anon:
        assert (await anon.post(WEBHOOK, content=b"{}")).status_code == 404  # no provider endpoint without Stripe
