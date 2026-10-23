"""S3.2: append-only, hash-chained, queryable, exportable audit trail."""
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.database import DATABASE_URL, IS_SQLITE, SessionLocal, bind_tenant
from app.db_models import AuditLog
from app.main import app
from scripts import verify_audit_export

SENDER = "Wilhelmina Quartermaine"


@pytest_asyncio.fixture
async def tenant():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@audit.io",
                                                      "password": "SecurePass123!", "first_name": "Au",
                                                      "last_name": "Dit"})
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        tx = (await ac.post("/api/v1/transactions", json={
            "amount": 20000.0, "currency": "USD", "transaction_type": "wire", "sender_name": SENDER,
            "receiver_name": "Harbour Freight", "idempotency_key": uuid.uuid4().hex})).json()["data"]
        me = (await ac.get("/api/auth/me")).json()
        yield {"client": ac, "tx": tx, "tenant_id": me["tenant_id"]}


async def test_screening_decision_is_audited_with_model_version_and_no_raw_names(tenant):
    ac = tenant["client"]
    page = (await ac.get("/api/v1/audit", params={"action": "transaction_screened"})).json()
    entry = next(e for e in page["items"] if e["resource_id"] == tenant["tx"]["transaction_id"])
    assert entry["details"]["model_version"] == tenant["tx"]["model_version"]
    assert entry["details"]["decision"] == tenant["tx"]["status"]
    assert SENDER not in json.dumps(entry) and entry["details"]["inputs"]["sender"].startswith("ps_")


async def test_verify_seals_and_validates_the_chain(tenant):
    result = (await tenant["client"].get("/api/v1/audit/verify")).json()
    assert result["ok"] and result["verified"] >= 2 and result["pending"] == 0


async def test_tampering_breaks_verification_and_the_export_reports_it(tenant):
    ac = tenant["client"]
    assert (await ac.get("/api/v1/audit/verify")).json()["ok"]
    _tamper(tenant["tenant_id"])
    result = (await ac.get("/api/v1/audit/verify")).json()
    assert not result["ok"] and result["first_break_seq"] == 1
    bundle = (await ac.get("/api/v1/audit/export")).json()
    assert bundle["verification"]["ok"] is False


def _tamper(tenant_id: str) -> None:
    """Rewrite the first sealed entry the way an attacker with DB superuser rights would."""
    if IS_SQLITE:
        db = SessionLocal()
        db.info["rls_bypass"] = True
        row = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id, AuditLog.seq == 1).one()
        row.details = {**(row.details or {}), "tampered": True}
        db.commit()
        db.close()
        return
    owner = create_engine(DATABASE_URL)  # no SET ROLE: superuser, triggers suspended for this session
    with owner.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text("UPDATE audit_logs SET details = '{\"tampered\": true}' WHERE tenant_id = :t AND seq = 1"),
                     {"t": tenant_id})
    owner.dispose()


async def test_export_verifies_independently(tenant, tmp_path):
    ac = tenant["client"]
    bundle = (await ac.get("/api/v1/audit/export")).json()
    pem = (await ac.get("/api/v1/audit/public-key")).json()["public_key"]
    key = tmp_path / "trusted.pem"
    key.write_text(pem, encoding="ascii")
    good = tmp_path / "export.json"
    good.write_text(json.dumps(bundle), encoding="utf-8")
    assert verify_audit_export.main([str(good), "--public-key", str(key)]) == 0

    bundle["entries"][0]["action"] = "something_else"
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(bundle), encoding="utf-8")
    assert verify_audit_export.main([str(bad), "--public-key", str(key)]) == 1

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    other = tmp_path / "other.pem"
    other.write_bytes(Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    assert verify_audit_export.main([str(good), "--public-key", str(other)]) == 1


@pytest.mark.postgres
async def test_update_and_delete_fail_at_the_database_level(tenant):
    await tenant["client"].get("/api/v1/audit/verify")  # seal
    db = SessionLocal()
    try:
        bind_tenant(db, tenant["tenant_id"])
        for stmt in ("UPDATE audit_logs SET action = 'rewritten' WHERE tenant_id = :t",
                     "DELETE FROM audit_logs WHERE tenant_id = :t"):
            with pytest.raises(DBAPIError, match="append-only|permission denied"):
                db.execute(text(stmt), {"t": tenant["tenant_id"]})
                db.commit()
            db.rollback()
    finally:
        db.close()
