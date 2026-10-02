"""
FinShield AI — Transaction Compliance Engine
Data models for the compliance pipeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class TransactionType(str, Enum):
    WIRE = "wire"
    ACH = "ach"
    CARD = "card"
    INTERNATIONAL = "international"
    CRYPTO = "crypto"
    P2P = "p2p"


class ScreeningStatus(str, Enum):
    APPROVED = "approved"
    FLAGGED = "flagged"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    PENDING = "pending"


class CaseStatus(str, Enum):
    CREATED = "created"
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CasePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleType(str, Enum):
    SANCTIONS = "sanctions"
    PEP = "pep"
    THRESHOLD = "threshold"
    VELOCITY = "velocity"
    GEOGRAPHY = "geography"
    BEHAVIORAL = "behavioral"


class CreditTier(str, Enum):
    RULE_ONLY = "rule_only"         # 0.2 credits
    BEHAVIORAL = "behavioral"       # 0.5 credits
    FULL_ML = "full_ml"             # 1.0 credits


# --- Request Models ---

class TransactionRequest(BaseModel):
    """Incoming transaction to screen."""
    idempotency_key: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Idempotency key for deduplication"
    )
    amount: float = Field(gt=0, description="Transaction amount")
    currency: str = Field(default="USD", max_length=3)
    transaction_type: TransactionType
    sender_name: str
    sender_id: Optional[str] = None
    receiver_name: str
    receiver_id: Optional[str] = None
    destination_country: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None


class CaseCreateRequest(BaseModel):
    """Request to create a compliance case."""
    transaction_id: str
    reason: str
    priority: CasePriority = CasePriority.MEDIUM
    assigned_to: Optional[str] = None


# --- Response Models ---

class RuleResult(BaseModel):
    rule_id: str
    rule_type: RuleType
    rule_name: str
    triggered: bool
    detail: Optional[str] = None
    latency_ms: float


class ScreeningResult(BaseModel):
    """Result of the full compliance pipeline."""
    transaction_id: str
    idempotency_key: str
    status: ScreeningStatus
    risk_score: float = Field(ge=0, le=1)
    credit_tier: CreditTier
    credits_consumed: float
    rule_results: list[RuleResult]
    behavioral_score: Optional[float] = None
    ml_classification: Optional[str] = None
    ml_confidence: Optional[float] = None
    total_latency_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pipeline_stages: list[str]
    rag_context: Optional[dict] = None


class TransactionResponse(BaseModel):
    """API response wrapper."""
    success: bool
    data: Optional[ScreeningResult] = None
    error: Optional[str] = None


class CaseResponse(BaseModel):
    case_id: str
    transaction_id: str
    status: CaseStatus
    priority: CasePriority
    reason: str
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, str]
    uptime_seconds: float


class CreditsResponse(BaseModel):
    total_credits: int
    used_credits: int
    remaining_credits: int
    plan: str
