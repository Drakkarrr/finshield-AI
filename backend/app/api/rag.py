"""FinShield AI — RAG retrieval."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import (
    get_current_user,
)
from app.db_models import (
    User,
)
from app.rag_service import RAGRetrievalService

router = APIRouter()


# ============================================================
# RAG RETRIEVAL ROUTES
# ============================================================

class RAGSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    jurisdiction: Optional[str] = None
    top_k: int = 5

class RAGSanctionsSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    threshold: float = 0.8

class RAGPrecedentSearchRequest(BaseModel):
    query: str
    decision_filter: Optional[str] = None
    top_k: int = 5

class RAGMultiHopRequest(BaseModel):
    sender_name: str
    receiver_name: str
    transaction_type: Optional[str] = None
    destination_country: Optional[str] = None

@router.post("/api/v1/rag/search-documents", tags=["RAG"])
def search_compliance_documents(
    request: Request,
    req: RAGSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search for similar compliance documents."""
    rag_service: RAGRetrievalService = getattr(request.app.state, 'rag_service', None)
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not available")

    results = rag_service.search_similar_documents(
        query=req.query,
        category=req.category,
        jurisdiction=req.jurisdiction,
        top_k=req.top_k
    )
    return {"results": results, "count": len(results)}

@router.post("/api/v1/rag/search-sanctions", tags=["RAG"])
def search_sanctions(
    request: Request,
    req: RAGSanctionsSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search for potential sanctions matches."""
    rag_service: RAGRetrievalService = getattr(request.app.state, 'rag_service', None)
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not available")

    results = rag_service.search_sanctions_matches(
        query=req.query,
        top_k=req.top_k,
        threshold=req.threshold
    )
    return {"results": results, "count": len(results), "threshold": req.threshold}

@router.post("/api/v1/rag/search-precedents", tags=["RAG"])
def search_precedents(
    request: Request,
    req: RAGPrecedentSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search for similar historical decisions."""
    rag_service: RAGRetrievalService = getattr(request.app.state, 'rag_service', None)
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not available")

    results = rag_service.search_similar_precedents(
        query=req.query,
        decision_filter=req.decision_filter,
        top_k=req.top_k
    )
    return {"results": results, "count": len(results)}

@router.post("/api/v1/rag/multi-hop-retrieval", tags=["RAG"])
def multi_hop_retrieval(
    request: Request,
    req: RAGMultiHopRequest,
    current_user: User = Depends(get_current_user),
):
    """Perform multi-hop retrieval for transaction context."""
    rag_service: RAGRetrievalService = getattr(request.app.state, 'rag_service', None)
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not available")

    transaction_context = {
        "sender_name": req.sender_name,
        "receiver_name": req.receiver_name,
        "transaction_type": req.transaction_type,
        "destination_country": req.destination_country,
    }

    results = rag_service.multi_hop_retrieval(transaction_context)
    return results
