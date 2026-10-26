"""S7.1: Retention-safe deletes — transactions and cases."""
import uuid
from datetime import datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db_models import AuditLog, Transaction
from app.main import app
from tests.conftest import system_session


def _client(token=None):
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if token:
        ac.headers["Authorization"] = f"Bearer {token}"
    return ac


@pytest_asyncio.fixture
async def org():
    """Create a user and some test transactions."""
    async with _client() as anon:
        r = await anon.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex[:8]}@s71.io",
            "password": "SecurePass123!",
            "first_name": "S",
            "last_name": "Seven",
        })
    admin = _client(r.json()["access_token"])

    # Create transactions: one recent, one old (outside retention)
    recent_tx = (await admin.post("/api/v1/transactions", json={
        "amount": 1000.0, "currency": "USD", "transaction_type": "wire",
        "sender_name": "John Doe", "receiver_name": "Jane Smith",
        "idempotency_key": uuid.uuid4().hex,
    })).json()["data"]["transaction_id"]

    old_tx = (await admin.post("/api/v1/transactions", json={
        "amount": 2000.0, "currency": "USD", "transaction_type": "wire",
        "sender_name": "Old Sender", "receiver_name": "Old Receiver",
        "idempotency_key": uuid.uuid4().hex,
    })).json()["data"]["transaction_id"]

    # Make old_tx actually old (6 years ago, outside 5-year retention)
    db = system_session()
    try:
        db.get(Transaction, old_tx).created_at = datetime.utcnow() - timedelta(days=6 * 365)
        db.commit()
    finally:
        db.close()

    yield {"admin": admin, "recent": recent_tx, "old": old_tx}
    await admin.aclose()


async def test_delete_inside_retention_window_refused(org):
    """Delete within retention window returns 409 with eligible_from."""
    ac = org["admin"]
    res = await ac.delete(f"/api/v1/transactions/{org['recent']}")
    assert res.status_code == 409
    body = res.json()
    assert "retention" in body["detail"].lower() or "eligible" in body["detail"].lower()

    # Verify transaction still exists
    db = system_session()
    try:
        tx = db.get(Transaction, org["recent"])
        assert tx is not None
    finally:
        db.close()

    # Verify audit entry
    db = system_session()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.resource_id == org["recent"],
            AuditLog.action == "delete_refused"
        ).first()
        assert audit is not None
    finally:
        db.close()


async def test_delete_linked_to_case_refused(org):
    """Delete of transaction linked to a case returns 409."""
    ac = org["admin"]

    # Create a case linked to the old transaction
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["old"],
        "reason": "Test case for retention",
    })
    assert case_res.status_code == 201

    # Try to delete the transaction
    res = await ac.delete(f"/api/v1/transactions/{org['old']}")
    assert res.status_code == 409
    assert "linked" in res.json()["detail"].lower()


async def test_delete_linked_to_filing_refused(org):
    """Delete of transaction linked to a filing returns 409."""
    ac = org["admin"]

    # Create a case and resolve it as suspicious
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["old"],
        "reason": "Test case for filing",
    })
    case_id = case_res.json()["case_id"]

    # Resolve the case as suspicious (required for filing)
    await ac.patch(f"/api/v1/cases/{case_id}", json={
        "status": "resolved",
        "resolution": "confirmed_suspicious",
        "resolution_summary": "Test resolution",
    })

    filing_res = await ac.post("/api/v1/filings", json={
        "case_id": case_id,
        "filing_type": "SAR",
        "narrative": "Test SAR",
    })
    assert filing_res.status_code == 201

    # Try to delete the transaction
    res = await ac.delete(f"/api/v1/transactions/{org['old']}")
    assert res.status_code == 409


async def test_delete_outside_retention_pseudonymises(org):
    """Delete outside retention window pseudonymises instead of hard delete."""
    ac = org["admin"]

    # Create a case for old_tx first (so we can delete the case later)
    # Actually, we need a transaction NOT linked to any case
    # Let's create a new old transaction
    new_old_tx = (await ac.post("/api/v1/transactions", json={
        "amount": 3000.0, "currency": "USD", "transaction_type": "wire",
        "sender_name": "Very Old Sender", "receiver_name": "Very Old Receiver",
        "idempotency_key": uuid.uuid4().hex,
    })).json()["data"]["transaction_id"]

    db = system_session()
    try:
        db.get(Transaction, new_old_tx).created_at = datetime.utcnow() - timedelta(days=6 * 365)
        db.commit()
    finally:
        db.close()

    # Delete should succeed and pseudonymise
    res = await ac.delete(f"/api/v1/transactions/{new_old_tx}")
    assert res.status_code == 200
    assert res.json().get("pseudonymised") == new_old_tx

    # Verify transaction still exists but is pseudonymised
    db = system_session()
    try:
        tx = db.get(Transaction, new_old_tx)
        assert tx is not None
        assert tx.sender_name != "Very Old Sender"  # Should be pseudonymised
    finally:
        db.close()


async def test_delete_case_with_filing_refused(org):
    """Delete of case with a linked filing returns 409."""
    ac = org["admin"]

    # Create a case and resolve it as suspicious
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["recent"],
        "reason": "Test case for delete",
    })
    case_id = case_res.json()["case_id"]

    # Resolve the case as suspicious (required for filing)
    await ac.patch(f"/api/v1/cases/{case_id}", json={
        "status": "resolved",
        "resolution": "confirmed_suspicious",
        "resolution_summary": "Test resolution",
    })

    filing_res = await ac.post("/api/v1/filings", json={
        "case_id": case_id,
        "filing_type": "SAR",
        "narrative": "Test SAR for delete",
    })
    assert filing_res.status_code == 201

    # Try to delete the case
    res = await ac.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 409
    assert "filing" in res.json()["detail"].lower()


async def test_delete_case_without_filing_succeeds(org):
    """Delete of case without filing succeeds and is audited."""
    ac = org["admin"]

    # Create a case without filing
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["old"],
        "reason": "Test case for delete success",
    })
    case_id = case_res.json()["case_id"]

    # Make the case old (6 years ago)
    db = system_session()
    try:
        from app.db_models import Case
        case = db.get(Case, case_id)
        case.created_at = datetime.utcnow() - timedelta(days=6 * 365)
        db.commit()
    finally:
        db.close()

    # Delete should succeed
    res = await ac.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 200
    assert res.json().get("deleted") == case_id

    # Verify audit entry
    db = system_session()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.resource_id == case_id,
            AuditLog.action == "case_deleted"
        ).first()
        assert audit is not None
    finally:
        db.close()


async def test_delete_open_case_refused(org):
    """Delete of an open case returns 409 (within retention)."""
    ac = org["admin"]

    # Create an open case
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["recent"],
        "reason": "Open case test",
    })
    case_id = case_res.json()["case_id"]

    # Delete should be refused (within retention window)
    res = await ac.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 409
    assert "retention" in res.json()["detail"].lower() or "eligible" in res.json()["detail"].lower()


async def test_delete_recently_resolved_case_refused(org):
    """Delete of a recently resolved case returns 409."""
    ac = org["admin"]

    # Create and resolve a case
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["recent"],
        "reason": "Resolved case test",
    })
    case_id = case_res.json()["case_id"]

    await ac.patch(f"/api/v1/cases/{case_id}", json={
        "status": "resolved",
        "resolution": "false_positive",
        "resolution_summary": "Test resolution",
    })

    # Delete should be refused (within retention window)
    res = await ac.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 409


async def test_delete_old_resolved_case_succeeds(org):
    """Delete of a case resolved more than 5 years ago succeeds."""
    ac = org["admin"]

    # Create and resolve a case
    case_res = await ac.post("/api/v1/cases", json={
        "transaction_id": org["old"],
        "reason": "Old resolved case test",
    })
    case_id = case_res.json()["case_id"]

    await ac.patch(f"/api/v1/cases/{case_id}", json={
        "status": "resolved",
        "resolution": "false_positive",
        "resolution_summary": "Test resolution",
    })

    # Make the case old (6 years ago)
    db = system_session()
    try:
        from app.db_models import Case
        case = db.get(Case, case_id)
        case.resolved_at = datetime.utcnow() - timedelta(days=6 * 365)
        case.created_at = datetime.utcnow() - timedelta(days=6 * 365)
        db.commit()
    finally:
        db.close()

    # Delete should succeed
    res = await ac.delete(f"/api/v1/cases/{case_id}")
    assert res.status_code == 200
    assert res.json().get("deleted") == case_id
