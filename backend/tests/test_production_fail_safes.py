"""S7.5: production fail-safes. No simulated payments or fictional PEP data in production by
accident, and a stale sanctions list holds decisions for human review."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app import screening_service
from app.main import app, check_payments_config
from scripts.bootstrap import _flag

SANCTIONED = "DARKFUND"  # fictional entry in tests/fixtures/lists/sdn.csv


def _client(token: str | None = None) -> AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


async def _token() -> str:
    async with _client() as anon:
        r = await anon.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@s75.io",
                                                        "password": "SecurePass123!", "first_name": "S",
                                                        "last_name": "Five", "company": "s75"})
        assert r.status_code == 201, r.text
        return r.json()["access_token"]


async def _screen(token: str, receiver: str = "Ordinary Receiver") -> dict:
    async with _client(token) as c:
        r = await c.post("/api/v1/transactions", json={
            "amount": 120.0, "currency": "USD", "transaction_type": "ach", "sender_name": "Ordinary Sender",
            "receiver_name": receiver, "idempotency_key": uuid.uuid4().hex})
        assert r.status_code == 200, r.text
        return r.json()["data"]


# --- startup: payments ------------------------------------------------------------------------

@pytest.mark.parametrize("env, mode, allow, refuses", [
    ({"APP_ENV": "production"}, "simulated", None, True),
    ({}, "simulated", None, True),  # APP_ENV unset means production
    ({"APP_ENV": "production"}, "simulated", "true", False),
    ({"APP_ENV": "production"}, "stripe", None, False),
    ({"APP_ENV": "development"}, "simulated", None, False),
])
def test_production_refuses_simulated_payments_unless_explicitly_allowed(monkeypatch, env, mode, allow, refuses):
    monkeypatch.delenv("APP_ENV", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PAYMENTS_MODE", mode)
    if allow is None:
        monkeypatch.delenv("ALLOW_SIMULATED_PAYMENTS", raising=False)
    else:
        monkeypatch.setenv("ALLOW_SIMULATED_PAYMENTS", allow)
    if refuses:
        with pytest.raises(RuntimeError, match="PAYMENTS_MODE=simulated"):
            check_payments_config()
    else:
        check_payments_config()


# --- bootstrap: fictional PEP fixtures --------------------------------------------------------

@pytest.mark.parametrize("app_env, explicit, expected", [
    ("production", None, False),
    (None, None, False),  # unset means production
    ("development", None, True),
    ("production", "true", True),  # an explicit value always wins
    ("development", "false", False),
])
def test_demo_fixtures_are_off_outside_development_by_default(monkeypatch, app_env, explicit, expected):
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)
    if explicit is None:
        monkeypatch.delenv("LISTS_DEMO_FIXTURES", raising=False)
    else:
        monkeypatch.setenv("LISTS_DEMO_FIXTURES", explicit)
    assert _flag("LISTS_DEMO_FIXTURES") is expected


# --- screening: list freshness ----------------------------------------------------------------
# The freshness lookup is replaced per test so the shared list data of the suite stays untouched.

def _freshness(monkeypatch, sources: list[dict]) -> None:
    monkeypatch.setattr(screening_service.lists, "status", lambda db, max_age, now=None: sources)


async def test_stale_sanctions_list_holds_the_decision_for_review(monkeypatch):
    token = await _token()
    _freshness(monkeypatch, [{"list_type": "sanctions", "stale": True}, {"list_type": "pep", "stale": False}])
    d = await _screen(token)
    assert d["status"] == "in_review" and d["degraded"] is True
    assert "list_stale" in d["degraded_dependencies"]
    assert any(r["source"] == "resilience" and "list_stale" in (r.get("value") or []) for r in d["reasons"])


async def test_one_fresh_sanctions_source_is_enough(monkeypatch):
    token = await _token()
    _freshness(monkeypatch, [{"list_type": "sanctions", "stale": True}, {"list_type": "sanctions", "stale": False}])
    d = await _screen(token)
    assert "list_stale" not in d["degraded_dependencies"]


async def test_fresh_lists_do_not_degrade_and_sanctions_still_block():
    token = await _token()
    clean = await _screen(token)
    assert clean["degraded"] is False and "list_stale" not in clean["degraded_dependencies"]
    hit = await _screen(token, receiver=SANCTIONED)
    assert hit["status"] == "blocked"


async def test_freshness_check_failure_fails_safe(monkeypatch):
    token = await _token()

    def broken(db, max_age, now=None):
        raise RuntimeError("list store unavailable")

    monkeypatch.setattr(screening_service.lists, "status", broken)
    d = await _screen(token)
    assert d["status"] == "in_review" and "list_stale" in d["degraded_dependencies"]
