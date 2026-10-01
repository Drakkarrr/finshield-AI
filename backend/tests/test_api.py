"""
FinShield AI — Integration Tests for API Endpoints (Production)
Tests auth flow, transaction screening, cases, credits, API keys, and rate limiting.
"""
import os

# CRITICAL: Set test environment BEFORE any app imports
os.environ["APP_ENV"] = "test"

import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import engine, Base, reset_db

# Ensure tables exist at module load
Base.metadata.create_all(bind=engine)


@pytest_asyncio.fixture(scope="session")
async def anyio_loop():
    """Provide an event loop for the session."""
    pass


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _unique_email() -> str:
    return f"{uuid.uuid4().hex[:8]}@test.io"


@pytest_asyncio.fixture(scope="session")
async def session_auth_client():
    """Session-scoped authenticated client — registers once, reused across all tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = _unique_email()
        r = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Auth",
            "last_name": "Tester",
            "company": "Test Corp",
        })
        assert r.status_code == 201, f"Register failed: {r.status_code} {r.text}"
        token = r.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest_asyncio.fixture
async def auth_client(session_auth_client: AsyncClient):
    """Per-test client that shares the session-scoped auth token."""
    yield session_auth_client


# =============================================
# Health Endpoint
# =============================================

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "2.4.0"

    @pytest.mark.asyncio
    async def test_health_includes_all_services(self, client):
        resp = await client.get("/api/health")
        services = resp.json()["services"]
        assert "rule_engine" in services
        assert "behavioral_ml" in services
        assert "database" in services

    @pytest.mark.asyncio
    async def test_health_uptime_positive(self, client):
        resp = await client.get("/api/health")
        assert resp.json()["uptime_seconds"] > 0


# =============================================
# Auth Endpoints
# =============================================

class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_register_new_user(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": _unique_email(),
            "password": "Password123!",
            "first_name": "New",
            "last_name": "User",
            "company": "Startup Inc",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["credits_remaining"] == 1000

    @pytest.mark.asyncio
    async def test_register_duplicate_email_fails(self, client):
        email = _unique_email()
        payload = {
            "email": email,
            "password": "Password123!",
            "first_name": "A",
            "last_name": "B",
        }
        await client.post("/api/auth/register", json=payload)
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        email = _unique_email()
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "MyPassword1!",
            "first_name": "Login",
            "last_name": "Test",
        })
        resp = await client.post("/api/auth/login", json={
            "email": email,
            "password": "MyPassword1!",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        email = _unique_email()
        await client.post("/api/auth/register", json={
            "email": email,
            "password": "CorrectPass1!",
            "first_name": "A",
            "last_name": "B",
        })
        resp = await client.post("/api/auth/login", json={
            "email": email,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, auth_client):
        resp = await auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_credits"] == 1000

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


# =============================================
# Transaction Screening (Authenticated)
# =============================================

class TestTransactionScreening:
    @pytest.mark.asyncio
    async def test_screen_clean_transaction(self, auth_client):
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": 500.0,
            "currency": "USD",
            "transaction_type": "wire",
            "sender_name": "John Doe",
            "receiver_name": "Jane Smith",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] in ("approved", "flagged", "blocked", "in_review")

    @pytest.mark.asyncio
    async def test_screen_sanctioned_sender(self, auth_client):
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": 100000.0,
            "currency": "USD",
            "transaction_type": "international",
            "sender_name": "GlobalRemit",
            "receiver_name": "Unknown",
            "destination_country": "KP",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_screen_unauthenticated_returns_401(self, client):
        resp = await client.post("/api/v1/transactions", json={
            "amount": 500.0,
            "transaction_type": "wire",
            "sender_name": "Test",
            "receiver_name": "Receiver",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_screen_invalid_amount_returns_422(self, auth_client):
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": -100.0,
            "transaction_type": "wire",
            "sender_name": "Test",
            "receiver_name": "Receiver",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_screen_missing_field_returns_422(self, auth_client):
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": 100.0,
            "transaction_type": "wire",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_transactions(self, auth_client):
        await auth_client.post("/api/v1/transactions", json={
            "amount": 500.0,
            "transaction_type": "wire",
            "sender_name": "Test",
            "receiver_name": "Receiver",
        })
        resp = await auth_client.get("/api/v1/transactions")
        assert resp.status_code == 200
        txs = resp.json()
        assert isinstance(txs, list)
        assert len(txs) >= 1

    @pytest.mark.asyncio
    async def test_sanctioned_sender_is_blocked_regardless_of_amount(self, auth_client):
        """C1: a triggered 'block' rule must block even a small amount."""
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": 50.0,
            "transaction_type": "wire",
            "sender_name": "darkfund",  # in SANCTIONED_ENTITIES
            "receiver_name": "Anyone",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "blocked"
        sanctions = next(r for r in data["rule_results"] if r["rule_id"] == "RULE-001")
        assert sanctions["triggered"] is True

    @pytest.mark.asyncio
    async def test_high_risk_country_is_blocked(self, auth_client):
        """C1: geography 'escalate' action must block."""
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": 200.0,
            "transaction_type": "wire",
            "sender_name": "Normalco",
            "receiver_name": "Acme",
            "destination_country": "KP",
        })
        data = resp.json()["data"]
        assert data["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_api_key_authenticates_requests(self, auth_client):
        """C2: a live API key must authenticate a screening call."""
        create = await auth_client.post("/api/v1/keys", json={"name": "Auth Key"})
        raw = create.json()["key"]
        # Use the API key as a bearer token on a fresh client (no JWT)
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/transactions", json={
                "amount": 300.0, "transaction_type": "wire",
                "sender_name": "KeySender", "receiver_name": "Recv",
            }, headers={"Authorization": f"Bearer {raw}"})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, auth_client):
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/credits", headers={"Authorization": "Bearer fsk_live_notarealkey"})
            assert resp.status_code == 401


# =============================================
# Cases Endpoints (Authenticated)
# =============================================

class TestCasesEndpoints:
    async def _make_tx(self, auth_client) -> str:
        """Screen a real transaction and return its persisted DB id."""
        resp = await auth_client.post("/api/v1/transactions", json={
            "amount": 500.0,
            "transaction_type": "wire",
            "sender_name": "CaseSender",
            "receiver_name": "CaseReceiver",
        })
        return resp.json()["data"]["transaction_id"]

    @pytest.mark.asyncio
    async def test_create_case(self, auth_client):
        tx_id = await self._make_tx(auth_client)
        resp = await auth_client.post("/api/v1/cases", json={
            "transaction_id": tx_id,
            "reason": "Suspicious wire pattern",
            "priority": "high",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["case_id"].startswith("CASE-")
        assert data["status"] == "created"

    @pytest.mark.asyncio
    async def test_create_case_unknown_transaction_returns_404(self, auth_client):
        resp = await auth_client.post("/api/v1/cases", json={
            "transaction_id": "TX-DOES-NOT-EXIST",
            "reason": "Orphan case",
            "priority": "high",
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_case(self, auth_client):
        tx_id = await self._make_tx(auth_client)
        create_resp = await auth_client.post("/api/v1/cases", json={
            "transaction_id": tx_id,
            "reason": "Test case",
        })
        case_id = create_resp.json()["case_id"]
        get_resp = await auth_client.get(f"/api/v1/cases/{case_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["case_id"] == case_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_case_returns_404(self, auth_client):
        resp = await auth_client.get("/api/v1/cases/CASE-NOTREAL")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_cases(self, auth_client):
        resp = await auth_client.get("/api/v1/cases")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# =============================================
# Credits Endpoint (Authenticated)
# =============================================

class TestCreditsEndpoint:
    @pytest.mark.asyncio
    async def test_get_credits(self, auth_client):
        resp = await auth_client.get("/api/v1/credits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_credits"] == 1000
        assert data["remaining_credits"] <= data["total_credits"]

    @pytest.mark.asyncio
    async def test_credits_decrease_after_screening(self, auth_client):
        before = await auth_client.get("/api/v1/credits")
        before_remaining = before.json()["remaining_credits"]
        for _ in range(10):
            await auth_client.post("/api/v1/transactions", json={
                "amount": 100.0,
                "transaction_type": "wire",
                "sender_name": "TestUser",
                "receiver_name": "Receiver",
            })
        after = await auth_client.get("/api/v1/credits")
        after_remaining = after.json()["remaining_credits"]
        assert after_remaining < before_remaining


# =============================================
# API Keys Endpoints
# =============================================

class TestApiKeys:
    @pytest.mark.asyncio
    async def test_create_api_key(self, auth_client):
        resp = await auth_client.post("/api/v1/keys", json={"name": "Test Key"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Key"
        assert data["key"].startswith("fsk_live_")

    @pytest.mark.asyncio
    async def test_list_api_keys(self, auth_client):
        await auth_client.post("/api/v1/keys", json={"name": "Key 1"})
        resp = await auth_client.get("/api/v1/keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) >= 1

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, auth_client):
        create_resp = await auth_client.post("/api/v1/keys", json={"name": "To Revoke"})
        key_id = create_resp.json()["id"]
        resp = await auth_client.delete(f"/api/v1/keys/{key_id}")
        assert resp.status_code == 200


# =============================================
# Stats / Analytics (Authenticated)
# =============================================

class TestStats:
    @pytest.mark.asyncio
    async def test_get_stats(self, auth_client):
        resp = await auth_client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("total_transactions", "approved", "flagged", "blocked",
                    "in_review", "open_cases", "avg_risk_score", "credits_remaining"):
            assert key in data

    @pytest.mark.asyncio
    async def test_stats_reflect_screened_transactions(self, auth_client):
        before = (await auth_client.get("/api/v1/stats")).json()["total_transactions"]
        await auth_client.post("/api/v1/transactions", json={
            "amount": 700.0, "transaction_type": "wire",
            "sender_name": "StatTest", "receiver_name": "Recv",
        })
        after = (await auth_client.get("/api/v1/stats")).json()["total_transactions"]
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_stats_unauthenticated_401(self, client):
        resp = await client.get("/api/v1/stats")
        assert resp.status_code == 401


# =============================================
# Rules (Authenticated)
# =============================================

class TestRules:
    @pytest.mark.asyncio
    async def test_list_rules(self, auth_client):
        resp = await auth_client.get("/api/v1/rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert isinstance(rules, list)
        assert len(rules) == 4
        rule_types = {r["rule_type"] for r in rules}
        assert {"sanctions", "pep", "threshold", "geography"} <= rule_types
        for r in rules:
            assert "rule_id" in r and "name" in r and "action" in r

    @pytest.mark.asyncio
    async def test_disabling_rule_stops_it_firing(self, auth_client):
        """C2: engine must respect a disabled rule (geography)."""
        # Baseline: high-risk country triggers geography rule and blocks
        tx = {"amount": 60000.0, "transaction_type": "international",
              "sender_name": "Acme", "receiver_name": "X", "destination_country": "KP",
              "idempotency_key": "geo-on-" + uuid.uuid4().hex}
        baseline = (await auth_client.post("/api/v1/transactions", json=tx)).json()["data"]
        geo = next(r for r in baseline["rule_results"] if r["rule_id"] == "RULE-004")
        assert geo["triggered"] is True

        # Disable RULE-004
        await auth_client.patch("/api/v1/rules/RULE-004", json={"enabled": False})
        tx2 = dict(tx, idempotency_key="geo-off-" + uuid.uuid4().hex)
        after = (await auth_client.post("/api/v1/transactions", json=tx2)).json()["data"]
        assert all(r["rule_id"] != "RULE-004" for r in after["rule_results"])

    @pytest.mark.asyncio
    async def test_custom_threshold_param_is_honored(self, auth_client):
        """C3: engine must use user's custom threshold."""
        # Lower wire threshold to 100; a $50 wire should then NOT trigger RULE-003
        await auth_client.patch("/api/v1/rules/RULE-003", json={"custom_parameters": {"wire": 100}})
        tx = {"amount": 50.0, "transaction_type": "wire", "sender_name": "Small",
              "receiver_name": "Recv", "idempotency_key": "thr-" + uuid.uuid4().hex}
        data = (await auth_client.post("/api/v1/transactions", json=tx)).json()["data"]
        thr = next((r for r in data["rule_results"] if r["rule_id"] == "RULE-003"), None)
        assert thr is not None and thr["triggered"] is False


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_idempotency_key_no_crash(self, auth_client):
        """C4: replaying the same idempotency key returns stored result, not 500."""
        key = "idem-" + uuid.uuid4().hex
        tx = {"amount": 500.0, "transaction_type": "wire",
              "sender_name": "Idem", "receiver_name": "Recv", "idempotency_key": key}
        first = await auth_client.post("/api/v1/transactions", json=tx)
        assert first.status_code == 200
        second = await auth_client.post("/api/v1/transactions", json=tx)
        assert second.status_code == 200
        assert second.json()["data"]["transaction_id"] == first.json()["data"]["transaction_id"]


# =============================================
# Billing & Subscription (Authenticated)
# =============================================

class TestBilling:
    @pytest.mark.asyncio
    async def test_list_plans(self, auth_client):
        resp = await auth_client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data and "current_plan" in data
        plan_ids = {p["id"] for p in data["plans"]}
        assert {"starter", "growth", "pro", "enterprise"} <= plan_ids

    @pytest.mark.asyncio
    async def test_subscribe_to_plan(self, auth_client):
        resp = await auth_client.post("/api/v1/billing/subscribe", json={"plan_id": "pro"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "pro"
        assert data["total_credits"] >= 250000

    @pytest.mark.asyncio
    async def test_subscribe_unknown_plan_400(self, auth_client):
        resp = await auth_client.post("/api/v1/billing/subscribe", json={"plan_id": "bogus"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_subscribe_enterprise_requires_sales(self, auth_client):
        resp = await auth_client.post("/api/v1/billing/subscribe", json={"plan_id": "enterprise"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_purchase_credits(self, auth_client):
        before = (await auth_client.get("/api/v1/credits")).json()["total_credits"]
        resp = await auth_client.post("/api/v1/credits/purchase", json={"credits": 50000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["credits_added"] == 50000
        assert data["price_usd"] == 39
        assert data["total_credits"] == before + 50000

    @pytest.mark.asyncio
    async def test_purchase_invalid_pack_400(self, auth_client):
        resp = await auth_client.post("/api/v1/credits/purchase", json={"credits": 123})
        assert resp.status_code == 400


# =============================================
# Root Endpoint
# =============================================

class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_root_returns_service_info(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "FinShield AI"
        assert data["version"] == "2.4.0"
