"""S3.3: DSAR access export, erasure that preserves what regulation requires, masking."""
import uuid
from datetime import datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db_models import AuditLog, Filing, PrivacyRequest, Transaction
from app.main import app
from tests.conftest import system_session

SUBJECT = "Rosalind Ellsworth-Vane"
RESOLVE = {"status": "resolved", "resolution": "confirmed_suspicious", "resolution_summary": "test"}


def _client(token=None):
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if token:
        ac.headers["Authorization"] = f"Bearer {token}"
    return ac


async def _screen(ac, **kw) -> str:
    body = {"amount": 300.0, "currency": "USD", "transaction_type": "ach", "sender_name": SUBJECT,
            "receiver_name": "Utility Co", "idempotency_key": uuid.uuid4().hex, **kw}
    return (await ac.post("/api/v1/transactions", json=body)).json()["data"]["transaction_id"]


@pytest_asyncio.fixture
async def org():
    async with _client() as anon:
        r = await anon.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@priv.io",
                                                        "password": "SecurePass123!", "first_name": "P",
                                                        "last_name": "Riv"})
    admin = _client(r.json()["access_token"])
    old, recent, filed = await _screen(admin), await _screen(admin), await _screen(admin)
    case = (await admin.post("/api/v1/cases", json={"transaction_id": filed, "reason": "suspicious"})).json()
    await admin.patch(f"/api/v1/cases/{case['case_id']}", json=RESOLVE)
    filing = (await admin.post("/api/v1/filings", json={"case_id": case["case_id"], "filing_type": "SAR",
                                                        "narrative": "n"})).json()
    db = system_session()
    try:  # make one transaction older than the 5-year retention window
        db.get(Transaction, old).created_at = datetime.utcnow() - timedelta(days=6 * 365)
        db.commit()
    finally:
        db.close()
    yield {"admin": admin, "old": old, "recent": recent, "filed": filed, "filing": filing["id"]}
    await admin.aclose()


async def _request(ac, request_type):
    r = await ac.post("/api/v1/privacy/requests", json={"subject_type": "customer", "subject_ref": SUBJECT,
                                                        "request_type": request_type})
    assert r.status_code == 201, r.text
    return r.json()


async def test_access_export_is_complete_and_withholds_filings(org):
    ac = org["admin"]
    created = await _request(ac, "access")
    due = datetime.fromisoformat(created["due_at"]) - datetime.fromisoformat(created["received_at"])
    assert due == timedelta(days=30) and created["subject_ref_masked"] != SUBJECT
    out = (await ac.post(f"/api/v1/privacy/requests/{created['id']}/execute")).json()["outcome"]
    assert {t["id"] for t in out["transactions"]} == {org["old"], org["recent"], org["filed"]}
    assert out["withheld"]["regulatory_filings"] == 1 and "tipping" in out["withheld"]["legal_basis"]
    assert out["audit_entries_referencing_subject"] >= 3  # screening entries, by pseudonym


async def test_erasure_removes_what_it_may_and_retains_what_it_must(org):
    ac = org["admin"]
    created = await _request(ac, "erasure")
    db = system_session()
    try:
        audit_before = db.query(AuditLog).count()
    finally:
        db.close()
    out = (await ac.post(f"/api/v1/privacy/requests/{created['id']}/execute")).json()["outcome"]
    assert out["erased"] == [f"transaction:{org['old']}"]
    retained = {r["record"]: r for r in out["retained"]}
    assert "filing" in retained[f"transaction:{org['filed']}"]["legal_basis"]
    assert "retention" in retained[f"transaction:{org['recent']}"]["reason"]

    db = system_session()
    try:
        erased = db.get(Transaction, org["old"])
        assert SUBJECT not in (erased.sender_name or "") and SUBJECT not in str(erased.decision)
        assert db.get(Transaction, org["filed"]).sender_name == SUBJECT
        assert db.get(Filing, org["filing"]) is not None
        assert db.query(AuditLog).count() >= audit_before  # nothing removed from the trail
        stored = db.get(PrivacyRequest, created["id"])
        assert SUBJECT not in stored.subject_ref_enc and SUBJECT not in (stored.outcome_enc or "")
    finally:
        db.close()
    assert (await ac.get("/api/v1/audit/verify")).json()["ok"]
    assert (await ac.post(f"/api/v1/privacy/requests/{created['id']}/execute")).status_code == 409


async def test_masked_role_cannot_read_unmasked_names_or_accounts(org):
    ac = org["admin"]
    email = f"analyst-{uuid.uuid4().hex[:6]}@priv.io"
    await ac.post("/api/v1/admin/users", json={"email": email, "password": "SecurePass123!", "first_name": "An",
                                               "last_name": "Alyst", "role": "analyst"})
    async with _client() as anon:
        token = (await anon.post("/api/auth/login", json={"email": email, "password": "SecurePass123!"})).json()["access_token"]
    tx = await _screen(ac, account_id="ACC-778899001")
    async with _client(token) as analyst:
        listed = (await analyst.get("/api/v1/transactions")).text
        detail = (await analyst.get(f"/api/v1/transactions/{tx}")).json()
        export = (await analyst.get("/api/v1/transactions/export")).text
        search = (await analyst.get("/api/v1/search", params={"q": "Ellsworth"})).text
    for body in (listed, str(detail), export, search):
        assert SUBJECT not in body
    assert detail["account_id"].endswith("9001") and "ACC-778899001" not in str(detail)
    full = (await ac.get(f"/api/v1/transactions/{tx}")).json()  # admin: unmasked
    assert full["sender_name"] == SUBJECT and full["account_id"] == "ACC-778899001"


async def test_pii_classification_comes_from_config(org):
    out = (await org["admin"].get("/api/v1/privacy/pii-classification")).json()
    assert "sender_name" in out["pii_fields"]["transactions"] and out["masked_roles"] == ["analyst"]
