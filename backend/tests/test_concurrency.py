"""S1.3: handlers must not block the event loop.

Handlers are plain `def`, so FastAPI runs them in a threadpool. The check is differential, so it is
independent of how much CPU/DB work a screening does (that part serialises on the GIL and on
SQLite's write lock regardless): N concurrent screenings are timed with no injected latency and
again with LATENCY_S of injected blocking I/O inside the pipeline call. If handlers overlap, the
extra wall time is about one latency period; if anything blocked the event loop it would be
N * LATENCY_S.
"""
import asyncio
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app import screening_service
from app.main import app

N = 50
LATENCY_S = 0.1


def _payload() -> dict:
    return {
        "amount": 120.0,
        "currency": "USD",
        "transaction_type": "ach",
        "sender_name": "Concurrency Sender",
        "receiver_name": "Concurrency Receiver",
        "idempotency_key": f"conc-{uuid.uuid4().hex}",
    }


async def _burst(ac: AsyncClient) -> float:
    t0 = time.perf_counter()
    responses = await asyncio.gather(*(ac.post("/api/v1/transactions", json=_payload()) for _ in range(N)))
    elapsed = time.perf_counter() - t0
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses if r.status_code != 200][:3]
    return elapsed


@pytest.mark.asyncio
async def test_concurrent_screening_is_not_serialised(monkeypatch):
    real_screen = screening_service.screen
    latency = {"s": 0.0}

    def slow_screen(*args, **kwargs):
        time.sleep(latency["s"])  # stands in for blocking I/O (DB, list lookups, RAG)
        return real_screen(*args, **kwargs)

    monkeypatch.setattr(screening_service, "screen", slow_screen)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120) as ac:
        r = await ac.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex[:8]}@conc.io", "password": "SecurePass123!",
            "first_name": "Con", "last_name": "Current",
        })
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

        await _burst(ac)  # warm-up: caches, breaker rows, first-use imports
        no_latency = await _burst(ac)
        latency["s"] = LATENCY_S
        with_latency = await _burst(ac)

    extra = with_latency - no_latency
    blocked = N * LATENCY_S
    print(f"\n{N} concurrent: {no_latency:.2f}s without injected I/O, {with_latency:.2f}s with "
          f"{LATENCY_S * 1000:.0f} ms each -> extra {extra:.2f}s (a blocked loop would add ~{blocked:.1f}s)")
    assert extra < blocked / 3
