"""S1.3: handlers must not block the event loop.

Handlers are plain `def` (FastAPI runs them in a threadpool). To make the check independent of
disk speed, the engine call gets a fixed simulated I/O latency: if any handler or dependency on the
screening path blocked the event loop, 50 concurrent requests would take as long as 50 serial ones.
"""
import asyncio
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.main import app

N = 50
LATENCY_S = 0.05


def _payload() -> dict:
    return {
        "amount": 120.0,
        "currency": "USD",
        "transaction_type": "ach",
        "sender_name": "Concurrency Sender",
        "receiver_name": "Concurrency Receiver",
        "idempotency_key": f"conc-{uuid.uuid4().hex}",
    }


@pytest.mark.asyncio
async def test_concurrent_screening_is_not_serialised(monkeypatch):
    real_screen = main_module.engine.screen

    def slow_screen(*args, **kwargs):
        time.sleep(LATENCY_S)  # stands in for blocking I/O (DB, list lookups)
        return real_screen(*args, **kwargs)

    monkeypatch.setattr(main_module.engine, "screen", slow_screen)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60) as ac:
        r = await ac.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex[:8]}@conc.io", "password": "SecurePass123!",
            "first_name": "Con", "last_name": "Current",
        })
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

        t0 = time.perf_counter()
        for _ in range(5):
            assert (await ac.post("/api/v1/transactions", json=_payload())).status_code == 200
        serial_per_request = (time.perf_counter() - t0) / 5

        t0 = time.perf_counter()
        responses = await asyncio.gather(*(ac.post("/api/v1/transactions", json=_payload()) for _ in range(N)))
        concurrent = time.perf_counter() - t0

    assert all(r.status_code == 200 for r in responses), [r.text for r in responses if r.status_code != 200][:3]
    serial_estimate = serial_per_request * N
    print(f"\nserial estimate for {N}: {serial_estimate:.2f}s | concurrent: {concurrent:.2f}s "
          f"| speed-up x{serial_estimate / concurrent:.1f}")
    # A blocked event loop gives ~1x (the old async-def handlers did not finish at all under this
    # load); sync handlers measure x3-4 on SQLite, whose writes serialise, and more on Postgres.
    assert concurrent < serial_estimate / 2
