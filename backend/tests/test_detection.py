"""P2 acceptance tests: behavioral (S2.1), determinism + reasons (S2.2), lists (S2.3),
model versions (S2.5) and degraded routing through circuit breakers (S2.6)."""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import resilience
from app.config_service import ScreeningConfig
from app.db_models import ModelVersion, Transaction
from app.domain import behavioral
from app.domain.models_registry import V1_PARAMS, registry
from app.domain.rag.embedders import HashEmbedder
from app.domain.screening import ScreeningContext, gating, screen
from app.main import app
from app.models import RuleResult, RuleType, ScreeningStatus, TransactionRequest, TransactionType
from tests.conftest import system_session

COUNTRIES = frozenset({"KP", "IR", "SY", "CU", "RU"})


def tx(**kw) -> TransactionRequest:
    base = dict(amount=100.0, currency="USD", transaction_type=TransactionType.ACH,
                sender_name="Clean Sender", receiver_name="Clean Receiver")
    base.update(kw)
    return TransactionRequest(**base)


def ctx(watchlist, **kw) -> ScreeningContext:
    base = dict(config=ScreeningConfig.defaults(), model=registry.BUILTIN, watchlist=watchlist,
                high_risk_countries=COUNTRIES)
    base.update(kw)
    return ScreeningContext(**base)


def history(amount: float, n: int, days: int, start: datetime | None = None) -> list[behavioral.HistoryRow]:
    start = start or datetime(2026, 1, 1)
    step = timedelta(days=days / max(n - 1, 1))
    return [behavioral.HistoryRow(amount=amount + (i % 3) * 2, created_at=start + i * step,
                                  destination_country="US", receiver_name="Landlord", transaction_type="ach")
            for i in range(n)]


def _strip_volatile(result) -> dict:
    d = result.model_dump(mode="json")
    for k in ("timestamp", "total_latency_ms", "transaction_id", "idempotency_key"):
        d.pop(k)
    for r in d["rule_results"]:
        r.pop("latency_ms")
    return d


# ---------------- S2.1 behavioral ----------------

class TestBehavioral:
    def test_warm_account_20x_mean_flags_with_z_score_reason(self, fixture_watchlist):
        base = behavioral.compute_baseline(history(250.0, 40, 120))
        out = screen(tx(amount=5000.0), ctx(fixture_watchlist, baseline=base,
                                            population=behavioral.Population(200, 260.0, 40.0))).result
        z = next(r for r in out.reasons if r.source == "behavioral" and r.feature == "amount_z_score")
        assert z.cold_start is False and z.basis == "account" and z.value > 3
        assert out.behavioral_score == 1.0
        assert out.status == ScreeningStatus.FLAGGED  # behavioral trigger escalates; no rule fired

    def test_cold_start_account_same_amount_does_not_flag(self, fixture_watchlist):
        base = behavioral.compute_baseline(history(250.0, 3, 5))  # 3 txs over 5 days: cold start
        population = behavioral.Population(count=500, avg_amount=6000.0, std_dev_amount=4000.0)
        out = screen(tx(amount=5000.0), ctx(fixture_watchlist, baseline=base, population=population)).result
        trig = next(r for r in out.reasons if r.source == "behavioral" and r.feature == "trigger")
        assert trig.cold_start is True and trig.triggered is False
        assert any(r.source == "behavioral" and getattr(r, "basis", None) == "population" for r in out.reasons)
        assert out.status == ScreeningStatus.APPROVED

    def test_no_random_jitter_in_behavioral_score(self, fixture_watchlist):
        base = behavioral.compute_baseline(history(250.0, 40, 120))
        scores = {screen(tx(amount=6000.0), ctx(fixture_watchlist, baseline=base)).result.behavioral_score
                  for _ in range(20)}
        assert len(scores) == 1


# ---------------- S2.2 determinism, reasons, gate ----------------

class TestDeterminism:
    def test_same_payload_twenty_times_identical(self, fixture_watchlist):
        base = behavioral.compute_baseline(history(900.0, 30, 90))
        payload = dict(amount=60000.0, transaction_type=TransactionType.WIRE, destination_country="SY",
                       sender_name="Acme Exports", receiver_name="Northwind Shipping")
        outs = [_strip_volatile(screen(tx(idempotency_key=f"k{i}", **payload),
                                       ctx(fixture_watchlist, baseline=base, velocity_24h=3)).result)
                for i in range(20)]
        assert all(o == outs[0] for o in outs)

    def test_every_non_approved_decision_has_reasons(self, fixture_watchlist):
        for t in (tx(sender_name="darkfund"), tx(amount=20000.0, transaction_type=TransactionType.WIRE),
                  tx(destination_country="KP"), tx(sender_name="Senator XYZ")):
            out = screen(t, ctx(fixture_watchlist)).result
            assert out.status != ScreeningStatus.APPROVED
            assert [r for r in out.reasons if r.source in ("rule", "list")]
            assert any(r.source == "gate" for r in out.reasons)
            assert out.model_version == registry.BUILTIN.version


class TestPrecedenceGate:
    """Pins the rule-action precedence semantics (must never change)."""
    BANDS = ScreeningConfig.defaults().bands

    def rr(self, rule_id: str, triggered=True) -> RuleResult:
        return RuleResult(rule_id=rule_id, rule_type=RuleType.SANCTIONS, rule_name=rule_id, triggered=triggered,
                          latency_ms=0)

    def test_rule_action_overrides_score_band(self):
        assert gating.precedence_gate(0.0, True, [self.rr("RULE-001")], self.BANDS) == ScreeningStatus.BLOCKED
        assert gating.precedence_gate(0.0, True, [self.rr("RULE-004")], self.BANDS) == ScreeningStatus.BLOCKED
        assert gating.precedence_gate(0.99, True, [self.rr("RULE-002")], self.BANDS) == ScreeningStatus.FLAGGED
        assert gating.precedence_gate(0.99, True, [self.rr("RULE-003")], self.BANDS) == ScreeningStatus.IN_REVIEW

    def test_block_beats_flag_beats_review(self):
        rules = [self.rr("RULE-003"), self.rr("RULE-002"), self.rr("RULE-001")]
        assert gating.precedence_gate(0.1, True, rules, self.BANDS) == ScreeningStatus.BLOCKED
        assert gating.precedence_gate(0.1, True, rules[:2], self.BANDS) == ScreeningStatus.FLAGGED

    def test_score_bands_only_when_no_rule_fired(self):
        quiet = [self.rr("RULE-001", triggered=False)]
        assert gating.precedence_gate(0.85, False, quiet, self.BANDS) == ScreeningStatus.BLOCKED
        assert gating.precedence_gate(0.55, False, quiet, self.BANDS) == ScreeningStatus.FLAGGED
        assert gating.precedence_gate(0.35, False, quiet, self.BANDS) == ScreeningStatus.IN_REVIEW
        assert gating.precedence_gate(0.10, False, quiet, self.BANDS) == ScreeningStatus.APPROVED

    def test_overlays_only_escalate(self):
        status, _ = gating.decide(0.0, [self.rr("RULE-001")], self.BANDS, behavioral_triggered=False,
                                  rag_sanctions_match=False, degraded_dependencies=["rag"])
        assert status == ScreeningStatus.BLOCKED  # degraded never lowers a block to review


# ---------------- S2.3 lists ----------------

class TestLists:
    def test_alias_hit_names_entry_version_and_score(self, fixture_watchlist):
        out = screen(tx(receiver_name="Volkoff, Andrei"), ctx(fixture_watchlist)).result
        hit = next(r for r in out.reasons if r.feature == "sanctions_match")
        assert hit.entry_id == "FIXTURE-OFAC:900005"
        assert hit.list_version == fixture_watchlist.versions["FIXTURE-OFAC"]
        assert hit.match_type == "fuzzy" and hit.score >= 0.88
        assert out.status == ScreeningStatus.BLOCKED

    def test_exact_alias_match(self, fixture_watchlist):
        out = screen(tx(sender_name="Global Remit Services Ltd."), ctx(fixture_watchlist)).result
        hit = next(r for r in out.reasons if r.feature == "sanctions_match")
        assert (hit.entry_id, hit.match_type, hit.score) == ("FIXTURE-OFAC:900001", "exact", 1.0)

    def test_unrelated_name_does_not_hit(self, fixture_watchlist):
        for name in ("Acme Corporation", "Trading", "Northern Lights Bakery"):
            out = screen(tx(sender_name=name), ctx(fixture_watchlist)).result
            assert not any(r.feature == "sanctions_match" for r in out.reasons), name

    @pytest.mark.parametrize("name", ["globalremit", "darkfund", "terrorfin"])
    def test_legacy_names_still_hit_via_fixture(self, fixture_watchlist, name):
        assert screen(tx(sender_name=name), ctx(fixture_watchlist)).result.status == ScreeningStatus.BLOCKED

    def test_missing_list_is_degraded_never_approved(self):
        out = screen(tx(), ctx(None)).result
        assert out.degraded and "sanctions_list" in out.degraded_dependencies
        assert out.status == ScreeningStatus.IN_REVIEW


# ---------------- API-level: S2.2 / S2.5 / S2.6 ----------------

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/auth/register", json={
            "email": f"{uuid.uuid4().hex[:8]}@detect.io", "password": "SecurePass123!",
            "first_name": "De", "last_name": "Tect"})
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield ac


FULL_ML = {"amount": 15000.0, "currency": "USD", "transaction_type": "wire", "sender_name": "Meridian Holdings",
           "receiver_name": "Pacific Freight", "destination_country": "US", "account_id": "ACC-1"}


async def test_api_decisions_are_persisted_and_reproducible(client):
    other = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    r = await other.post("/api/auth/register", json={
        "email": f"{uuid.uuid4().hex[:8]}@detect.io", "password": "SecurePass123!", "first_name": "A", "last_name": "B"})
    other.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    a = (await client.post("/api/v1/transactions", json={**FULL_ML, "idempotency_key": uuid.uuid4().hex})).json()["data"]
    b = (await other.post("/api/v1/transactions", json={**FULL_ML, "idempotency_key": uuid.uuid4().hex})).json()["data"]
    await other.aclose()
    for d in (a, b):
        for k in ("timestamp", "total_latency_ms", "transaction_id", "idempotency_key"):
            d.pop(k)
        for rr in d["rule_results"]:
            rr.pop("latency_ms")
    assert a == b  # two accounts in identical state -> identical decision
    detail = (await client.get(f"/api/v1/transactions/{(await client.get('/api/v1/transactions')).json()[0]['id']}")).json()
    assert detail["model_version"] and detail["reasons"] and detail["decision"]["status"] == detail["status"]


async def test_replay_returns_the_stored_decision(client):
    body = {**FULL_ML, "idempotency_key": uuid.uuid4().hex}
    first = (await client.post("/api/v1/transactions", json=body)).json()["data"]
    second = (await client.post("/api/v1/transactions", json=body)).json()["data"]
    assert first == second


async def test_shadow_scored_and_stored_but_never_decides_then_promotion_does(client):
    db = system_session()
    try:
        active_before = db.query(ModelVersion).filter(ModelVersion.status == "active").count()
    finally:
        db.close()
    aggressive = {**V1_PARAMS, "bias": 4.0}
    reg = await client.post("/api/v1/models", json={"name": "test-aggressive", "params": aggressive,
                                                     "model_card": {"intended_use": "test"}})
    assert reg.status_code == 201 and reg.json()["status"] == "shadow"
    try:
        out = (await client.post("/api/v1/transactions", json={**FULL_ML, "idempotency_key": uuid.uuid4().hex})).json()["data"]
        db = system_session()
        try:
            row = db.get(Transaction, out["transaction_id"])
            assert row.shadow_result["model_version"] == reg.json()["label"]
            assert row.shadow_result["score"] > out["ml_confidence"]  # shadow scored, but...
            assert row.model_version == out["model_version"] != reg.json()["label"]  # ...did not decide
        finally:
            db.close()

        promoted = await client.post(f"/api/v1/models/{reg.json()['id']}/promote")
        assert promoted.status_code == 200 and promoted.json()["status"] == "active"
        after = (await client.post("/api/v1/transactions", json={**FULL_ML, "idempotency_key": uuid.uuid4().hex})).json()["data"]
        assert after["model_version"] == reg.json()["label"]
        assert after["ml_confidence"] > out["ml_confidence"]
        db = system_session()
        try:
            assert db.query(ModelVersion).filter(ModelVersion.status == "active").count() == max(active_before, 1)
        finally:
            db.close()
    finally:
        db = system_session()
        try:
            for row in db.query(ModelVersion).filter(ModelVersion.name == "test-aggressive").all():
                db.delete(row)
            db.commit()
        finally:
            db.close()
        registry.invalidate()


async def test_dead_rag_routes_to_review_opens_breaker_then_recovers(client):
    class DeadRag:
        embedder = HashEmbedder()

        def multi_hop_retrieval(self, _):
            raise ConnectionError("rag postgres down")

    class LiveRag:
        embedder = HashEmbedder()

        def multi_hop_retrieval(self, _):
            return {"policies": [], "sanctions_matches": [], "similar_precedents": []}

    resilience.forget()
    previous = getattr(app.state, "rag_service", None)
    app.state.rag_service = DeadRag()
    clean = {"amount": 40.0, "currency": "USD", "transaction_type": "ach", "sender_name": "Clean Sender",
             "receiver_name": "Clean Receiver"}
    try:
        for _ in range(resilience.DEFAULTS["failure_threshold"]):
            r = await client.post("/api/v1/transactions", json={**clean, "idempotency_key": uuid.uuid4().hex})
            assert r.status_code == 200
            d = r.json()["data"]
            assert d["status"] == "in_review" and d["degraded"] and "rag" in d["degraded_dependencies"]
        breakers = {b["dependency"]: b["state"] for b in
                    (await client.get("/api/v1/health/circuit-breakers")).json()["breakers"]}
        assert breakers["rag"] == "open"
        assert (await client.get("/api/health")).status_code == 503

        app.state.rag_service = LiveRag()
        st = resilience._get("rag")
        st.changed_at -= timedelta(seconds=st.cooldown_seconds + 1)  # cooldown elapsed
        r = (await client.post("/api/v1/transactions", json={**clean, "idempotency_key": uuid.uuid4().hex})).json()["data"]
        assert r["status"] == "approved" and not r["degraded"] and r["rag_status"] == "lexical_fallback"
        assert resilience.states()["rag"]["state"] == "closed"
    finally:
        app.state.rag_service = previous
        resilience.reset("rag")
        resilience.forget()
