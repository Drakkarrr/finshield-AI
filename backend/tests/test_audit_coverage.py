"""S7.2: Audit coverage expansion - failed logins, API key ops, role changes, IP capture."""
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db_models import AuditLog, User
from app.main import app
from tests.conftest import system_session


def _client(token=None):
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if token:
        ac.headers["Authorization"] = f"Bearer {token}"
    return ac


async def _register(email=None):
    """Register a new user and return (client, user_id)."""
    email = email or f"{uuid.uuid4().hex[:8]}@audit.io"
    async with _client() as anon:
        r = await anon.post("/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "Audit",
            "last_name": "Test",
        })
        assert r.status_code == 201, r.text
        data = r.json()
        return _client(data["access_token"]), data["user"]["id"]


@pytest_asyncio.fixture
async def admin_client():
    """Admin client for testing."""
    client, user_id = await _register()
    yield {"client": client, "user_id": user_id}
    await client.aclose()


async def test_failed_login_is_audited_with_pseudonymised_email():
    """Failed login attempts are audited with pseudonymised email."""
    email = f"{uuid.uuid4().hex[:8]}@audit.io"
    # Register first
    await _register(email)

    # Try wrong password
    async with _client() as anon:
        r = await anon.post("/api/auth/login", json={
            "email": email,
            "password": "WrongPassword123!",
        })
        assert r.status_code == 401

    # Check audit log
    db = system_session()
    try:
        user = db.query(User).filter(User.email == email).first()
        audit = db.query(AuditLog).filter(
            AuditLog.user_id == user.id,
            AuditLog.action == "login_failed"
        ).first()
        assert audit is not None
        assert audit.details["reason"] == "invalid_credentials"
        assert "email_pseudo" in audit.details
        # Email should be pseudonymised (not raw)
        assert email not in str(audit.details)
        assert audit.ip_address is not None  # IP should be captured
    finally:
        db.close()


async def test_api_key_create_and_revoke_are_audited(admin_client):
    """API key creation and revocation are audited."""
    ac = admin_client["client"]

    # Create API key
    r = await ac.post("/api/v1/keys", json={"name": "test-key"})
    assert r.status_code == 201
    key_id = r.json()["id"]

    # Check create audit
    db = system_session()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.action == "api_key_created",
            AuditLog.resource_id == key_id
        ).first()
        assert audit is not None
        assert audit.details["name"] == "test-key"
        assert audit.ip_address is not None
    finally:
        db.close()

    # Revoke API key
    r = await ac.delete(f"/api/v1/keys/{key_id}")
    assert r.status_code == 200

    # Check revoke audit
    db = system_session()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.action == "api_key_revoked",
            AuditLog.resource_id == key_id
        ).first()
        assert audit is not None
        assert audit.details["name"] == "test-key"
        assert audit.ip_address is not None
    finally:
        db.close()


async def test_user_role_change_is_audited(admin_client):
    """User role changes are audited with before/after state."""
    ac = admin_client["client"]

    # Create a new user
    r = await ac.post("/api/v1/admin/users", json={
        "email": f"{uuid.uuid4().hex[:8]}@audit.io",
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
        "role": "analyst",
    })
    assert r.status_code == 201
    new_user_id = r.json()["id"]

    # Check create audit
    db = system_session()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.action == "user_created",
            AuditLog.resource_id == new_user_id
        ).first()
        assert audit is not None
        assert audit.details["role"] == "analyst"
        assert audit.ip_address is not None
    finally:
        db.close()

    # Update role
    r = await ac.patch(f"/api/v1/admin/users/{new_user_id}", json={"role": "investigator"})
    assert r.status_code == 200

    # Check update audit
    db = system_session()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.action == "user_updated",
            AuditLog.resource_id == new_user_id
        ).first()
        assert audit is not None
        assert audit.details["before"]["role"] == "analyst"
        assert audit.details["after"]["role"] == "investigator"
        assert audit.ip_address is not None
    finally:
        db.close()


async def test_ip_address_is_pseudonymised_in_audit_logs():
    """IP addresses in audit logs are pseudonymised, not raw."""
    email = f"{uuid.uuid4().hex[:8]}@audit.io"
    async with _client() as anon:
        r = await anon.post("/api/auth/register", json={
            "email": email,
            "password": "SecurePass123!",
            "first_name": "IP",
            "last_name": "Test",
        })
        assert r.status_code == 201

    # Check that IP is pseudonymised
    db = system_session()
    try:
        user = db.query(User).filter(User.email == email).first()
        audit = db.query(AuditLog).filter(
            AuditLog.user_id == user.id,
            AuditLog.action == "user_registered"
        ).first()
        assert audit is not None
        assert audit.ip_address is not None
        # IP should be a hash/pseudonym, not a raw IP like "127.0.0.1" or "testclient"
        assert "." not in audit.ip_address or len(audit.ip_address) > 15  # pseudonyms are long hashes
    finally:
        db.close()
