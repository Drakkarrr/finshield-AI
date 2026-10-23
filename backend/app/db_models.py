"""
FinShield AI — Database Models
SQLAlchemy ORM models. Every table lives on the one Base so Alembic sees the whole schema.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
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
    # RBAC (S3.1)
    role = Column(String, default="user")  # user, analyst, admin, super_admin
    # Multi-tenancy (S3.4)
    tenant_id = Column(String, nullable=True, index=True)  # Tenant isolation
    # Trial
    is_trial = Column(Boolean, default=True)
    trial_expires_at = Column(DateTime, nullable=True)
    # Billing cycle tracking
    billing_cycle_start = Column(DateTime, nullable=True)
    billing_cycle_end = Column(DateTime, nullable=True)
    pending_plan_change = Column(String, nullable=True)  # Downgrade queued for end-of-cycle
    # Preferences
    timezone = Column(String, nullable=True)  # e.g. "America/New_York"
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String, nullable=True, index=True)  # Multi-tenancy (S3.4)
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String, nullable=True, index=True)  # Multi-tenancy (S3.4)
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

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String, nullable=True, index=True)  # Multi-tenancy (S3.4)
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
    """Immutable audit log with hash chain for tamper detection (S3.2)."""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # Hash chain for immutability (S3.2)
    prev_hash = Column(String, nullable=True)  # Hash of previous entry
    entry_hash = Column(String, nullable=True, index=True)  # Hash of this entry
    chain_sequence = Column(Integer, nullable=True, index=True)  # Sequential number
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# SQLAlchemy event listener to auto-compute hash chain on insert
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import event, text
import hashlib
import json

@event.listens_for(AuditLog, 'before_insert')
def compute_audit_hash(mapper, connection, target):
    """Automatically compute hash chain for new audit log entries."""
    # Get next sequence and previous hash
    result = connection.execute(text("SELECT MAX(chain_sequence) FROM audit_logs")).fetchone()
    max_seq = result[0] if result and result[0] is not None else 0
    
    target.chain_sequence = max_seq + 1
    
    # Get previous hash
    if max_seq > 0:
        prev_result = connection.execute(
            text(f"SELECT entry_hash FROM audit_logs WHERE chain_sequence = {max_seq}")
        ).fetchone()
        target.prev_hash = prev_result[0] if prev_result else None
    else:
        target.prev_hash = None
    
    # Compute entry hash
    if not target.id:
        target.id = f"audit-{target.chain_sequence}"
    if not target.created_at:
        target.created_at = datetime.utcnow()
    
    data = {
        "id": target.id,
        "user_id": target.user_id,
        "action": target.action,
        "resource_type": target.resource_type,
        "resource_id": target.resource_id,
        "details": target.details,
        "ip_address": target.ip_address,
        "created_at": target.created_at.isoformat() if target.created_at else None,
        "prev_hash": target.prev_hash,
        "chain_sequence": target.chain_sequence,
    }
    json_str = json.dumps(data, sort_keys=True, default=str)
    target.entry_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String, nullable=True, index=True)  # Multi-tenancy (S3.4)
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
    """Circuit breaker state per downstream dependency."""
    __tablename__ = "circuit_breakers"

    id = Column(String, primary_key=True, default=generate_uuid)
    dependency = Column(String, nullable=False, unique=True)  # model_server, pgvector, redis, notification_service
    state = Column(String, default="closed")  # closed, open, half_open
    failure_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    last_failure_at = Column(DateTime, nullable=True)
    last_state_change_at = Column(DateTime, nullable=True)

    # Configuration
    failure_threshold = Column(Integer, default=5)  # Failures before opening
    cooldown_seconds = Column(Integer, default=60)  # Seconds to wait before half-open
    half_open_max_calls = Column(Integer, default=3)  # Max probe calls in half-open

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookEvent(Base):
    """Webhook event delivery tracking."""
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=generate_uuid)
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
    """Rolling per-account behavioral baseline for fraud detection."""
    __tablename__ = "account_baselines"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    account_id = Column(String, nullable=False)  # External account identifier

    # Rolling statistics (90-day window by default)
    avg_amount = Column(Float, default=0.0)
    avg_frequency_per_day = Column(Float, default=0.0)
    max_amount = Column(Float, default=0.0)
    min_amount = Column(Float, default=0.0)
    std_dev_amount = Column(Float, default=0.0)

    # Typical patterns
    typical_countries = Column(JSON, nullable=True)  # List of frequent destination countries
    typical_payees = Column(JSON, nullable=True)  # List of frequent receiver names
    typical_tx_types = Column(JSON, nullable=True)  # List of frequent transaction types

    # Account age tracking
    first_transaction_at = Column(DateTime, nullable=True)
    last_transaction_at = Column(DateTime, nullable=True)
    history_days = Column(Integer, default=0)
    total_transactions = Column(Integer, default=0)

    # Cold-start flag
    is_cold_start = Column(Boolean, default=True)  # True if < 30 days of history

    # Baseline freshness
    last_computed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)


class PEPEntry(Base):
    """Politically Exposed Persons list entries."""
    __tablename__ = "pep_entries"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    position = Column(String, nullable=True)  # Current or former position
    country = Column(String, nullable=True)
    category = Column(String, nullable=True)  # domestic, foreign, international_org
    aliases = Column(JSON, nullable=True)
    source = Column(String, nullable=True)  # e.g., "World-Check", "Dow Jones"
    embedding = Column(Vector(EMBEDDING_DIM))
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskModelVersion(Base):
    """Versioned risk models with shadow mode support."""
    __tablename__ = "risk_model_versions"

    id = Column(String, primary_key=True)
    version = Column(String, nullable=False, unique=True)  # e.g., "1.0.0", "2.0.0-beta"
    name = Column(String, nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)
    
    # Model configuration
    model_type = Column(String, nullable=False)  # "rule_based", "ml_classifier", "ensemble"
    config = Column(JSON, nullable=True)  # Model-specific parameters
    
    # Status and deployment
    status = Column(String, default="development")  # development, shadow, production, deprecated
    is_active = Column(Boolean, default=False)  # Currently serving traffic
    
    # Shadow mode support
    shadow_of = Column(String, ForeignKey("risk_model_versions.version"), nullable=True)
    shadow_percentage = Column(Float, default=0.0)  # % of traffic to shadow (0-100)
    
    # Model card metadata
    training_data_summary = Column(Text, nullable=True)
    performance_metrics = Column(JSON, nullable=True)  # precision, recall, FPR, etc.
    limitations = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    deprecated_at = Column(DateTime, nullable=True)


class DSARRequest(Base):
    """Data Subject Access Request tracking (S3.3 Privacy)."""
    __tablename__ = "dsar_requests"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    request_type = Column(String, nullable=False)  # access, erasure, rectification, portability
    status = Column(String, default="pending")  # pending, processing, completed, denied
    reason = Column(Text, nullable=True)
    
    # Request details
    requested_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String, nullable=True)
    
    # Export/erasure results
    data_export_path = Column(String, nullable=True)  # Path to exported data file
    records_affected = Column(Integer, default=0)
    retention_preserved = Column(Boolean, default=False)  # True if legal retention kept
    
    # Audit
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Tenant(Base):
    """Multi-tenancy support (S3.4)."""
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)  # URL-friendly identifier
    domain = Column(String, nullable=True, unique=True)  # Custom domain
    
    # Configuration
    plan = Column(String, default="starter")
    max_users = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    
    # Settings
    settings = Column(JSON, nullable=True)  # Tenant-specific settings
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookSubscription(Base):
    """Webhook subscriptions for event delivery (S4.2)."""
    __tablename__ = "webhook_subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=False)  # HMAC signing secret
    
    # Event types to subscribe to
    event_types = Column(JSON, nullable=False)  # ["transaction.blocked", "case.escalated", etc.]
    
    # Status
    is_active = Column(Boolean, default=True)
    consecutive_failures = Column(Integer, default=0)
    delivery_count = Column(Integer, default=0)
    last_delivered_at = Column(DateTime, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User")


class PrecedentDecision(Base):
    """Historical compliance decisions for reference."""
    __tablename__ = "precedent_decisions"

    id = Column(String, primary_key=True)
    case_summary = Column(Text, nullable=False)
    decision = Column(String, nullable=False)  # approved, flagged, blocked
    reasoning = Column(Text, nullable=True)
    risk_factors = Column(JSON, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM))
    created_at = Column(DateTime, default=datetime.utcnow)
