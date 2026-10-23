"""
FinShield AI — Database Models
SQLAlchemy ORM models. Every table lives on the one Base so Alembic sees the whole schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    """An organisation. Every owned row carries tenant_id; Postgres RLS enforces the boundary (D3)."""
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('analyst', 'investigator', 'supervisor', 'admin')", name="ck_users_role"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    company = Column(String, nullable=True)
    plan = Column(String, default="starter")
    total_credits = Column(Integer, default=1000)
    used_credits = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    # analyst < investigator < supervisor < admin (app.permissions). The tenant's first user is admin.
    role: Mapped[str] = mapped_column(String, default="analyst", server_default="analyst")
    # Trial
    is_trial = Column(Boolean, default=True)
    trial_expires_at = Column(DateTime, nullable=True)
    # Billing cycle tracking
    billing_cycle_start = Column(DateTime, nullable=True)
    billing_cycle_end = Column(DateTime, nullable=True)
    pending_plan_change = Column(String, nullable=True)  # Downgrade queued for end-of-cycle
    # Preferences
    timezone = Column(String, nullable=True)  # e.g. "America/New_York"
    # Saved payment method (for Qoder-like flow)
    saved_card_last4 = Column(String, nullable=True)
    saved_card_expiry = Column(String, nullable=True)
    saved_card_holder = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, nullable=False)
    key_prefix = Column(String, nullable=False)  # First 8 chars for display
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    transaction_type = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    receiver_name = Column(String, nullable=False)
    destination_country = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Screening results
    status = Column(String, default="pending")
    risk_score = Column(Float, default=0.0)
    credit_tier = Column(String, nullable=True)
    credits_consumed = Column(Float, default=0.0)
    rule_results = Column(JSON, nullable=True)
    behavioral_score = Column(Float, nullable=True)
    ml_classification = Column(String, nullable=True)
    ml_confidence = Column(Float, nullable=True)
    total_latency_ms = Column(Float, nullable=True)
    pipeline_stages = Column(JSON, nullable=True)
    rag_context = Column(JSON, nullable=True)

    # Structured, reproducible decision (S2.1/S2.2/S2.5)
    account_id = Column(String, nullable=True, index=True)  # baseline key: account_id > sender_id > sender_name
    reasons = Column(JSON, nullable=True)
    decision = Column(JSON, nullable=True)  # the full ScreeningResult as returned
    model_version = Column(String, nullable=True)
    degraded = Column(Boolean, default=False)
    shadow_result = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    status = Column(String, default="open")  # open, under_review, escalated, resolved, closed
    priority = Column(String, default="medium")  # low, medium, high, critical
    severity = Column(String, default="medium")  # low, medium, high, critical (for SLA)
    reason = Column(Text, nullable=False)
    assigned_to = Column(String, nullable=True)

    # SLA tracking
    sla_deadline = Column(DateTime, nullable=True)  # Auto-calculated from severity
    escalated_at = Column(DateTime, nullable=True)
    escalated_by = Column(String, nullable=True)
    escalation_reason = Column(Text, nullable=True)

    # Resolution
    resolution = Column(String, nullable=True)  # confirmed_suspicious, false_positive, filed_sar, closed_no_action
    resolution_summary = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cases")
    transaction = relationship("Transaction")
    filings = relationship("Filing", back_populates="case", cascade="all, delete-orphan")
    notes = relationship("CaseNote", back_populates="case", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # blocked_tx, new_case, credit_alert, system, plan_change
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    link = Column(String, nullable=True)  # Optional deep link
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    email_blocked_tx = Column(Boolean, default=True)
    email_new_cases = Column(Boolean, default=True)
    email_daily_summary = Column(Boolean, default=False)
    email_weekly_report = Column(Boolean, default=True)
    email_system_downtime = Column(Boolean, default=True)
    email_credit_alerts = Column(Boolean, default=True)

    user = relationship("User")


class RuleConfig(Base):
    """User-customizable rule configuration with priority and versioning."""
    __tablename__ = "rule_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    rule_id: Mapped[str] = mapped_column(String)  # e.g. RULE-001
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    custom_parameters: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # User overrides

    # Priority (lower runs first), version (bumped on every change) and effective window
    priority: Mapped[Optional[int]] = mapped_column(Integer, default=100)
    version: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Hit tracking
    hit_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    false_positive_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Metadata
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class CaseComment(Base):
    __tablename__ = "case_comments"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case")
    user = relationship("User")


class CaseNote(Base):
    """Ephemeral investigator notes (not part of immutable audit log)."""
    __tablename__ = "case_notes"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="notes")
    user = relationship("User")


class Filing(Base):
    """SAR/STR regulatory filings for confirmed suspicious cases."""
    __tablename__ = "filings"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    case_id = Column(String, ForeignKey("cases.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Filing type and status
    filing_type = Column(String, nullable=False)  # SAR (Suspicious Activity Report), STR (Suspicious Transaction Report)
    status = Column(String, default="draft")  # draft, under_review, submitted, confirmed, rejected

    # Deadline tracking
    deadline = Column(DateTime, nullable=True)  # 30 days from detection (FinCEN SAR)

    # Filing content
    narrative = Column(Text, nullable=True)  # Free-text description of suspicious activity
    structured_data = Column(JSON, nullable=True)  # Auto-populated from case (tx details, parties, amounts)

    # Submission tracking
    reference_number = Column(String, nullable=True)  # Regulator-assigned reference
    submitted_at = Column(DateTime, nullable=True)
    submitted_by = Column(String, nullable=True)  # User ID who submitted
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(String, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    case = relationship("Case", back_populates="filings")
    user = relationship("User")


class CircuitBreaker(Base):
    """Circuit breaker state per real dependency (see app.resilience.DEPENDENCIES)."""
    __tablename__ = "circuit_breakers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    dependency: Mapped[str] = mapped_column(String, unique=True)
    state: Mapped[Optional[str]] = mapped_column(String, default="closed")  # closed, open, half_open
    failure_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    success_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_state_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Configuration
    failure_threshold: Mapped[Optional[int]] = mapped_column(Integer, default=5)  # consecutive failures to open
    cooldown_seconds: Mapped[Optional[int]] = mapped_column(Integer, default=60)  # open -> half_open after this
    half_open_max_calls: Mapped[Optional[int]] = mapped_column(Integer, default=3)  # successes to close

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookEvent(Base):
    """Webhook event delivery tracking."""
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)  # transaction.flagged, case.created, etc.
    payload = Column(JSON, nullable=False)

    # Delivery tracking
    status = Column(String, default="pending")  # pending, delivered, failed, dead_letter
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)

    user = relationship("User")


class AccountBaseline(Base):
    """Per-account behavioral baseline, refreshed after every screening of that account."""
    __tablename__ = "account_baselines"
    __table_args__ = (UniqueConstraint("tenant_id", "account_id", name="uq_account_baselines_tenant_account"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id"), index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    account_id: Mapped[str] = mapped_column(String)  # transactions.account_id key

    # Rolling statistics (90-day window)
    avg_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    avg_frequency_per_day: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    max_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    min_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    std_dev_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0)

    # Typical patterns
    typical_countries: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    typical_payees: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    typical_tx_types: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Account age tracking
    first_transaction_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_transaction_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    history_days: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    total_transactions: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Cold-start flag (see app.domain.behavioral.is_cold_start)
    is_cold_start: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    # Baseline freshness
    last_computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class Setting(Base):
    """Runtime setting override (S1.4). Defaults and validation live in app.config_service."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, primary_key=True, default="global")  # "global" until tenants (S3.4)
    value: Mapped[Any] = mapped_column(JSON)
    updated_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)


class FeatureFlag(Base):
    """Runtime feature flag (S1.4)."""
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, primary_key=True, default="global")
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)


class WatchlistEntry(Base):
    """A sanctions or PEP list entry (S2.3). Replaced wholesale per source on each import."""
    __tablename__ = "watchlist_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # "<source>:<source id>"
    source: Mapped[str] = mapped_column(String, index=True)
    list_version: Mapped[str] = mapped_column(String)
    list_type: Mapped[str] = mapped_column(String, index=True)  # sanctions | pep
    primary_name: Mapped[str] = mapped_column(String)
    aliases: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    raw: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)


class ListImport(Base):
    """One import run per source: what version is loaded, when, and how many entries."""
    __tablename__ = "list_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, index=True)
    list_type: Mapped[str] = mapped_column(String)
    list_version: Mapped[str] = mapped_column(String)
    entry_count: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)


class HighRiskCountry(Base):
    """Jurisdictions screened by RULE-004 (ISO 3166-1 alpha-2)."""
    __tablename__ = "high_risk_countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    source: Mapped[str] = mapped_column(String)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)



class ModelVersion(Base):
    """A versioned risk model (S2.5). Exactly one `active` version per kind (enforced by a partial
    unique index); `shadow` versions are scored alongside but never affect a decision."""
    __tablename__ = "model_versions"
    __table_args__ = (
        Index("uq_model_versions_one_active_per_kind", "kind", unique=True,
              postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'")),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String, default="risk")
    status: Mapped[str] = mapped_column(String, default="shadow")  # shadow | active | retired
    params: Mapped[Any] = mapped_column(JSON)
    feature_list: Mapped[Any] = mapped_column(JSON)
    metrics: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    model_card: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"

# --- RAG corpora (pgvector). 384-dim matches both the hashing embedder and all-MiniLM-L6-v2. ---
EMBEDDING_DIM = 384


class ComplianceDocument(Base):
    """Compliance policy documents and regulations."""
    __tablename__ = "compliance_documents"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=False)  # policy, regulation, guideline
    jurisdiction = Column(String, nullable=True)
    effective_date = Column(DateTime, nullable=True)
    doc_metadata = Column("metadata", JSON, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM))
    embedding_model = Column(String, nullable=True)  # embedder that produced `embedding` (S2.4)
    created_at = Column(DateTime, default=datetime.utcnow)


class SanctionsEntry(Base):
    """Sanctions list entries (OFAC, UN, EU, etc.)."""
    __tablename__ = "sanctions_entries"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # individual, entity, vessel
    program = Column(String, nullable=True)  # SDN, SSI, etc.
    country = Column(String, nullable=True)
    aliases = Column(JSON, nullable=True)
    remarks = Column(Text, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM))
    embedding_model = Column(String, nullable=True)  # embedder that produced `embedding` (S2.4)
    created_at = Column(DateTime, default=datetime.utcnow)


class PrecedentDecision(Base):
    """Historical compliance decisions for reference."""
    __tablename__ = "precedent_decisions"

    id = Column(String, primary_key=True)
    case_summary = Column(Text, nullable=False)
    decision = Column(String, nullable=False)  # approved, flagged, blocked
    reasoning = Column(Text, nullable=True)
    risk_factors = Column(JSON, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM))
    embedding_model = Column(String, nullable=True)  # embedder that produced `embedding` (S2.4)
    created_at = Column(DateTime, default=datetime.utcnow)
