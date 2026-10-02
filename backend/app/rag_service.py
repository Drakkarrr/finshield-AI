"""
FinShield AI - RAG Retrieval Service

Provides semantic search over compliance policies, sanctions lists,
and precedent decisions using pgvector.

Embedding strategy (local-first, no heavy ML runtime required):
- Default: deterministic hashing-based embedding (numpy only) producing
  384-dim vectors with lexical similarity. Fast, reproducible, no GPU/torch.
- Optional: if `sentence-transformers` is installed, it is used automatically
  for higher-quality semantic embeddings. The vector dimension must match the
  pgvector column (384) — all-MiniLM-L6-v2 is 384-dim, so both paths align.
"""

import os
import re
import hashlib
import numpy as np
from typing import List, Dict, Optional, Tuple
from sqlalchemy import create_engine, Column, String, Text, Float, DateTime, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pgvector.sqlalchemy import Vector
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384

# Detect optional sentence-transformers at import time
_ST_MODEL = None
_ST_AVAILABLE = False
try:
    # Only attempt if explicitly enabled to avoid heavy import cost by default
    if os.getenv("RAG_USE_SENTENCE_TRANSFORMERS", "false").lower() == "true":
        from sentence_transformers import SentenceTransformer
        _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        _ST_AVAILABLE = True
        logger.info("RAG using sentence-transformers (all-MiniLM-L6-v2)")
except Exception as e:  # pragma: no cover - optional dependency
    logger.warning(f"sentence-transformers unavailable, using hashing embeddings: {e}")
    _ST_MODEL = None
    _ST_AVAILABLE = False


def _tokenize(text: str) -> List[str]:
    """Lowercase word tokenization with simple normalization."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _hash_embedding(text: str) -> List[float]:
    """
    Deterministic hashing-based (feature hashing) embedding.

    Uses the hashing trick: each token (and bigram) is hashed to one of
    EMBEDDING_DIM buckets with a sign, then L2-normalized. Cosine similarity
    between two such vectors approximates lexical overlap — sufficient for
    compliance-document and sanctions-name matching without any ML runtime.
    """
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    # unigrams + bigrams for light context capture
    features = tokens + [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    for feat in features:
        h = hashlib.md5(feat.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if h[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a list of texts."""
    if _ST_AVAILABLE and _ST_MODEL is not None:
        return _ST_MODEL.encode(texts, show_progress_bar=False).tolist()
    return [_hash_embedding(t) for t in texts]


def get_single_embedding(text: str) -> List[float]:
    """Get embedding for a single text."""
    return get_embeddings([text])[0]


def _cosine_similarity(a, b) -> float:
    """Compute cosine similarity between two embedding vectors in Python.

    Used to score already-retrieved rows (the SQL ORDER BY handles ranking;
    this recomputes the similarity value for the response payload).
    """
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)

# Database setup for RAG
RAGBase = declarative_base()

class ComplianceDocument(RAGBase):
    """Compliance policy documents and regulations."""
    __tablename__ = "compliance_documents"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=False)  # policy, regulation, guideline
    jurisdiction = Column(String, nullable=True)
    effective_date = Column(DateTime, nullable=True)
    doc_metadata = Column("metadata", JSON, nullable=True)
    embedding = Column(Vector(384))  # hashing / MiniLM both produce 384-dim vectors
    created_at = Column(DateTime, default=datetime.utcnow)
    
class SanctionsEntry(RAGBase):
    """Sanctions list entries (OFAC, UN, EU, etc.)."""
    __tablename__ = "sanctions_entries"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # individual, entity, vessel
    program = Column(String, nullable=True)  # SDN, SSI, etc.
    country = Column(String, nullable=True)
    aliases = Column(JSON, nullable=True)
    remarks = Column(Text, nullable=True)
    embedding = Column(Vector(384))
    created_at = Column(DateTime, default=datetime.utcnow)

class PrecedentDecision(RAGBase):
    """Historical compliance decisions for reference."""
    __tablename__ = "precedent_decisions"
    
    id = Column(String, primary_key=True)
    case_summary = Column(Text, nullable=False)
    decision = Column(String, nullable=False)  # approved, flagged, blocked
    reasoning = Column(Text, nullable=True)
    risk_factors = Column(JSON, nullable=True)
    embedding = Column(Vector(384))
    created_at = Column(DateTime, default=datetime.utcnow)


class RAGRetrievalService:
    """Service for RAG-based compliance retrieval."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        # Ensure the pgvector extension exists before creating vector columns
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        RAGBase.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("RAG Retrieval Service initialized")
    
    def _get_db(self) -> Session:
        return self.SessionLocal()
    
    def add_compliance_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        category: str,
        jurisdiction: Optional[str] = None,
        effective_date: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a compliance document with automatic embedding."""
        embedding = get_single_embedding(f"{title} {content}")
        
        doc = ComplianceDocument(
            id=doc_id,
            title=title,
            content=content,
            category=category,
            jurisdiction=jurisdiction,
            effective_date=effective_date,
            doc_metadata=metadata,
            embedding=embedding
        )
        
        db = self._get_db()
        try:
            db.add(doc)
            db.commit()
            logger.info(f"Added compliance document: {doc_id}")
            return doc_id
        finally:
            db.close()
    
    def add_sanctions_entry(
        self,
        entry_id: str,
        name: str,
        entry_type: str,
        program: Optional[str] = None,
        country: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        remarks: Optional[str] = None
    ) -> str:
        """Add a sanctions list entry with automatic embedding."""
        text_to_embed = f"{name} {' '.join(aliases or [])} {program or ''}"
        embedding = get_single_embedding(text_to_embed)
        
        entry = SanctionsEntry(
            id=entry_id,
            name=name,
            type=entry_type,
            program=program,
            country=country,
            aliases=aliases,
            remarks=remarks,
            embedding=embedding
        )
        
        db = self._get_db()
        try:
            db.add(entry)
            db.commit()
            logger.info(f"Added sanctions entry: {entry_id}")
            return entry_id
        finally:
            db.close()
    
    def add_precedent_decision(
        self,
        decision_id: str,
        case_summary: str,
        decision: str,
        reasoning: Optional[str] = None,
        risk_factors: Optional[Dict] = None
    ) -> str:
        """Add a precedent decision with automatic embedding."""
        embedding = get_single_embedding(f"{case_summary} {reasoning or ''}")
        
        precedent = PrecedentDecision(
            id=decision_id,
            case_summary=case_summary,
            decision=decision,
            reasoning=reasoning,
            risk_factors=risk_factors,
            embedding=embedding
        )
        
        db = self._get_db()
        try:
            db.add(precedent)
            db.commit()
            logger.info(f"Added precedent decision: {decision_id}")
            return decision_id
        finally:
            db.close()
    
    def search_similar_documents(
        self,
        query: str,
        category: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """Search for similar compliance documents."""
        query_embedding = get_single_embedding(query)
        
        db = self._get_db()
        try:
            query_stmt = db.query(ComplianceDocument)
            
            if category:
                query_stmt = query_stmt.filter(ComplianceDocument.category == category)
            if jurisdiction:
                query_stmt = query_stmt.filter(ComplianceDocument.jurisdiction == jurisdiction)
            
            # Use pgvector similarity search
            results = query_stmt.order_by(
                ComplianceDocument.embedding.cosine_distance(query_embedding)
            ).limit(top_k).all()
            
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "content": r.content[:500],  # Truncate for response
                    "category": r.category,
                    "jurisdiction": r.jurisdiction,
                    "score": _cosine_similarity(r.embedding, query_embedding)
                }
                for r in results
            ]
        finally:
            db.close()
    
    def search_sanctions_matches(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.8
    ) -> List[Dict]:
        """Search for potential sanctions matches."""
        query_embedding = get_single_embedding(query)
        
        db = self._get_db()
        try:
            results = db.query(SanctionsEntry).order_by(
                SanctionsEntry.embedding.cosine_distance(query_embedding)
            ).limit(top_k).all()
            
            matches = []
            for r in results:
                similarity = _cosine_similarity(r.embedding, query_embedding)
                if similarity >= threshold:
                    matches.append({
                        "id": r.id,
                        "name": r.name,
                        "type": r.type,
                        "program": r.program,
                        "country": r.country,
                        "aliases": r.aliases,
                        "similarity_score": similarity
                    })
            
            return matches
        finally:
            db.close()
    
    def search_similar_precedents(
        self,
        query: str,
        decision_filter: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """Search for similar historical decisions."""
        query_embedding = get_single_embedding(query)
        
        db = self._get_db()
        try:
            query_stmt = db.query(PrecedentDecision)
            
            if decision_filter:
                query_stmt = query_stmt.filter(PrecedentDecision.decision == decision_filter)
            
            results = query_stmt.order_by(
                PrecedentDecision.embedding.cosine_distance(query_embedding)
            ).limit(top_k).all()
            
            return [
                {
                    "id": r.id,
                    "case_summary": r.case_summary,
                    "decision": r.decision,
                    "reasoning": r.reasoning,
                    "risk_factors": r.risk_factors,
                    "score": _cosine_similarity(r.embedding, query_embedding)
                }
                for r in results
            ]
        finally:
            db.close()
    
    def multi_hop_retrieval(
        self,
        transaction_context: Dict,
        max_results: int = 10
    ) -> Dict:
        """
        Perform multi-hop retrieval for a transaction.
        
        1. Search for relevant compliance policies
        2. Check sanctions lists
        3. Find similar historical decisions
        """
        # Build query from transaction context
        query_parts = [
            transaction_context.get("sender_name", ""),
            transaction_context.get("receiver_name", ""),
            transaction_context.get("transaction_type", ""),
            transaction_context.get("destination_country", ""),
        ]
        query = " ".join([p for p in query_parts if p])
        
        # Screen each party independently (combining names dilutes each match),
        # then merge unique sanctions hits keeping the highest score per entry.
        sanctions_matches: Dict[str, Dict] = {}
        for party in (transaction_context.get("sender_name", ""), transaction_context.get("receiver_name", "")):
            if not party:
                continue
            for m in self.search_sanctions_matches(party, top_k=5, threshold=0.7):
                prev = sanctions_matches.get(m["id"])
                if prev is None or m["similarity_score"] > prev["similarity_score"]:
                    m["matched_party"] = party
                    sanctions_matches[m["id"]] = m
        merged_sanctions = sorted(
            sanctions_matches.values(),
            key=lambda x: x["similarity_score"],
            reverse=True,
        )

        results = {
            "policies": self.search_similar_documents(
                query,
                category="policy",
                top_k=3
            ),
            "sanctions_matches": merged_sanctions,
            "similar_precedents": self.search_similar_precedents(
                query,
                top_k=3
            )
        }

        return results
