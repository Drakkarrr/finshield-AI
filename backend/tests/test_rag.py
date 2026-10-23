"""S2.4 RAG end to end. Retrieval needs pgvector, so the DB-backed tests are Postgres-only;
the status/degradation tests run everywhere."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config_service import ScreeningConfig
from app.database import DATABASE_URL, IS_SQLITE
from app.domain.models_registry.registry import BUILTIN
from app.domain.rag.embedders import HashEmbedder, load_embedder
from app.domain.rag.seed import seed_rag_data
from app.domain.rag.service import EmbeddingMismatch, RAGRetrievalService
from app.domain.screening import ScreeningContext, screen
from app.main import app
from app.models import ScreeningStatus, TransactionRequest, TransactionType

# Shares vocabulary with DOC-003 (wire transfer reporting): retrievable by any embedder.
WIRE_MEMO = "International wire transfer with no apparent business purpose, beneficiary information incomplete"
# Says the same thing as DOC-003 with none of its key terms: only a semantic embedder finds it.
WIRE_PARAPHRASE = "Sending money overseas electronically needs the full details of who pays and who receives it"


@pytest.fixture(scope="module")
def rag():
    if IS_SQLITE:
        pytest.skip("RAG retrieval needs pgvector (TEST_DATABASE_URL=postgresql://...)")
    os.environ.setdefault("RAG_EMBEDDER", "hash")
    service = RAGRetrievalService(DATABASE_URL, load_embedder())
    service.reembed()  # the corpus may have been written by another embedder in this database
    seed_rag_data(service)
    return service


@pytest.mark.postgres
def test_ranked_retrieval(rag):
    results = rag.search_similar_documents(WIRE_MEMO, top_k=3)
    assert [r["id"] for r in results][0] == "DOC-003"
    assert results[0]["score"] >= results[-1]["score"]


@pytest.mark.postgres
def test_semantic_paraphrase_retrieval(rag):
    if not rag.embedder.semantic:
        pytest.skip("hash embedder is lexical; run with RAG_EMBEDDER=minilm (backend image)")
    assert rag.search_similar_documents(WIRE_PARAPHRASE, top_k=1)[0]["id"] == "DOC-003"


@pytest.mark.postgres
def test_refuses_to_search_vectors_from_another_model(rag):
    class OtherEmbedder(HashEmbedder):
        name = "other-model"

    foreign = RAGRetrievalService(DATABASE_URL, OtherEmbedder())
    with pytest.raises(EmbeddingMismatch, match="re-embed|reembed"):
        foreign.search_similar_documents("anything")


@pytest.mark.postgres
async def test_screening_persists_rag_context_and_reasons(rag):
    previous = getattr(app.state, "rag_service", None)
    app.state.rag_service = rag
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@rag.io",
                                                          "password": "SecurePass123!", "first_name": "R",
                                                          "last_name": "Ag"})
            ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
            out = (await ac.post("/api/v1/transactions", json={
                "amount": 9500.0, "currency": "USD", "transaction_type": "ach", "sender_name": "Cash Customer",
                "receiver_name": "Branch Deposit", "description": WIRE_MEMO,
                "idempotency_key": uuid.uuid4().hex})).json()["data"]
            detail = (await ac.get(f"/api/v1/transactions/{out['transaction_id']}")).json()
    finally:
        app.state.rag_service = previous
    assert out["rag_status"] in ("ok", "lexical_fallback")
    assert detail["rag_context"]["policies"][0]["id"] == "DOC-003"
    assert any(r["source"] == "rag" and r["feature"] == "policy_match" for r in detail["reasons"])


def _tx() -> TransactionRequest:
    return TransactionRequest(amount=50.0, transaction_type=TransactionType.ACH, sender_name="Clean Sender",
                              receiver_name="Clean Receiver")


def test_disabled_rag_is_reported_and_does_not_change_the_decision(fixture_watchlist):
    out = screen(_tx(), ScreeningContext(config=ScreeningConfig.defaults(), model=BUILTIN,
                                         watchlist=fixture_watchlist, rag_status="disabled")).result
    assert out.rag_status == "disabled" and out.status == ScreeningStatus.APPROVED and not out.degraded
    assert any(r.source == "rag" and r.degraded for r in out.reasons)


def test_lexical_fallback_is_labelled_never_presented_as_semantic(fixture_watchlist):
    ctx = {"policies": [{"id": "DOC-1", "title": "AML policy", "score": 0.4}], "sanctions_matches": [],
           "similar_precedents": []}
    out = screen(_tx(), ScreeningContext(config=ScreeningConfig.defaults(), model=BUILTIN,
                                         watchlist=fixture_watchlist, rag_status="lexical_fallback",
                                         rag_context=ctx)).result
    assert out.rag_status == "lexical_fallback"
    assert any(r.feature == "embedder" and r.value == "lexical_fallback" and r.degraded for r in out.reasons)
    assert all(r.degraded for r in out.reasons if r.source == "rag")
