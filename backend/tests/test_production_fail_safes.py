"""S7.5: Production fail-safes — startup checks and stale-list degradation."""
import os

os.environ["APP_ENV"] = "test"

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import system_session
from app.db_models import ListImport, WatchlistEntry


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_login(client: AsyncClient, email: str, role: str = "admin") -> tuple[str, str]:
    """Register a user and return their access token and tenant_id."""
    import uuid
    email = f"{uuid.uuid4().hex[:8]}@test.io"
    res = await client.post("/api/auth/register", json={
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
        "company": "Test Corp",
    })
    assert res.status_code == 201, f"Register failed: {res.status_code} {res.text}"
    token = res.json()["access_token"]

    db = system_session()
    try:
        from app.db_models import User
        user = db.query(User).filter(User.email == email).first()
        user.role = role
        db.commit()
        return token, user.tenant_id
    finally:
        db.close()


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient):
    token, _ = await _register_and_login(client, "admin@test.io", "admin")
    return {"Authorization": f"Bearer {token}"}


def test_startup_refuses_production_with_simulated_payments(monkeypatch):
    """APP_ENV=production with PAYMENTS_MODE=simulated refuses to start unless ALLOW_SIMULATED_PAYMENTS=true."""
    from app.main import startup
    import asyncio

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_MODE", "simulated")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "test-key-for-startup-check-must-be-32-chars!!")
    monkeypatch.delenv("ALLOW_SIMULATED_PAYMENTS", raising=False)

    with pytest.raises(RuntimeError, match="ALLOW_SIMULATED_PAYMENTS=true"):
        asyncio.get_event_loop().run_until_complete(startup())


def test_startup_allows_production_with_simulated_payments_when_explicitly_allowed(monkeypatch):
    """APP_ENV=production with PAYMENTS_MODE=simulated starts when ALLOW_SIMULATED_PAYMENTS=true."""
    from app.main import startup
    import asyncio

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_MODE", "simulated")
    monkeypatch.setenv("ALLOW_SIMULATED_PAYMENTS", "true")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "test-key-for-startup-check-must-be-32-chars!!")

    # Should not raise
    asyncio.get_event_loop().run_until_complete(startup())


def test_startup_allows_production_with_stripe_payments(monkeypatch):
    """APP_ENV=production with PAYMENTS_MODE=stripe starts without ALLOW_SIMULATED_PAYMENTS."""
    from app.main import startup
    import asyncio

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_MODE", "stripe")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "test-key-for-startup-check-must-be-32-chars!!")
    monkeypatch.delenv("ALLOW_SIMULATED_PAYMENTS", raising=False)

    # Should not raise
    asyncio.get_event_loop().run_until_complete(startup())


def test_lists_demo_fixtures_defaults_to_false_outside_development(monkeypatch):
    """LISTS_DEMO_FIXTURES defaults to false when APP_ENV != development."""
    from scripts.bootstrap import _flag

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("LISTS_DEMO_FIXTURES", raising=False)

    assert _flag("LISTS_DEMO_FIXTURES") is False


def test_lists_demo_fixtures_defaults_to_true_in_development(monkeypatch):
    """LISTS_DEMO_FIXTURES defaults to true when APP_ENV = development."""
    from scripts.bootstrap import _flag

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("LISTS_DEMO_FIXTURES", raising=False)

    assert _flag("LISTS_DEMO_FIXTURES") is True


def test_lists_demo_fixtures_respects_explicit_value(monkeypatch):
    """LISTS_DEMO_FIXTURES respects explicit value regardless of APP_ENV."""
    from scripts.bootstrap import _flag

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LISTS_DEMO_FIXTURES", "true")

    assert _flag("LISTS_DEMO_FIXTURES") is True


@pytest.mark.asyncio
async def test_stale_sanctions_list_degrades_decision_to_in_review(client: AsyncClient, admin_headers: dict):
    """A stale sanctions list (older than lists.max_age_hours) degrades the decision to in_review."""
    from app import config_service

    db = system_session()
    try:
        # Get admin user ID for actor_id
        from app.db_models import User
        admin_user = db.query(User).filter(User.role == "admin").first()
        actor_id = admin_user.id if admin_user else "system"

        # Set max_age_hours to 1 hour
        config_service.set_setting(db, "lists.max_age_hours", 1.0, actor_id)

        # Insert a sanctions list import that is 2 hours old (stale)
        db.query(ListImport).filter(ListImport.source == "OFAC").delete()
        db.query(WatchlistEntry).filter(WatchlistEntry.source == "OFAC").delete()
        db.commit()

        old_import = ListImport(
            source="OFAC",
            list_type="sanctions",
            list_version="2024-01-01",
            entry_count=1,
            imported_at=datetime.utcnow() - timedelta(hours=2),
            is_fixture=True,
        )
        db.add(old_import)
        db.add(WatchlistEntry(
            id="test-stale-1",
            source="OFAC",
            list_version="2024-01-01",
            list_type="sanctions",
            primary_name="TEST STALE",
            aliases=[],
            entity_type="individual",
            country="US",
            effective_from=datetime.utcnow() - timedelta(days=365),
        ))
        db.commit()
    finally:
        db.close()

    # Screen a transaction
    res = await client.post("/api/v1/transactions", headers=admin_headers, json={
        "amount": 1000.0,
        "transaction_type": "wire",
        "sender_name": "Test User",
        "receiver_name": "Receiver",
        "idempotency_key": "stale-list-test-" + __import__('uuid').uuid4().hex,
    })
    assert res.status_code == 200
    data = res.json()["data"]

    # Decision should be in_review due to stale list
    assert data["status"] == "in_review"
    assert data["degraded"] is True
    assert "list_stale" in data["degraded_dependencies"]


@pytest.mark.asyncio
async def test_missing_sanctions_list_degrades_decision_to_in_review(client: AsyncClient, admin_headers: dict):
    """A missing sanctions list degrades the decision to in_review."""
    from app import config_service

    db = system_session()
    try:
        from app.db_models import User
        admin_user = db.query(User).filter(User.role == "admin").first()
        actor_id = admin_user.id if admin_user else "system"

        # Set max_age_hours to 24 hours
        config_service.set_setting(db, "lists.max_age_hours", 24.0, actor_id)

        # Delete all sanctions list imports
        db.query(ListImport).filter(ListImport.list_type == "sanctions").delete()
        db.query(WatchlistEntry).filter(WatchlistEntry.list_type == "sanctions").delete()
        db.commit()
    finally:
        db.close()

    # Screen a transaction
    res = await client.post("/api/v1/transactions", headers=admin_headers, json={
        "amount": 1000.0,
        "transaction_type": "wire",
        "sender_name": "Test User",
        "receiver_name": "Receiver",
        "idempotency_key": "missing-list-test-" + __import__('uuid').uuid4().hex,
    })
    assert res.status_code == 200
    data = res.json()["data"]

    # Decision should be in_review due to missing list
    assert data["status"] == "in_review"
    assert data["degraded"] is True
    assert "list_stale" in data["degraded_dependencies"]


@pytest.mark.asyncio
async def test_fresh_sanctions_list_does_not_degrade(client: AsyncClient, admin_headers: dict):
    """A fresh sanctions list does not add list_stale to degraded_dependencies."""
    from app import config_service

    db = system_session()
    try:
        from app.db_models import User
        admin_user = db.query(User).filter(User.role == "admin").first()
        actor_id = admin_user.id if admin_user else "system"

        # Set max_age_hours to 24 hours
        config_service.set_setting(db, "lists.max_age_hours", 24.0, actor_id)

        # Insert a fresh sanctions list import (1 hour old)
        db.query(ListImport).filter(ListImport.source == "OFAC").delete()
        db.query(WatchlistEntry).filter(WatchlistEntry.source == "OFAC").delete()
        db.commit()

        fresh_import = ListImport(
            source="OFAC",
            list_type="sanctions",
            list_version="2024-01-02",
            entry_count=1,
            imported_at=datetime.utcnow() - timedelta(hours=1),
            is_fixture=True,
        )
        db.add(fresh_import)
        db.add(WatchlistEntry(
            id="test-fresh-1",
            source="OFAC",
            list_version="2024-01-02",
            list_type="sanctions",
            primary_name="TEST FRESH",
            aliases=[],
            entity_type="individual",
            country="US",
            effective_from=datetime.utcnow() - timedelta(days=365),
        ))
        db.commit()
    finally:
        db.close()

    # Screen a transaction
    res = await client.post("/api/v1/transactions", headers=admin_headers, json={
        "amount": 1000.0,
        "transaction_type": "wire",
        "sender_name": "Test User",
        "receiver_name": "Receiver",
        "idempotency_key": "fresh-list-test-" + __import__('uuid').uuid4().hex,
    })
    assert res.status_code == 200
    data = res.json()["data"]

    # list_stale should NOT be in degraded_dependencies
    assert "list_stale" not in (data.get("degraded_dependencies") or [])
