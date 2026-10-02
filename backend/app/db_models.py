"""
FinShield AI — Database Models
SQLAlchemy ORM models for users, transactions, cases, and API keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

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

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=generate_uuid)
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

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    rule_id = Column(String, nullable=False)  # e.g. RULE-001
    enabled = Column(Boolean, default=True)
    custom_parameters = Column(JSON, nullable=True)  # User overrides
    
    # Priority and versioning
    priority = Column(Integer, default=100)  # Lower number = higher priority
    version = Column(Integer, default=1)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    
    # Hit tracking
    hit_count = Column(Integer, default=0)
    last_hit_at = Column(DateTime, nullable=True)
    false_positive_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
