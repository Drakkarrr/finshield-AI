"""FinShield SDK Data Models."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class TransactionRequest:
    """Transaction screening request."""
    sender_name: str
    receiver_name: str
    amount: float
    currency: str
    transaction_type: str = "wire"
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
    destination_country: Optional[str] = None
    description: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass
class RuleResult:
    """Result of a single rule evaluation."""
    rule_id: str
    rule_type: str
    rule_name: str
    triggered: bool
    detail: Optional[str]
    latency_ms: float


@dataclass
class RagMatch:
    """RAG retrieval match."""
    id: str
    score: Optional[float] = None
    similarity_score: Optional[float] = None
    title: Optional[str] = None
    name: Optional[str] = None
    program: Optional[str] = None
    decision: Optional[str] = None
    case_summary: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


@dataclass
class RagContext:
    """RAG retrieved context."""
    policies: list[RagMatch] = field(default_factory=list)
    sanctions_matches: list[RagMatch] = field(default_factory=list)
    similar_precedents: list[RagMatch] = field(default_factory=list)


@dataclass
class ScreeningResult:
    """Transaction screening result."""
    transaction_id: str
    idempotency_key: str
    status: str
    risk_score: float
    credit_tier: str
    credits_consumed: int
    rule_results: list[RuleResult]
    behavioral_score: Optional[float]
    ml_classification: Optional[str]
    ml_confidence: Optional[float]
    total_latency_ms: float
    timestamp: str
    pipeline_stages: list[str]


@dataclass
class TransactionResponse:
    """API response for transaction screening."""
    success: bool
    data: Optional[ScreeningResult]
    error: Optional[str]


@dataclass
class CaseData:
    """Case data."""
    case_id: str
    transaction_id: str
    status: str
    priority: str
    reason: str
    assigned_to: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class RuleDefinition:
    """Rule definition."""
    rule_id: str
    rule_type: str
    name: str
    description: str
    enabled: bool
    action: str
    parameters: dict
    metadata: Optional[dict] = None
    is_customized: Optional[bool] = None


@dataclass
class UserProfile:
    """User profile."""
    id: str
    email: str
    first_name: str
    last_name: str
    company: Optional[str]
    plan: str
    total_credits: int
    used_credits: int
    credits_remaining: int
    created_at: str


@dataclass
class CreditsData:
    """Credits information."""
    total_credits: int
    used_credits: int
    remaining_credits: int
    plan: str


@dataclass
class StatsData:
    """Dashboard statistics."""
    total_transactions: int
    approved: int
    flagged: int
    blocked: int
    in_review: int
    open_cases: int
    avg_risk_score: float
    credits_used: int
    credits_remaining: int


@dataclass
class HealthData:
    """Health check response."""
    status: str
    version: str
    services: dict
    uptime_seconds: int
