"""S1.4: runtime settings, feature flags and rule priority / effective windows."""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db_models import AuditLog
from app.main import app
from tests.conftest import system_session


@pytest_asyncio.fixture
async def fresh_client():
    """A client for a brand-new user, so per-user rule overrides do not leak between tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex[:8]}@settings.io", "password": "SecurePass123!",
            "first_name": "Set", "last_name": "Tings",
        })
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        ac.user_id = r.json()["user"]["id"]
        yield ac


def _wire(amount: float, **kw) -> dict:
    return {"amount": amount, "currency": "USD", "transaction_type": "wire", "sender_name": "Plain Sender",
            "receiver_name": "Plain Receiver", "idempotency_key": f"set-{uuid.uuid4().hex}", **kw}


def _rule(data: dict, rule_id: str) -> dict:
    return next(r for r in data["data"]["rule_results"] if r["rule_id"] == rule_id)


@pytest.mark.asyncio
async def test_settings_list_has_every_key_with_defaults(fresh_client):
    resp = await fresh_client.get("/api/v1/settings")
    assert resp.status_code == 200
    by_key = {s["key"]: s for s in resp.json()}
    assert by_key["rules.threshold.wire"]["default"] == 10000.0
    assert by_key["risk.weights"]["default"] == {"rules": 0.5, "behavioral": 0.3, "model": 0.2}
    assert {"billing.plans", "billing.credit_packs", "decision.bands", "behavioral.trigger.warm"} <= set(by_key)


@pytest.mark.asyncio
async def test_threshold_change_takes_effect_without_restart_and_is_audited(fresh_client):
    before = await fresh_client.post("/api/v1/transactions", json=_wire(5000.0))
    assert _rule(before.json(), "RULE-003")["triggered"] is False

    try:
        put = await fresh_client.put("/api/v1/settings/rules.threshold.wire", json={"value": 4000.0})
        assert put.status_code == 200
        after = await fresh_client.post("/api/v1/transactions", json=_wire(5000.0))
        assert _rule(after.json(), "RULE-003")["triggered"] is True
        assert after.json()["data"]["status"] == "in_review"  # RULE-003's action is review
    finally:
        await fresh_client.put("/api/v1/settings/rules.threshold.wire", json={"value": 10000.0})

    db = system_session()
    try:
        row = (db.query(AuditLog)
               .filter(AuditLog.action == "setting_changed", AuditLog.resource_id == "rules.threshold.wire",
                       AuditLog.user_id == fresh_client.user_id)
               .order_by(AuditLog.created_at).first())
        assert row is not None
        assert row.details == {"before": 10000.0, "after": 4000.0}
    finally:
        db.close()


@pytest.mark.asyncio
async def test_invalid_and_unknown_settings_are_rejected(fresh_client):
    assert (await fresh_client.put("/api/v1/settings/rules.threshold.wire", json={"value": -1})).status_code == 422
    assert (await fresh_client.put("/api/v1/settings/risk.weights",
                                   json={"value": {"rules": 0.9, "behavioral": 0.3, "model": 0.2}})).status_code == 422
    assert (await fresh_client.put("/api/v1/settings/no.such.key", json={"value": 1})).status_code == 404
    assert (await fresh_client.put("/api/v1/flags/no.such.flag", json={"enabled": True})).status_code == 404


@pytest.mark.asyncio
async def test_flag_disables_behavioral_stage(fresh_client):
    try:
        assert (await fresh_client.put("/api/v1/flags/screening.behavioral", json={"enabled": False})).status_code == 200
        resp = await fresh_client.post("/api/v1/transactions", json=_wire(7000.0))
        assert "behavioral_analysis" not in resp.json()["data"]["pipeline_stages"]
        assert resp.json()["data"]["behavioral_score"] is None
    finally:
        await fresh_client.put("/api/v1/flags/screening.behavioral", json={"enabled": True})
    resp = await fresh_client.post("/api/v1/transactions", json=_wire(7000.0))
    assert "behavioral_analysis" in resp.json()["data"]["pipeline_stages"]


@pytest.mark.asyncio
async def test_rule_priority_sets_execution_order(fresh_client):
    # Priority changes require approval (S7.4)
    patch = await fresh_client.patch("/api/v1/rules/RULE-004", json={"priority": 1})
    assert patch.status_code == 200
    cr_id = patch.json()["change_request_id"]

    # Create a second admin to approve
    import uuid
    from datetime import datetime, timedelta

    from app.auth import hash_password
    from app.db_models import ChangeRequest, User
    db = system_session()
    try:
        cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
        tenant_id = cr.tenant_id
        admin2 = User(
            email=f"{uuid.uuid4().hex[:8]}@settings.io",
            hashed_password=hash_password("SecurePass123!"),
            first_name="Admin2",
            last_name="Test",
            company="Test Corp",
            role="admin",
            tenant_id=tenant_id,
            trial_expires_at=datetime.utcnow() + timedelta(days=365),
        )
        db.add(admin2)
        db.commit()
        admin2_email = admin2.email
    finally:
        db.close()

    # Login as admin2 and approve
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac2:
        login_res = await ac2.post("/api/auth/login", json={"email": admin2_email, "password": "SecurePass123!"})
        token2 = login_res.json()["access_token"]
        ac2.headers["Authorization"] = f"Bearer {token2}"
        approved = await ac2.post(f"/api/v1/change-requests/{cr_id}/approve", json={})
        assert approved.status_code == 200

    listed = await fresh_client.get("/api/v1/rules")
    assert listed.json()[0]["rule_id"] == "RULE-004"
    resp = await fresh_client.post("/api/v1/transactions", json=_wire(10.0))
    assert resp.json()["data"]["rule_results"][0]["rule_id"] == "RULE-004"


@pytest.mark.asyncio
async def test_lapsed_override_falls_back_to_the_builtin_rule(fresh_client):
    past = (datetime.utcnow() - timedelta(days=2)).isoformat()
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    patch = await fresh_client.patch("/api/v1/rules/RULE-003", json={
        "custom_parameters": {"wire": 100.0}, "effective_from": past, "effective_to": yesterday,
    })
    assert patch.status_code == 200
    resp = await fresh_client.post("/api/v1/transactions", json=_wire(5000.0))
    assert _rule(resp.json(), "RULE-003")["triggered"] is False  # default 10,000 threshold applies
    rule = next(r for r in (await fresh_client.get("/api/v1/rules")).json() if r["rule_id"] == "RULE-003")
    assert rule["override_active"] is False and rule["parameters"]["wire"] == 10000.0


@pytest.mark.asyncio
async def test_lapsed_disable_cannot_switch_off_sanctions_screening(fresh_client):
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    await fresh_client.patch("/api/v1/rules/RULE-001", json={"enabled": False, "effective_to": yesterday})
    resp = await fresh_client.post("/api/v1/transactions", json=_wire(10.0, sender_name="darkfund"))
    assert _rule(resp.json(), "RULE-001")["triggered"] is True
    assert resp.json()["data"]["status"] == "blocked"


@pytest.mark.asyncio
async def test_rule_update_bumps_version_and_audits_before_after(fresh_client):
    # Disable requires approval (S7.4)
    first = await fresh_client.patch("/api/v1/rules/RULE-002", json={"enabled": False})
    assert first.status_code == 200
    cr_id1 = first.json()["change_request_id"]

    # Create a second admin to approve
    import uuid
    from datetime import datetime, timedelta

    from app.auth import hash_password
    from app.db_models import ChangeRequest, User
    db = system_session()
    try:
        cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id1).first()
        tenant_id = cr.tenant_id
        admin2 = User(
            email=f"{uuid.uuid4().hex[:8]}@settings.io",
            hashed_password=hash_password("SecurePass123!"),
            first_name="Admin2",
            last_name="Test",
            company="Test Corp",
            role="admin",
            tenant_id=tenant_id,
            trial_expires_at=datetime.utcnow() + timedelta(days=365),
        )
        db.add(admin2)
        db.commit()
        admin2_email = admin2.email
    finally:
        db.close()

    # Login as admin2 and approve
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac2:
        login_res = await ac2.post("/api/auth/login", json={"email": admin2_email, "password": "SecurePass123!"})
        token2 = login_res.json()["access_token"]
        ac2.headers["Authorization"] = f"Bearer {token2}"
        approved = await ac2.post(f"/api/v1/change-requests/{cr_id1}/approve", json={})
        assert approved.status_code == 200

    # Re-enable is applied directly (doesn't require approval)
    second = await fresh_client.patch("/api/v1/rules/RULE-002", json={"enabled": True})
    assert second.status_code == 200
    assert second.json()["version"] == 2

    # Check audit trail - should have entries from both the approval and the direct update
    bad = await fresh_client.patch("/api/v1/rules/RULE-002", json={
        "effective_from": datetime.utcnow().isoformat(),
        "effective_to": (datetime.utcnow() - timedelta(days=1)).isoformat(),
    })
    assert bad.status_code == 422
    db = system_session()
    try:
        # Get the admin2's user_id (the approver)
        admin2_user = db.query(User).filter(User.email == admin2_email).first()
        admin2_user_id = admin2_user.id

        # Get audit entries from either the proposer or the approver
        rows = (db.query(AuditLog).filter(AuditLog.action == "rule_updated", AuditLog.resource_id == "RULE-002",
                                          AuditLog.user_id.in_([fresh_client.user_id, admin2_user_id])).order_by(AuditLog.created_at).all())
        assert len(rows) >= 2, f"Expected at least 2 audit entries, got {len(rows)}"
        # Check that we have version 1 (from approval) and version 2 (from re-enable)
        versions = [r.details["after"]["version"] for r in rows]
        assert 1 in versions and 2 in versions, f"Expected versions [1, 2], got {versions}"
        assert rows[1].details["before"]["enabled"] is False and rows[1].details["after"]["enabled"] is True
    finally:
        db.close()
