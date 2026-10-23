"""API keys: digest lookup (no bcrypt per request), legacy bcrypt-only keys upgrade, revocation."""
import uuid

from httpx import ASGITransport, AsyncClient

from app import auth
from app.database import SessionLocal
from app.db_models import ApiKey
from app.main import app


def _client(token: str | None = None) -> AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


async def _owner_and_key() -> tuple[str, str, str]:
    async with _client() as anon:
        r = await anon.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@keys.io",
                                                        "password": "SecurePass123!", "first_name": "K",
                                                        "last_name": "Y", "company": "keys"})
        token = r.json()["access_token"]
    async with _client(token) as c:
        created = (await c.post("/api/v1/keys", json={"name": "k"})).json()
    return token, created["id"], created["key"]


async def test_requests_authenticate_by_digest_without_bcrypt(monkeypatch):
    _, _, key = await _owner_and_key()

    def no_bcrypt(*_a, **_k):
        raise AssertionError("bcrypt must not run on the per-request path")

    monkeypatch.setattr(auth, "verify_password", no_bcrypt)
    async with _client(key) as c:
        assert (await c.get("/api/v1/transactions")).status_code == 200


async def test_legacy_key_without_digest_still_works_and_is_upgraded():
    _, key_id, key = await _owner_and_key()
    with SessionLocal() as db:
        db.info["rls_bypass"] = True
        db.get(ApiKey, key_id).key_digest = None  # as created before migration 0011
        db.commit()
    async with _client(key) as c:
        assert (await c.get("/api/v1/transactions")).status_code == 200
    with SessionLocal() as db:
        db.info["rls_bypass"] = True
        assert db.get(ApiKey, key_id).key_digest == auth.api_key_digest(key)


async def test_revoked_key_is_rejected():
    token, key_id, key = await _owner_and_key()
    async with _client(key) as c:
        assert (await c.get("/api/v1/transactions")).status_code == 200
    async with _client(token) as owner:
        assert (await owner.delete(f"/api/v1/keys/{key_id}")).status_code == 200
    async with _client(key) as c:
        assert (await c.get("/api/v1/transactions")).status_code == 401
    async with _client("fsk_live_" + "x" * 43) as c:  # unknown key
        assert (await c.get("/api/v1/transactions")).status_code == 401
