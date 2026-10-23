"""S3.4 tenant isolation and S3.1 RBAC.

Cross-tenant reads must return 404 (never 403: existence must not leak). On Postgres, RLS must
hide other tenants' rows even from a query that forgets the tenant filter. The permission matrix
is checked for every protected route and all four roles.
"""
import re
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DBAPIError

from app.database import SessionLocal, bind_tenant
from app.db_models import Transaction
from app.main import app
from app.permissions import MATRIX, RANK, ROLES, authorize, required_role
from tests.conftest import effective_routes

PASSWORD = "SecurePass123!"
RESOLVE_SUSPICIOUS = {"status": "resolved", "resolution": "confirmed_suspicious", "resolution_summary": "test"}


async def _register(ac: AsyncClient, company: str) -> dict:
    r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@{company}.io",
                                                  "password": PASSWORD, "first_name": "A", "last_name": "B",
                                                  "company": company})
    assert r.status_code == 201, r.text
    return r.json()


def _client(token: str | None = None) -> AsyncClient:
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if token:
        ac.headers["Authorization"] = f"Bearer {token}"
    return ac


@pytest_asyncio.fixture
async def two_tenants():
    async with _client() as anon:
        a, b = await _register(anon, "alpha"), await _register(anon, "beta")
    ca, cb = _client(a["access_token"]), _client(b["access_token"])
    tx = (await ca.post("/api/v1/transactions", json={
        "amount": 25000.0, "currency": "USD", "transaction_type": "wire", "sender_name": "Alpha Sender",
        "receiver_name": "Alpha Receiver", "idempotency_key": uuid.uuid4().hex})).json()["data"]
    case = (await ca.post("/api/v1/cases", json={"transaction_id": tx["transaction_id"], "reason": "test"})).json()
    await ca.patch(f"/api/v1/cases/{case['case_id']}", json=RESOLVE_SUSPICIOUS)
    filing = (await ca.post("/api/v1/filings", json={"case_id": case["case_id"], "filing_type": "SAR",
                                                     "narrative": "n"})).json()
    tenants = {k: (await c.get("/api/auth/me")).json()["tenant_id"] for k, c in (("a", ca), ("b", cb))}
    yield {"a": ca, "b": cb, "tx": tx["transaction_id"], "case": case["case_id"], "filing": filing["id"],
           "a_user": a["user"], "tenant_a": tenants["a"], "tenant_b": tenants["b"]}
    await ca.aclose()
    await cb.aclose()


async def test_cross_tenant_reads_are_404_not_403(two_tenants):
    t = two_tenants
    for path in (f"/api/v1/transactions/{t['tx']}", f"/api/v1/cases/{t['case']}", f"/api/v1/filings/{t['filing']}"):
        assert (await t["a"].get(path)).status_code == 200, path
        assert (await t["b"].get(path)).status_code == 404, path
    assert (await t["b"].delete(f"/api/v1/transactions/{t['tx']}")).status_code == 404
    listed = {x["id"] for x in (await t["b"].get("/api/v1/transactions")).json()}
    assert t["tx"] not in listed


async def test_settings_are_scoped_per_tenant(two_tenants):
    t = two_tenants
    assert (await t["a"].put("/api/v1/settings/rules.threshold.wire", json={"value": 1234.0})).status_code == 200
    values = lambda r: {s["key"]: s["value"] for s in r.json()}  # noqa: E731
    assert values(await t["a"].get("/api/v1/settings"))["rules.threshold.wire"] == 1234.0
    assert values(await t["b"].get("/api/v1/settings"))["rules.threshold.wire"] == 10000.0


@pytest.mark.postgres
async def test_rls_hides_rows_even_when_the_app_filter_is_forgotten(two_tenants):
    t = two_tenants
    db = SessionLocal()
    try:
        bind_tenant(db, t["tenant_b"])
        assert db.query(Transaction).filter(Transaction.id == t["tx"]).count() == 0  # no tenant filter at all
        assert all(row.tenant_id == t["tenant_b"] for row in db.query(Transaction).all())
        db.add(Transaction(tenant_id=t["tenant_a"], user_id=t["a_user"]["id"], idempotency_key=uuid.uuid4().hex,
                           amount=1.0, transaction_type="ach", sender_name="x", receiver_name="y"))
        with pytest.raises(DBAPIError, match="row-level security"):
            db.commit()  # WITH CHECK: cannot write into another tenant
    finally:
        db.rollback()
        db.close()


# ---------------- RBAC ----------------

@pytest_asyncio.fixture(scope="module")
async def role_tokens():
    async with _client() as anon:
        owner = await _register(anon, "rbac")
    tokens = {"admin": owner["access_token"]}
    async with _client(owner["access_token"]) as admin:
        for role in ("analyst", "investigator", "supervisor"):
            email = f"{role}-{uuid.uuid4().hex[:6]}@rbac.io"
            r = await admin.post("/api/v1/admin/users", json={"email": email, "password": PASSWORD,
                                                              "first_name": role, "last_name": "user", "role": role})
            assert r.status_code == 201, r.text
            login = await anon.post("/api/auth/login", json={"email": email, "password": PASSWORD}) \
                if False else None
            async with _client() as c:
                login = await c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
            tokens[role] = login.json()["access_token"]
    return tokens


def _protected_routes() -> list:
    routes = [r for r in effective_routes(app)
              if any(getattr(d, "dependency", None) is authorize for d in r.dependencies)]
    assert len(routes) >= 60  # guards against a vacuous walk
    return routes


def test_matrix_entries_all_exist():
    real = {(m, r.path) for r in _protected_routes() for m in r.methods}
    assert set(MATRIX) <= real, sorted(set(MATRIX) - real)


async def test_permission_matrix_for_every_route_and_role(role_tokens):
    failures = []
    for route in _protected_routes():
        path = re.sub(r"\{[^}]+\}", "no-such-id", route.path)
        for method in sorted(route.methods):
            need = required_role(method, route.path)
            for role in ROLES:
                async with _client(role_tokens[role]) as c:
                    r = await c.request(method, path, json={})
                denied = r.status_code == 403 and "role" in r.text
                if denied != (RANK[role] < RANK[need]) or (r.status_code >= 500 and r.status_code != 501):
                    failures.append(f"{method} {route.path} as {role}: {r.status_code} (needs {need})")
    assert failures == []


async def test_analyst_blocked_from_admin_routes_but_can_work_cases(role_tokens):
    async with _client(role_tokens["analyst"]) as c:
        for method, path in (("PUT", "/api/v1/settings/rules.threshold.wire"),
                             ("POST", "/api/v1/health/circuit-breakers/rag/reset"),
                             ("POST", "/api/v1/privacy/dsar"), ("GET", "/api/v1/admin/users")):
            assert (await c.request(method, path, json={"value": 1})).status_code == 403, path
        assert (await c.get("/api/v1/cases")).status_code == 200
        tx = (await c.post("/api/v1/transactions", json={"amount": 10.0, "currency": "USD", "transaction_type": "ach",
                                                         "sender_name": "s", "receiver_name": "r"})).json()["data"]
        case = await c.post("/api/v1/cases", json={"transaction_id": tx["transaction_id"], "reason": "analyst"})
        assert case.status_code in (200, 201)


async def test_only_supervisors_submit_filings(role_tokens):
    async with _client(role_tokens["investigator"]) as inv:
        tx = (await inv.post("/api/v1/transactions", json={"amount": 10.0, "currency": "USD", "transaction_type": "ach",
                                                           "sender_name": "s", "receiver_name": "r"})).json()["data"]
        case = (await inv.post("/api/v1/cases", json={"transaction_id": tx["transaction_id"], "reason": "x"})).json()
        await inv.patch(f"/api/v1/cases/{case['case_id']}", json=RESOLVE_SUSPICIOUS)
        filing = (await inv.post("/api/v1/filings", json={"case_id": case["case_id"], "filing_type": "SAR",
                                                          "narrative": "n"})).json()
        assert (await inv.patch(f"/api/v1/filings/{filing['id']}", json={"status": "submitted"})).status_code == 403
        assert (await inv.patch(f"/api/v1/filings/{filing['id']}", json={"narrative": "edited"})).status_code == 200
    async with _client(role_tokens["supervisor"]) as sup:
        assert (await sup.patch(f"/api/v1/filings/{filing['id']}", json={"status": "submitted"})).status_code == 200


async def test_me_reports_role_and_last_admin_is_protected(role_tokens):
    async with _client(role_tokens["admin"]) as admin:
        me = (await admin.get("/api/auth/me")).json()
        assert me["role"] == "admin"
        r = await admin.patch(f"/api/v1/admin/users/{me['id']}", json={"role": "analyst"})
        assert r.status_code == 409
        users = (await admin.get("/api/v1/admin/users")).json()
        assert {u["role"] for u in users} == set(ROLES)
