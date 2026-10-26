"""S7.0: Tenant-scoped idempotency tests.

Two tenants can use the same idempotency_key independently. Each tenant's replay
returns that tenant's own decision, not the other tenant's.
"""
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["APP_ENV"] = "test"

from app.main import app


@pytest_asyncio.fixture(scope="session")
async def session_auth_client():
    """Session-scoped authenticated client — registers once, reused across all tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"{uuid.uuid4().hex[:8]}@test.io"
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


@pytest_asyncio.fixture
async def other_tenant_client():
    """Create a second tenant for testing cross-tenant idempotency."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"{uuid.uuid4().hex[:8]}@other.io"
        r = await ac.post("/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Other",
            "last_name": "Tenant",
            "company": "Other Corp",
        })
        assert r.status_code == 201, f"Register failed: {r.status_code} {r.text}"
        token = r.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest.mark.asyncio
async def test_two_tenants_can_use_same_idempotency_key(auth_client, other_tenant_client):
    """Two different tenants can submit transactions with the same idempotency_key."""
    shared_key = f"shared-{uuid.uuid4().hex}"

    payload = {
        "sender_name": "Test Sender",
        "receiver_name": "Test Receiver",
        "amount": 1000.0,
        "currency": "USD",
        "transaction_type": "wire",
        "destination_country": "US",
        "idempotency_key": shared_key,
    }

    # Tenant A submits
    r1 = await auth_client.post("/api/v1/transactions", json=payload)
    assert r1.status_code == 200
    tx1 = r1.json()["data"]
    assert tx1["idempotency_key"] == shared_key

    # Tenant B submits with the same key
    r2 = await other_tenant_client.post("/api/v1/transactions", json=payload)
    assert r2.status_code == 200
    tx2 = r2.json()["data"]
    assert tx2["idempotency_key"] == shared_key

    # Both transactions exist with different IDs
    assert tx1["transaction_id"] != tx2["transaction_id"]


@pytest.mark.asyncio
async def test_idempotency_replay_returns_same_tenant_decision(auth_client, other_tenant_client):
    """Replaying a transaction returns the same tenant's decision, not another tenant's."""
    shared_key = f"replay-{uuid.uuid4().hex}"

    payload_a = {
        "sender_name": "Tenant A Sender",
        "receiver_name": "Receiver",
        "amount": 5000.0,
        "currency": "USD",
        "transaction_type": "wire",
        "destination_country": "US",
        "idempotency_key": shared_key,
    }

    payload_b = {
        "sender_name": "Tenant B Sender",
        "receiver_name": "Receiver",
        "amount": 10000.0,
        "currency": "USD",
        "transaction_type": "wire",
        "destination_country": "US",
        "idempotency_key": shared_key,
    }

    # Tenant A submits first
    r1 = await auth_client.post("/api/v1/transactions", json=payload_a)
    assert r1.status_code == 200
    tx1 = r1.json()["data"]
    tx1_id = tx1["transaction_id"]

    # Tenant B submits with same key
    r2 = await other_tenant_client.post("/api/v1/transactions", json=payload_b)
    assert r2.status_code == 200
    tx2 = r2.json()["data"]
    tx2_id = tx2["transaction_id"]

    # Different transactions for different tenants
    assert tx1_id != tx2_id

    # Tenant A replays - should get tenant A's transaction back
    r3 = await auth_client.post("/api/v1/transactions", json=payload_a)
    assert r3.status_code == 200
    tx3 = r3.json()["data"]
    assert tx3["transaction_id"] == tx1_id
    assert tx3["idempotency_key"] == shared_key

    # Tenant B replays - should get tenant B's transaction back
    r4 = await other_tenant_client.post("/api/v1/transactions", json=payload_b)
    assert r4.status_code == 200
    tx4 = r4.json()["data"]
    assert tx4["transaction_id"] == tx2_id
    assert tx4["idempotency_key"] == shared_key


@pytest.mark.asyncio
async def test_same_tenant_replay_returns_existing_decision(auth_client):
    """Within the same tenant, replaying returns the existing decision."""
    key = f"same-tenant-{uuid.uuid4().hex}"

    payload = {
        "sender_name": "Test Sender",
        "receiver_name": "Test Receiver",
        "amount": 2000.0,
        "currency": "USD",
        "transaction_type": "wire",
        "destination_country": "US",
        "idempotency_key": key,
    }

    # First submission
    r1 = await auth_client.post("/api/v1/transactions", json=payload)
    assert r1.status_code == 200
    tx1 = r1.json()["data"]

    # Replay with same key
    r2 = await auth_client.post("/api/v1/transactions", json=payload)
    assert r2.status_code == 200
    tx2 = r2.json()["data"]

    # Should return the same transaction
    assert tx1["transaction_id"] == tx2["transaction_id"]
    assert tx1["status"] == tx2["status"]
    assert tx1["risk_score"] == tx2["risk_score"]

