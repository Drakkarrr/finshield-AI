"""Browser session via httpOnly cookie (ruling D11) and list paging headers."""
import uuid

from httpx import ASGITransport, AsyncClient

from app.auth import SESSION_COOKIE
from app.main import app

PASSWORD = "SecurePass123!"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://test")  # the cookie is Secure


async def _register(ac: AsyncClient) -> dict:
    r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@cookie.io", "password": PASSWORD,
                                                  "first_name": "C", "last_name": "K", "company": "cookie"})
    assert r.status_code == 201, r.text
    return r.json()


async def test_login_sets_an_httponly_session_cookie_that_authenticates():
    async with _client() as ac:
        email = (await _register(ac))["user"]["email"]
        ac.cookies.clear()
        r = await ac.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200 and ac.cookies.get(SESSION_COOKIE)
        r = await ac.get("/api/auth/me")  # no Authorization header: the cookie alone authenticates
        assert r.status_code == 200 and r.json()["email"] == email


async def test_cookie_attributes():
    async with _client() as ac:
        r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@cookie.io", "password": PASSWORD,
                                                      "first_name": "C", "last_name": "K", "company": "cookie"})
        set_cookie = r.headers["set-cookie"].lower()
        assert set_cookie.startswith(f"{SESSION_COOKIE}=")
        assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/" in set_cookie


async def test_cookie_authenticated_writes_need_the_csrf_header():
    async with _client() as ac:
        await _register(ac)
        body = {"name": "csrf probe"}
        r = await ac.post("/api/v1/keys", json=body)
        assert r.status_code == 403 and "CSRF" in r.json()["detail"]
        r = await ac.post("/api/v1/keys", json=body, headers={"X-Requested-With": "XMLHttpRequest"})
        assert r.status_code in (200, 201), r.text


async def test_bearer_clients_need_no_csrf_header():
    async with _client() as ac:
        token = (await _register(ac))["access_token"]
    async with _client() as api:  # no cookie jar contents: a programmatic client
        r = await api.post("/api/v1/keys", json={"name": "bearer"},
                           headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (200, 201), r.text


async def test_logout_clears_the_session():
    async with _client() as ac:
        await _register(ac)
        r = await ac.post("/api/auth/logout")
        assert r.status_code == 204
        assert ac.cookies.get(SESSION_COOKIE) is None
        assert (await ac.get("/api/auth/me")).status_code == 401


async def test_transaction_list_reports_the_total_for_paging():
    async with _client() as ac:
        await _register(ac)
        hdr = {"X-Requested-With": "XMLHttpRequest"}
        for i in range(3):
            r = await ac.post("/api/v1/transactions", headers=hdr,
                              json={"amount": 100.0 + i, "currency": "USD", "transaction_type": "ach",
                                    "sender_name": "Page Sender", "receiver_name": "Page Receiver",
                                    "idempotency_key": uuid.uuid4().hex})
            assert r.status_code == 200, r.text
        r = await ac.get("/api/v1/transactions", params={"limit": 2, "offset": 0})
        assert r.headers["x-total-count"] == "3" and len(r.json()) == 2
        assert (await ac.get("/api/v1/transactions", params={"limit": 501})).status_code == 422
