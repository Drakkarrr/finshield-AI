"""Tests for S7.4: Four-eyes approval workflow for detection changes."""
import os

os.environ["APP_ENV"] = "test"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

# Module-level storage for tenant_id
_test_tenant_id = None


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_login(client: AsyncClient, email: str, role: str = "admin", tenant_id: str = None) -> tuple[str, str]:
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

    # Get the user's tenant_id using RLS bypass
    from tests.conftest import system_session
    db = system_session()
    try:
        from app.db_models import User
        user = db.query(User).filter(User.email == email).first()
        user_tenant_id = user.tenant_id
        user.role = role
        # If a tenant_id was provided, move the user to that tenant
        if tenant_id:
            user.tenant_id = tenant_id
        db.commit()
        return token, user_tenant_id
    finally:
        db.close()


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient):
    global _test_tenant_id
    token, tenant_id = await _register_and_login(client, "admin@test.io", "admin")
    _test_tenant_id = tenant_id
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def supervisor_headers(client: AsyncClient):
    global _test_tenant_id
    # Use the same tenant as admin
    token, _ = await _register_and_login(client, "supervisor@test.io", "supervisor", _test_tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_model_promote_creates_change_request(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """Model promotion creates a pending change request, not an immediate promotion."""
    # Register a shadow model
    res = await client.post("/api/v1/models", headers=admin_headers, json={
        "name": "test-model",
        "params": {
            "bias": -3.0,
            "weights": {"amount_log": 2.5, "country_risk": 2.0, "counterparty_risk": 2.5, "rag_signal": 1.5, "velocity": 1.5, "type_risk": 1.0},
            "labels": {"medium_risk": 0.4, "high_risk": 0.7},
        },
        "model_card": {"intended_use": "test"},
    })
    assert res.status_code == 201
    version_id = res.json()["id"]

    # Propose promotion
    res = await client.post(f"/api/v1/models/{version_id}/promote", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "pending"
    change_request_id = res.json()["change_request_id"]

    # Verify the model is still shadow (not promoted yet)
    res = await client.get("/api/v1/models", headers=admin_headers)
    model = next(m for m in res.json() if m["id"] == version_id)
    assert model["status"] == "shadow"

    # Verify change request exists
    res = await client.get(f"/api/v1/change-requests/{change_request_id}", headers=admin_headers)
    assert res.status_code == 200
    cr = res.json()
    assert cr["change_type"] == "model_promote"
    assert cr["resource_id"] == version_id
    assert cr["status"] == "pending"


@pytest.mark.asyncio
async def test_self_approval_refused(client: AsyncClient, admin_headers: dict):
    """Cannot approve your own change request."""
    # Register and propose
    res = await client.post("/api/v1/models", headers=admin_headers, json={
        "name": "test-model-2",
        "params": {
            "bias": -3.0,
            "weights": {"amount_log": 2.5, "country_risk": 2.0, "counterparty_risk": 2.5, "rag_signal": 1.5, "velocity": 1.5, "type_risk": 1.0},
            "labels": {"medium_risk": 0.4, "high_risk": 0.7},
        },
        "model_card": {"intended_use": "test"},
    })
    version_id = res.json()["id"]
    res = await client.post(f"/api/v1/models/{version_id}/promote", headers=admin_headers)
    change_request_id = res.json()["change_request_id"]

    # Try to approve your own request
    res = await client.post(f"/api/v1/change-requests/{change_request_id}/approve", headers=admin_headers, json={})
    assert res.status_code == 422
    assert "Cannot approve your own change request" in res.json()["detail"]


@pytest.mark.asyncio
async def test_different_supervisor_can_approve(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """A different supervisor can approve the change request."""
    # Admin proposes
    res = await client.post("/api/v1/models", headers=admin_headers, json={
        "name": "test-model-3",
        "params": {
            "bias": -3.0,
            "weights": {"amount_log": 2.5, "country_risk": 2.0, "counterparty_risk": 2.5, "rag_signal": 1.5, "velocity": 1.5, "type_risk": 1.0},
            "labels": {"medium_risk": 0.4, "high_risk": 0.7},
        },
        "model_card": {"intended_use": "test"},
    })
    version_id = res.json()["id"]
    res = await client.post(f"/api/v1/models/{version_id}/promote", headers=admin_headers)
    change_request_id = res.json()["change_request_id"]

    # Supervisor approves
    res = await client.post(f"/api/v1/change-requests/{change_request_id}/approve", headers=supervisor_headers, json={"reason": "Approved for testing"})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    # Verify the model is now active
    res = await client.get("/api/v1/models", headers=admin_headers)
    model = next(m for m in res.json() if m["id"] == version_id)
    assert model["status"] == "active"


@pytest.mark.asyncio
async def test_rule_disable_requires_approval(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """Disabling a rule creates a change request, not an immediate disable."""
    # Propose to disable RULE-002
    res = await client.patch("/api/v1/rules/RULE-002", headers=admin_headers, json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["status"] == "pending"
    change_request_id = res.json()["change_request_id"]

    # Verify the rule is still enabled
    res = await client.get("/api/v1/rules", headers=admin_headers)
    rule = next(r for r in res.json() if r["rule_id"] == "RULE-002")
    assert rule["enabled"] is True

    # Supervisor approves
    res = await client.post(f"/api/v1/change-requests/{change_request_id}/approve", headers=supervisor_headers, json={})
    assert res.status_code == 200

    # Verify the rule is now disabled
    res = await client.get("/api/v1/rules", headers=admin_headers)
    rule = next(r for r in res.json() if r["rule_id"] == "RULE-002")
    assert rule["enabled"] is False


@pytest.mark.asyncio
async def test_rule_001_cannot_be_disabled(client: AsyncClient, admin_headers: dict):
    """RULE-001 (sanctions) cannot be disabled at all."""
    res = await client.patch("/api/v1/rules/RULE-001", headers=admin_headers, json={"enabled": False})
    assert res.status_code == 422
    assert "RULE-001 (sanctions) cannot be disabled" in res.json()["detail"]


@pytest.mark.asyncio
async def test_rule_override_requires_approval(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """Overriding rule parameters creates a change request."""
    # Propose to override RULE-003 parameters
    res = await client.patch("/api/v1/rules/RULE-003", headers=admin_headers, json={
        "custom_parameters": {"threshold": 5000}
    })
    assert res.status_code == 200
    assert res.json()["status"] == "pending"
    change_request_id = res.json()["change_request_id"]

    # Verify the rule has no custom parameters yet
    res = await client.get("/api/v1/rules", headers=admin_headers)
    rule = next(r for r in res.json() if r["rule_id"] == "RULE-003")
    assert rule.get("custom_parameters") is None

    # Supervisor approves
    res = await client.post(f"/api/v1/change-requests/{change_request_id}/approve", headers=supervisor_headers, json={})
    assert res.status_code == 200

    # Verify the rule now has custom parameters (check the actual config, not the list view)
    from app.db_models import RuleConfig, User
    from tests.conftest import system_session
    db = system_session()
    try:
        # Get the admin's tenant_id
        admin_user = db.query(User).filter(User.role == "admin").order_by(User.created_at.desc()).first()
        config = db.query(RuleConfig).filter(
            RuleConfig.rule_id == "RULE-003",
            RuleConfig.tenant_id == admin_user.tenant_id
        ).first()
        assert config is not None
        assert "threshold" in config.custom_parameters
        assert config.custom_parameters["threshold"] == 5000
    finally:
        db.close()


@pytest.mark.asyncio
async def test_duplicate_proposal_rejected(client: AsyncClient, admin_headers: dict):
    """Cannot create a duplicate pending change request for the same resource."""
    # First proposal
    res = await client.patch("/api/v1/rules/RULE-004", headers=admin_headers, json={"enabled": False})
    assert res.status_code == 200

    # Second proposal for the same rule
    res = await client.patch("/api/v1/rules/RULE-004", headers=admin_headers, json={"enabled": False})
    assert res.status_code == 409
    assert "already pending" in res.json()["detail"]


@pytest.mark.asyncio
async def test_change_request_audit_trail(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """Approving a change request creates an audit entry."""
    # Propose and approve
    res = await client.post("/api/v1/models", headers=admin_headers, json={
        "name": "test-model-audit",
        "params": {
            "bias": -3.0,
            "weights": {"amount_log": 2.5, "country_risk": 2.0, "counterparty_risk": 2.5, "rag_signal": 1.5, "velocity": 1.5, "type_risk": 1.0},
            "labels": {"medium_risk": 0.4, "high_risk": 0.7},
        },
        "model_card": {"intended_use": "test"},
    })
    version_id = res.json()["id"]
    res = await client.post(f"/api/v1/models/{version_id}/promote", headers=admin_headers)
    change_request_id = res.json()["change_request_id"]
    res = await client.post(f"/api/v1/change-requests/{change_request_id}/approve", headers=supervisor_headers, json={"reason": "Test approval"})

    # Check audit log
    res = await client.get("/api/v1/audit", headers=supervisor_headers)
    assert res.status_code == 200
    audit_response = res.json()
    audit_entries = audit_response["items"]
    approval_entry = next((e for e in audit_entries if e["action"] == "change_request_approved"), None)
    assert approval_entry is not None
    assert approval_entry["resource_id"] == change_request_id


@pytest.mark.asyncio
async def test_reject_change_request(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """Supervisor can reject a change request."""
    # Propose
    res = await client.patch("/api/v1/rules/RULE-004", headers=admin_headers, json={"enabled": False})
    change_request_id = res.json()["change_request_id"]

    # Reject
    res = await client.post(f"/api/v1/change-requests/{change_request_id}/reject", headers=supervisor_headers, json={"reason": "Not approved"})
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    # Verify the rule is still enabled
    res = await client.get("/api/v1/rules", headers=admin_headers)
    rule = next(r for r in res.json() if r["rule_id"] == "RULE-004")
    assert rule["enabled"] is True


@pytest.mark.asyncio
async def test_change_request_list_filtering(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """List change requests with status filtering."""
    # Create a few change requests (use different rules to avoid conflicts)
    # Note: RULE-001 cannot be disabled, so we use RULE-002 and RULE-003
    await client.patch("/api/v1/rules/RULE-002", headers=admin_headers, json={"enabled": False})
    await client.patch("/api/v1/rules/RULE-003", headers=admin_headers, json={"custom_parameters": {"test": 123}})

    # List all pending
    res = await client.get("/api/v1/change-requests?status=pending", headers=supervisor_headers)
    assert res.status_code == 200
    pending = res.json()
    assert all(cr["status"] == "pending" for cr in pending)


@pytest.mark.asyncio
async def test_engine_runs_rule_001_even_with_preexisting_disabled_config(client: AsyncClient, admin_headers: dict):
    """Engine must run RULE-001 even if a pre-existing RuleConfig has enabled=False."""
    from app.db_models import RuleConfig, User
    from tests.conftest import system_session

    # Insert a disabled RuleConfig for RULE-001 using system_session (RLS bypass)
    db = system_session()
    try:
        admin_user = db.query(User).filter(User.role == "admin").first()
        config = RuleConfig(
            tenant_id=admin_user.tenant_id,
            user_id=admin_user.id,
            rule_id="RULE-001",
            enabled=False,
            priority=100,
            version=1,
        )
        db.add(config)
        db.commit()
    finally:
        db.close()

    # Screen a sanctioned name - should still be blocked
    res = await client.post("/api/v1/transactions", headers=admin_headers, json={
        "amount": 1000.0,
        "transaction_type": "wire",
        "sender_name": "darkfund",  # This matches sanctions list fixture
        "receiver_name": "Receiver",
        "idempotency_key": "rule001-test-" + __import__('uuid').uuid4().hex,
    })
    assert res.status_code == 200
    data = res.json()["data"]
    # Should be blocked by RULE-001
    assert data["status"] == "blocked"
    rule_001_result = next((r for r in data["rule_results"] if r["rule_id"] == "RULE-001"), None)
    assert rule_001_result is not None
    assert rule_001_result["triggered"] is True


@pytest.mark.asyncio
async def test_window_change_on_disabled_rule_requires_approval(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """Extending the window of an approved disable creates a change request."""
    from datetime import datetime, timedelta

    # First, disable RULE-004 with approval
    res = await client.patch("/api/v1/rules/RULE-004", headers=admin_headers, json={"enabled": False})
    assert res.status_code == 200
    cr_id = res.json()["change_request_id"]

    # Approve the disable
    res = await client.post(f"/api/v1/change-requests/{cr_id}/approve", headers=supervisor_headers, json={})
    assert res.status_code == 200

    # Now try to extend the window - should require approval
    future = (datetime.utcnow() + timedelta(days=365)).isoformat()
    res = await client.patch("/api/v1/rules/RULE-004", headers=admin_headers, json={"effective_to": future})
    assert res.status_code == 200
    assert "change_request_id" in res.json()
    assert res.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_rule_proposal_with_datetime_returns_200(client: AsyncClient, admin_headers: dict):
    """A rule proposal with effective_from/effective_to returns 200, not 500."""
    from datetime import datetime, timedelta

    future_from = (datetime.utcnow() + timedelta(days=1)).isoformat()
    future_to = (datetime.utcnow() + timedelta(days=30)).isoformat()

    res = await client.patch("/api/v1/rules/RULE-003", headers=admin_headers, json={
        "custom_parameters": {"wire": 5000},
        "effective_from": future_from,
        "effective_to": future_to,
    })
    assert res.status_code == 200
    assert "change_request_id" in res.json()


@pytest.mark.asyncio
async def test_approved_request_cannot_be_approved_again(client: AsyncClient, admin_headers: dict, supervisor_headers: dict):
    """An approved request can't be approved a second time."""
    # Propose and approve
    res = await client.patch("/api/v1/rules/RULE-004", headers=admin_headers, json={"enabled": False})
    cr_id = res.json()["change_request_id"]

    res = await client.post(f"/api/v1/change-requests/{cr_id}/approve", headers=supervisor_headers, json={})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    # Try to approve again - should fail
    res = await client.post(f"/api/v1/change-requests/{cr_id}/approve", headers=supervisor_headers, json={})
    assert res.status_code == 409
    assert "already approved" in res.json()["detail"].lower()

    # List all (no filter)
    res = await client.get("/api/v1/change-requests", headers=supervisor_headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_approved_window_is_applied_so_a_temporary_disable_lapses(client: AsyncClient, admin_headers: dict,
                                                                        supervisor_headers: dict):
    """The approved window is part of the change: a disable approved until a date must lapse then,
    and an approved window extension must actually take effect."""
    from datetime import datetime, timedelta

    from app.db_models import RuleConfig
    from tests.conftest import system_session

    until = datetime.utcnow().replace(microsecond=0) + timedelta(days=1)
    res = await client.patch("/api/v1/rules/RULE-002", headers=admin_headers,
                             json={"enabled": False, "effective_to": until.isoformat()})
    cr_id = res.json()["change_request_id"]
    assert (await client.post(f"/api/v1/change-requests/{cr_id}/approve", headers=supervisor_headers,
                              json={})).status_code == 200
    me = (await client.get("/api/auth/me", headers=admin_headers)).json()
    db = system_session()
    try:
        cfg = db.query(RuleConfig).filter(RuleConfig.tenant_id == me["tenant_id"], RuleConfig.rule_id == "RULE-002").one()
        assert cfg.enabled is False and cfg.effective_to == until  # not a permanent disable
    finally:
        db.close()

    later = until + timedelta(days=30)
    res = await client.patch("/api/v1/rules/RULE-002", headers=admin_headers, json={"effective_to": later.isoformat()})
    cr_id = res.json()["change_request_id"]
    assert (await client.post(f"/api/v1/change-requests/{cr_id}/approve", headers=supervisor_headers,
                              json={})).status_code == 200
    db = system_session()
    try:
        cfg = db.query(RuleConfig).filter(RuleConfig.tenant_id == me["tenant_id"], RuleConfig.rule_id == "RULE-002").one()
        assert cfg.effective_to == later
    finally:
        db.close()
