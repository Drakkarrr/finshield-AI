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

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="transactions")


class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    status = Column(String, default="open")
    priority = Column(String, default="medium")
    reason = Column(Text, nullable=False)
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cases")
    transaction = relationship("Transaction")


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
    """User-customizable rule configuration."""
    __tablename__ = "rule_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    rule_id = Column(String, nullable=False)  # e.g. RULE-001
    enabled = Column(Boolean, default=True)
    custom_parameters = Column(JSON, nullable=True)  # User overrides
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
