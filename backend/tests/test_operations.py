"""P4: worker + dead-letter (S4.1), webhooks (S4.2), scheduled jobs (S4.3), observability (S4.4).

Celery runs eagerly under APP_ENV=test, so tasks execute inline; subscriber endpoints are an httpx
MockTransport. Everything else is the real code path.
"""
import json
import uuid
from datetime import datetime, timedelta

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import metrics, observability
from app.db_models import AuditLog, Case, Filing, JobRun, Notification, Tenant, WebhookEvent
from app.domain import webhooks
from app.main import app
from app.worker import tasks
from tests.conftest import system_session

RESOLVE = {"status": "resolved", "resolution": "confirmed_suspicious", "resolution_summary": "done"}


class Subscriber:
    """Records deliveries; answers with `status`."""

    def __init__(self, status: int = 200):
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status)

    def events(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


@pytest_asyncio.fixture
async def org():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@ops.io",
                                                      "password": "SecurePass123!", "first_name": "O", "last_name": "Ps"})
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        for key, value in (("webhooks.allow_http", True), ("webhooks.allow_private_targets", True),
                           ("webhooks.backoff_base_seconds", 1), ("webhooks.max_attempts", 3)):
            assert (await ac.put(f"/api/v1/settings/{key}", json={"value": value})).status_code == 200
        ac.tenant_id = (await ac.get("/api/auth/me")).json()["tenant_id"]
        yield ac
    webhooks.http_transport = None


async def _subscribe(ac, subscriber: Subscriber, events=("*",)) -> str:
    webhooks.http_transport = httpx.MockTransport(subscriber)
    r = await ac.post("/api/v1/webhooks/subscriptions", json={"url": "http://subscriber.test/hook", "events": list(events)})
    assert r.status_code == 201, r.text
    return r.json()["secret"]


async def _flagged_tx(ac) -> str:
    out = await ac.post("/api/v1/transactions", json={"amount": 100.0, "currency": "USD", "transaction_type": "ach",
                                                      "sender_name": "Senator XYZ", "receiver_name": "Printer Co",
                                                      "idempotency_key": uuid.uuid4().hex})
    data = out.json()["data"]
    assert data["status"] == "flagged"
    return data["transaction_id"]


# ---------------- S4.1 ----------------

def test_failing_task_retries_then_dead_letters():
    result = tasks.selftest.apply(kwargs={"fail": True})
    db = system_session()
    try:
        run = db.get(JobRun, result.id)
        assert run.status == "dead_letter" and run.attempts == tasks.LedgerTask.max_retries + 1
        assert "selftest failure requested" in run.last_error
        ok = tasks.selftest.apply()
        assert db.get(JobRun, ok.id).status == "succeeded"
    finally:
        db.close()


# ---------------- S4.2 ----------------

async def test_healthy_subscriber_gets_a_payload_whose_hmac_verifies(org):
    sub = Subscriber(200)
    secret = await _subscribe(org, sub, events=["transaction.flagged"])
    tx = await _flagged_tx(org)
    assert len(sub.requests) == 1
    req = sub.requests[0]
    assert webhooks.verify_signature(secret, req.headers["X-FinShield-Signature"], req.content)
    assert not webhooks.verify_signature("whsec_wrong", req.headers["X-FinShield-Signature"], req.content)
    body = json.loads(req.content)
    assert body["type"] == "transaction.flagged" and body["data"]["transaction_id"] == tx
    assert "Senator" not in req.content.decode()  # ids and decisions only
    log = (await org.get("/api/v1/webhooks", params={"event_type": "transaction.flagged"})).json()["items"]
    assert log[0]["status"] == "delivered" and log[0]["response_code"] == 200


async def test_failing_subscriber_is_retried_with_backoff_then_dead_lettered_and_replayable(org):
    sub = Subscriber(500)
    await _subscribe(org, sub, events=["transaction.flagged"])
    await _flagged_tx(org)
    item = (await org.get("/api/v1/webhooks", params={"status": "dead_letter"})).json()["items"][0]
    assert item["attempts"] == 3 and len(sub.requests) == 3
    delays = [a["retry_in_s"] for a in item["attempt_log"] if a.get("result") == "retry"]
    assert len(delays) == 2 and 1 <= delays[0] < 2 <= delays[1] < 3  # base 1s, doubling, + jitter < base
    sub.status = 200
    replay = await org.post(f"/api/v1/webhooks/{item['id']}/retry")
    assert replay.status_code == 200 and replay.json()["status"] == "delivered"


async def test_case_resolution_emits_an_event(org):
    sub = Subscriber(200)
    await _subscribe(org, sub, events=["case.created", "case.resolved"])
    tx = await _flagged_tx(org)
    case = (await org.post("/api/v1/cases", json={"transaction_id": tx, "reason": "pep"})).json()
    await org.patch(f"/api/v1/cases/{case['case_id']}", json=RESOLVE)
    assert [e["type"] for e in sub.events()] == ["case.created", "case.resolved"]


async def test_ssrf_guard_rejects_private_targets_by_default():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@ssrf.io",
                                                      "password": "SecurePass123!", "first_name": "S", "last_name": "F"})
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        for url in ("http://example.com/hook", "https://127.0.0.1/hook", "https://169.254.169.254/latest"):
            assert (await ac.post("/api/v1/webhooks/subscriptions", json={"url": url})).status_code == 422, url


# ---------------- S4.3 ----------------

async def test_sla_sweep_escalates_and_notifies_without_a_client_request(org):
    sub = Subscriber(200)
    await _subscribe(org, sub, events=["sla.breached"])
    tx = await _flagged_tx(org)
    case_id = (await org.post("/api/v1/cases", json={"transaction_id": tx, "reason": "x"})).json()["case_id"]
    db = system_session()
    try:
        db.get(Case, case_id).sla_deadline = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert tasks.sla_sweep()["escalated"] >= 1
    db = system_session()
    try:
        assert db.get(Case, case_id).status == "escalated"
        assert db.query(Notification).filter(Notification.type == "sla_breached",
                                             Notification.message.contains(case_id)).count() == 1
        assert db.query(AuditLog).filter(AuditLog.action == "case_escalated", AuditLog.resource_id == case_id).count() == 1
    finally:
        db.close()
    assert sub.events()[0]["data"]["case_id"] == case_id
    tasks.sla_sweep()  # idempotent: nothing more happens
    db = system_session()
    try:
        assert db.query(Notification).filter(Notification.type == "sla_breached",
                                             Notification.message.contains(case_id)).count() == 1
    finally:
        db.close()


async def test_filing_near_its_deadline_gets_one_reminder(org):
    tx = await _flagged_tx(org)
    case_id = (await org.post("/api/v1/cases", json={"transaction_id": tx, "reason": "x"})).json()["case_id"]
    await org.patch(f"/api/v1/cases/{case_id}", json=RESOLVE)
    filing = (await org.post("/api/v1/filings", json={"case_id": case_id, "filing_type": "SAR", "narrative": "n"})).json()
    db = system_session()
    try:
        db.get(Filing, filing["id"]).deadline = datetime.utcnow() + timedelta(days=2)
        db.commit()
    finally:
        db.close()
    tasks.filing_deadline_reminders()
    tasks.filing_deadline_reminders()  # same day: no duplicate
    db = system_session()
    try:
        assert db.query(Notification).filter(Notification.type == "filing_deadline",
                                             Notification.link.contains(filing["id"])).count() == 1
    finally:
        db.close()


async def test_audit_verifier_task_reports_chain_status(org):
    result = tasks.verify_audit()
    assert org.tenant_id not in {b["tenant_id"] for b in result["broken"]}


def test_outbox_sweep_picks_up_events_the_broker_missed():
    db = system_session()
    try:
        if db.get(Tenant, "system") is None:
            db.add(Tenant(id="system", name="system"))
            db.flush()
        ev = WebhookEvent(tenant_id="system", event_type="sla.breached", payload={}, status="pending", attempts=0,
                          created_at=datetime.utcnow() - timedelta(minutes=5))
        db.add(ev)
        db.commit()
        event_id = ev.id
    finally:
        db.close()
    assert tasks.webhook_outbox_sweep()["pending"] >= 1
    db = system_session()
    try:  # no subscription: permanently undeliverable -> dead letter, not an endless retry
        assert db.get(WebhookEvent, event_id).status == "dead_letter"
    finally:
        db.close()


# ---------------- S4.4 ----------------

async def test_one_screening_is_one_trace_with_a_span_per_stage(org):
    exporter = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
    r = await org.post("/api/v1/transactions", json={"amount": 25000.0, "currency": "USD", "transaction_type": "wire",
                                                     "sender_name": "Trace Sender", "receiver_name": "Trace Receiver",
                                                     "idempotency_key": uuid.uuid4().hex})
    request_id = r.headers["X-Request-ID"]
    spans = [s for s in exporter.get_finished_spans()]
    root = next(s for s in spans if s.name == "POST /api/v1/transactions"
                and s.attributes.get("http.request_id") == request_id)
    mine = [s for s in spans if s.context.trace_id == root.context.trace_id]
    names = {s.name for s in mine}
    assert {"screening.rules", "screening.behavioral", "screening.rag", "screening.model", "screening.scoring",
            "screening.gate", "screening.lists.snapshot"} <= names
    gate = next(s for s in mine if s.name == "screening.gate")
    assert gate.attributes["decision"] == r.json()["data"]["status"]


async def test_metrics_endpoint_requires_its_token(org, monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        assert (await anon.get("/metrics")).status_code == 404
        monkeypatch.setenv("METRICS_TOKEN", "scrape-token-for-tests")
        assert (await anon.get("/metrics")).status_code == 404
        r = await anon.get("/metrics", headers={"Authorization": "Bearer scrape-token-for-tests"})
    assert r.status_code == 200
    assert "pipeline_transactions_total" in r.text and "http_request_duration_seconds" in r.text
    assert 'circuit_breaker_state{dependency=' in r.text


async def test_forced_error_reaches_the_error_tracker(org, monkeypatch):
    from app import screening_service

    captured = []
    monkeypatch.setattr(observability, "capture_exception", lambda exc: captured.append(exc))

    def boom(*a, **kw):
        raise RuntimeError("forced failure for the error tracker")

    monkeypatch.setattr(screening_service, "run", boom)
    before = metrics.PIPELINE_ERRORS._value.get()
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
                           headers={"Authorization": org.headers["Authorization"]}) as ac:
        r = await ac.post("/api/v1/transactions", json={"amount": 1.0, "currency": "USD", "transaction_type": "ach",
                                                        "sender_name": "a", "receiver_name": "b"})
    assert r.status_code == 500 and "forced failure" not in r.text
    assert captured and isinstance(captured[0], RuntimeError)
    assert metrics.PIPELINE_ERRORS._value.get() == before + 1
