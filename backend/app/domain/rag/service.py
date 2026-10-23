"""RAG retrieval over compliance policies, a sanctions corpus and precedent decisions (pgvector).

Every row stores the `embedding_model` that produced its vector. Searches refuse to compare
against rows embedded by a different model (EmbeddingMismatch) instead of returning meaningless
similarities; `reembed()` rebuilds the vectors with the current embedder.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Optional

import numpy as np
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.db_models import ComplianceDocument, PrecedentDecision, SanctionsEntry
from app.domain.rag.embedders import Embedder

EMBED_CACHE_SIZE = 4096  # distinct texts kept per process

logger = logging.getLogger("finshield.rag")

CORPORA = (ComplianceDocument, SanctionsEntry, PrecedentDecision)


class EmbeddingMismatch(RuntimeError):
    """Stored vectors were produced by another embedding model; re-embed before searching."""


def _cosine(a: Any, b: Any) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / denom) if denom else 0.0


def _text(row: Any) -> str:
    if isinstance(row, ComplianceDocument):
        return f"{row.title} {row.content}"
    if isinstance(row, SanctionsEntry):
        return f"{row.name} {' '.join(row.aliases or [])} {row.program or ''}"
    return f"{row.case_summary} {row.reasoning or ''}"


class RAGRetrievalService:
    def __init__(self, database_url: str, embedder: Embedder):
        # Tables and the vector extension are created by Alembic, not here.
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.embedder = embedder
        self._vectors: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_lock = threading.Lock()

    def _db(self) -> Session:
        return self.SessionLocal()

    def _embed(self, text: str) -> list[float]:
        """One text per encode, so a text always maps to the same vector; recurring texts
        (counterparty names, transaction types) are served from a bounded cache."""
        with self._cache_lock:
            hit = self._vectors.get(text)
            if hit is not None:
                self._vectors.move_to_end(text)
                return hit
        vector = self.embedder.embed([text])[0]
        with self._cache_lock:
            self._vectors[text] = vector
            if len(self._vectors) > EMBED_CACHE_SIZE:
                self._vectors.popitem(last=False)
        return vector

    def _check_model(self, db: Session, model: Any) -> None:
        stored = {m for (m,) in db.query(model.embedding_model).distinct().all()}
        foreign = stored - {self.embedder.name}
        if foreign:
            raise EmbeddingMismatch(
                f"{model.__tablename__} holds vectors from {sorted(m or 'unknown' for m in foreign)} but the active "
                f"embedder is {self.embedder.name}; run `python -m scripts.bootstrap --reembed`")

    def model_status(self) -> dict[str, list[str]]:
        db = self._db()
        try:
            return {m.__tablename__: sorted(x or "unknown" for (x,) in db.query(m.embedding_model).distinct().all())
                    for m in CORPORA}
        finally:
            db.close()

    def counts(self) -> dict[str, int]:
        db = self._db()
        try:
            return {m.__tablename__: db.query(func.count()).select_from(m).scalar() or 0 for m in CORPORA}
        finally:
            db.close()

    # --- writes -------------------------------------------------------------------------------
    def _add(self, row: Any) -> str:
        row.embedding = self._embed(_text(row))
        row.embedding_model = self.embedder.name
        db = self._db()
        try:
            db.merge(row)
            db.commit()
            return row.id
        finally:
            db.close()

    def add_compliance_document(self, doc_id: str, title: str, content: str, category: str,
                                jurisdiction: Optional[str] = None, effective_date: Optional[datetime] = None,
                                metadata: Optional[dict] = None) -> str:
        return self._add(ComplianceDocument(id=doc_id, title=title, content=content, category=category,
                                            jurisdiction=jurisdiction, effective_date=effective_date,
                                            doc_metadata=metadata))

    def add_sanctions_entry(self, entry_id: str, name: str, entry_type: str, program: Optional[str] = None,
                            country: Optional[str] = None, aliases: Optional[list[str]] = None,
                            remarks: Optional[str] = None) -> str:
        return self._add(SanctionsEntry(id=entry_id, name=name, type=entry_type, program=program, country=country,
                                        aliases=aliases, remarks=remarks))

    def add_precedent_decision(self, decision_id: str, case_summary: str, decision: str,
                               reasoning: Optional[str] = None, risk_factors: Optional[dict] = None) -> str:
        return self._add(PrecedentDecision(id=decision_id, case_summary=case_summary, decision=decision,
                                           reasoning=reasoning, risk_factors=risk_factors))

    def reembed(self) -> dict[str, int]:
        """Recompute every stored vector with the current embedder. Returns rows per table."""
        out = {}
        db = self._db()
        try:
            for model in CORPORA:
                rows: list[Any] = db.query(model).all()
                vectors = self.embedder.embed([_text(r) for r in rows]) if rows else []
                for r, v in zip(rows, vectors, strict=False):
                    r.embedding = v
                    r.embedding_model = self.embedder.name
                out[model.__tablename__] = len(rows)
            db.commit()
            return out
        finally:
            db.close()

    # --- reads --------------------------------------------------------------------------------
    def search_similar_documents(self, query: str, category: Optional[str] = None,
                                 jurisdiction: Optional[str] = None, top_k: int = 5,
                                 vector: Optional[list[float]] = None) -> list[dict]:
        q = vector if vector is not None else self._embed(query)
        db = self._db()
        try:
            self._check_model(db, ComplianceDocument)
            stmt = db.query(ComplianceDocument)
            if category:
                stmt = stmt.filter(ComplianceDocument.category == category)
            if jurisdiction:
                stmt = stmt.filter(ComplianceDocument.jurisdiction == jurisdiction)
            rows = stmt.order_by(ComplianceDocument.embedding.cosine_distance(q), ComplianceDocument.id).limit(top_k).all()
            return [{"id": r.id, "title": r.title, "content": r.content[:500], "category": r.category,
                     "jurisdiction": r.jurisdiction, "score": round(_cosine(r.embedding, q), 4)} for r in rows]
        finally:
            db.close()

    def search_sanctions_matches(self, query: str, top_k: int = 10, threshold: float = 0.8,
                                 vector: Optional[list[float]] = None) -> list[dict]:
        q = vector if vector is not None else self._embed(query)
        db = self._db()
        try:
            self._check_model(db, SanctionsEntry)
            rows = (db.query(SanctionsEntry).order_by(SanctionsEntry.embedding.cosine_distance(q), SanctionsEntry.id)
                    .limit(top_k).all())
            out = []
            for r in rows:
                score = round(_cosine(r.embedding, q), 4)
                if score >= threshold:
                    out.append({"id": r.id, "name": r.name, "type": r.type, "program": r.program,
                                "country": r.country, "aliases": r.aliases, "similarity_score": score})
            return out
        finally:
            db.close()

    def search_similar_precedents(self, query: str, decision_filter: Optional[str] = None, top_k: int = 5,
                                  vector: Optional[list[float]] = None) -> list[dict]:
        q = vector if vector is not None else self._embed(query)
        db = self._db()
        try:
            self._check_model(db, PrecedentDecision)
            stmt = db.query(PrecedentDecision)
            if decision_filter:
                stmt = stmt.filter(PrecedentDecision.decision == decision_filter)
            rows = stmt.order_by(PrecedentDecision.embedding.cosine_distance(q), PrecedentDecision.id).limit(top_k).all()
            return [{"id": r.id, "case_summary": r.case_summary, "decision": r.decision, "reasoning": r.reasoning,
                     "risk_factors": r.risk_factors, "score": round(_cosine(r.embedding, q), 4)} for r in rows]
        finally:
            db.close()

    def multi_hop_retrieval(self, transaction_context: dict, max_results: int = 10) -> dict:
        """Policies relevant to the transaction (memo + context), each party screened separately
        against the sanctions corpus (combining names dilutes each match), similar precedents."""
        context = " ".join(p for p in (
            transaction_context.get("transaction_type"), transaction_context.get("destination_country"),
            transaction_context.get("description"),
        ) if p)
        parties = [p for p in (transaction_context.get("sender_name"), transaction_context.get("receiver_name")) if p]
        query = " ".join([*parties, context]) or "transaction"
        party_vectors = [self._embed(p) for p in parties]
        policy_vector, query_vector = self._embed(context or query), self._embed(query)
        sanctions: dict[str, dict] = {}
        for party, vector in zip(parties, party_vectors, strict=True):
            for m in self.search_sanctions_matches(party, top_k=5, threshold=0.7, vector=vector):
                prev = sanctions.get(m["id"])
                if prev is None or m["similarity_score"] > prev["similarity_score"]:
                    sanctions[m["id"]] = {**m, "matched_party": party}
        return {
            "embedding_model": self.embedder.name,
            "semantic": self.embedder.semantic,
            # every document type (policy, regulation, guideline) can be relevant to a transaction
            "policies": self.search_similar_documents(context or query, top_k=3, vector=policy_vector),
            "sanctions_matches": sorted(sanctions.values(), key=lambda x: (-x["similarity_score"], x["id"])),
            "similar_precedents": self.search_similar_precedents(query, top_k=3, vector=query_vector),
        }
