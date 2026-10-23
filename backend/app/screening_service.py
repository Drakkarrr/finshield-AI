"""Screening orchestration: resolve every input of the pure pipeline, through circuit breakers.

The pipeline (app.domain.screening) never touches I/O. This module does all of it: list snapshot,
account history and population, velocity, RAG retrieval, model versions. A dependency that fails
or whose breaker is open is passed in as failed, and the gate then holds the decision for review.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import config_service, resilience
from app.db_models import AccountBaseline, Transaction
from app.domain import behavioral
from app.domain.lists import provider as lists
from app.domain.models_registry import registry
from app.domain.screening import ScreeningContext, ScreeningOutcome, screen
from app.models import TransactionRequest

logger = logging.getLogger("finshield.screening")

HISTORY_DAYS = 90
HISTORY_LIMIT = 1000
POPULATION_LIMIT = 5000


def account_key(tx: TransactionRequest) -> tuple[str, str]:
    if tx.account_id:
        return tx.account_id, "account_id"
    if tx.sender_id:
        return tx.sender_id, "sender_id"
    return tx.sender_name, "sender_name"


def history(db: Session, tenant_id: str, key: str, since: datetime) -> list[behavioral.HistoryRow]:
    rows = (db.query(Transaction.amount, Transaction.created_at, Transaction.destination_country,
                     Transaction.receiver_name, Transaction.transaction_type)
            .filter(Transaction.tenant_id == tenant_id, Transaction.account_id == key, Transaction.created_at >= since)
            .order_by(Transaction.created_at.desc(), Transaction.id).limit(HISTORY_LIMIT).all())
    return [behavioral.HistoryRow(*r) for r in rows]


def population(db: Session, tenant_id: str, since: datetime) -> Optional[behavioral.Population]:
    amounts = [a for (a,) in db.query(Transaction.amount)
               .filter(Transaction.tenant_id == tenant_id, Transaction.created_at >= since)
               .order_by(Transaction.created_at.desc(), Transaction.id).limit(POPULATION_LIMIT).all()]
    return behavioral.compute_population(amounts)


def build_context(db: Session, tenant_id: str, tx: TransactionRequest, rag_service: Any,
                  now: Optional[datetime] = None) -> ScreeningContext:
    now = now or datetime.utcnow()
    cfg = config_service.screening_config(db)
    failed: list[str] = []

    watchlist = None
    try:
        watchlist = resilience.call("watchlist", lambda: lists.snapshot(db))
    except resilience.DependencyUnavailable as e:
        logger.warning("%s", e)
        failed.append("watchlist")

    model = registry.BUILTIN
    shadow = None
    try:
        model = resilience.call("risk_model", lambda: registry.active_model(db))
        shadow = registry.shadow_model(db)
    except resilience.DependencyUnavailable as e:
        logger.warning("%s", e)
        failed.append("risk_model")

    rag_context, rag_status = None, "disabled"
    if rag_service is not None and config_service.get_flag(db, "screening.rag"):
        try:
            rag_context = resilience.call("rag", lambda: rag_service.multi_hop_retrieval({
                "sender_name": tx.sender_name,
                "receiver_name": tx.receiver_name,
                "transaction_type": tx.transaction_type.value,
                "destination_country": tx.destination_country,
                "description": tx.description,
            }))
            rag_status = "ok" if rag_service.embedder.semantic else "lexical_fallback"
        except resilience.DependencyUnavailable as e:
            logger.warning("%s", e)
            rag_status = "unavailable"
            failed.append("rag")

    key, key_source = account_key(tx)
    since = now - timedelta(days=HISTORY_DAYS)
    rows = history(db, tenant_id, key, since)
    velocity = sum(1 for h in rows if h.created_at >= now - timedelta(hours=24))
    return ScreeningContext(
        config=cfg, model=model, shadow_model=shadow,
        rule_configs=config_service.rule_overrides(db, tenant_id, now),
        watchlist=watchlist, high_risk_countries=lists.high_risk_countries(db),
        account_key=key, account_key_source=key_source,
        baseline=behavioral.compute_baseline(rows), population=population(db, tenant_id, since),
        velocity_24h=velocity, rag_context=rag_context, rag_status=rag_status,
        failed_dependencies=tuple(failed),
    )


def run(db: Session, tenant_id: str, tx: TransactionRequest, rag_service: Any) -> ScreeningOutcome:
    return screen(tx, build_context(db, tenant_id, tx, rag_service))


def refresh_baseline(db: Session, tenant_id: str, user_id: str, key: str,
                     now: Optional[datetime] = None) -> Optional[AccountBaseline]:
    """Recompute and store the account's baseline from its history (also used by the
    /behavioral/update-baseline endpoint, so the two can never disagree)."""
    now = now or datetime.utcnow()
    stats = behavioral.compute_baseline(history(db, tenant_id, key, now - timedelta(days=HISTORY_DAYS)))
    if stats is None:
        return None
    row = db.query(AccountBaseline).filter(AccountBaseline.tenant_id == tenant_id,
                                           AccountBaseline.account_id == key).first()
    if row is None:
        row = AccountBaseline(user_id=user_id, account_id=key)
        db.add(row)
    cfg = config_service.screening_config(db)
    row.avg_amount = stats.avg_amount
    row.std_dev_amount = stats.std_dev_amount
    row.max_amount = stats.max_amount
    row.min_amount = stats.min_amount
    row.total_transactions = stats.total_transactions
    row.first_transaction_at = stats.first_transaction_at
    row.last_transaction_at = stats.last_transaction_at
    row.history_days = stats.history_days
    row.typical_countries = stats.typical_countries
    row.typical_payees = stats.typical_payees
    row.typical_tx_types = stats.typical_tx_types
    row.is_cold_start = behavioral.is_cold_start(stats, behavioral.BehavioralConfig(
        cfg.behavioral_trigger_warm, cfg.behavioral_trigger_cold_start, cfg.cold_start_days, cfg.min_history_txs))
    row.last_computed_at = now
    return row
