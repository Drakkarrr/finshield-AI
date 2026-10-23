"""FinShield AI — Transaction screening, listing, export and detail."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import config_service
from app.auth import (
    get_current_user,
)
from app.core import engine, limiter, logger
from app.database import get_db
from app.db_models import (
    Case,
    CaseComment,
    Notification,
    Transaction,
    User,
)
from app.models import (
    CreditTier,
    RuleResult,
    ScreeningResult,
    ScreeningStatus,
    TransactionRequest,
    TransactionResponse,
)

router = APIRouter()


# ============================================================
# COMPLIANCE ROUTES (authenticated + persisted)
# ============================================================

@router.post("/api/v1/transactions", response_model=TransactionResponse, tags=["Compliance"])
@limiter.limit("60/minute")
def screen_transaction(
    request: Request,
    tx: TransactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Screen a transaction through the full compliance pipeline."""
    # Check trial expiry
    if current_user.is_trial and current_user.trial_expires_at:
        if datetime.utcnow() > current_user.trial_expires_at:
            raise HTTPException(status_code=403, detail="Trial expired. Upgrade to continue screening transactions.")

    # Check credits
    remaining = current_user.total_credits - current_user.used_credits
    if remaining < 1.0:
        raise HTTPException(status_code=402, detail="Insufficient credits. Purchase more or upgrade your plan.")

    # Idempotency: if this key was already screened, return the stored result (no crash, no double-charge)
    existing_tx = db.query(Transaction).filter(
        Transaction.idempotency_key == tx.idempotency_key, Transaction.user_id == current_user.id
    ).first()
    if existing_tx:
        return TransactionResponse(success=True, data=ScreeningResult(
            transaction_id=existing_tx.id,
            idempotency_key=existing_tx.idempotency_key,
            status=ScreeningStatus(existing_tx.status),
            risk_score=existing_tx.risk_score,
            credit_tier=CreditTier(existing_tx.credit_tier),
            credits_consumed=existing_tx.credits_consumed,
            rule_results=[RuleResult(**r) for r in (existing_tx.rule_results or [])],
            behavioral_score=existing_tx.behavioral_score,
            ml_classification=existing_tx.ml_classification,
            ml_confidence=existing_tx.ml_confidence,
            total_latency_ms=existing_tx.total_latency_ms or 0.0,
            pipeline_stages=existing_tx.pipeline_stages or [],
            rag_context=existing_tx.rag_context,
            timestamp=existing_tx.created_at,
        ))

    # Runtime config (settings + flags) and the user's in-effect rule overrides
    screening_cfg = config_service.screening_config(db)
    user_rule_configs = config_service.rule_overrides(db, current_user.id)

    result = engine.screen(tx, rule_configs=user_rule_configs, config=screening_cfg, db=db, user_id=current_user.id)

    # RAG enrichment: retrieve relevant compliance context (policies, sanctions, precedents).
    # Non-blocking — if RAG is unavailable, screening still completes normally with honest degraded signal.
    # Wrapped with circuit breaker for pgvector dependency.
    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service is not None and config_service.get_flag(db, "screening.rag"):
        try:
            # Check circuit breaker state for pgvector
            from app.api.breakers import get_or_create_breaker
            from app.domain.circuit_breaker import CircuitBreakerOpen, get_degraded_action
            
            pgvector_breaker = get_or_create_breaker(db, "pgvector")
            
            # If circuit is open, skip RAG and use degraded mode
            if pgvector_breaker.state == "open":
                degraded_action = get_degraded_action("pgvector")
                result.rag_context = {
                    "degraded": True,
                    "reason": f"pgvector circuit breaker is open (state: {pgvector_breaker.state})",
                    "action": degraded_action,
                    "fallback": "rule_based_screening_only",
                }
                if "rag_retrieval_degraded" not in result.pipeline_stages:
                    result.pipeline_stages = result.pipeline_stages + ["rag_retrieval_degraded"]
            else:
                # Circuit is closed or half-open, try RAG retrieval
                try:
                    rag_context = rag_service.multi_hop_retrieval({
                        "sender_name": tx.sender_name,
                        "receiver_name": tx.receiver_name,
                        "transaction_type": tx.transaction_type.value,
                        "destination_country": tx.destination_country,
                    })
                    # Add model version metadata for audit trail
                    from app.rag_service import EMBEDDING_MODEL_VERSION, EMBEDDING_MODEL_NAME
                    rag_context["model_version"] = EMBEDDING_MODEL_VERSION
                    rag_context["model_name"] = EMBEDDING_MODEL_NAME
                    result.rag_context = rag_context
                    # Surface the retrieval stage in the pipeline for explainability
                    if "rag_retrieval" not in result.pipeline_stages:
                        result.pipeline_stages = result.pipeline_stages + ["rag_retrieval"]
                    # A strong sanctions match reinforces escalation (never silently auto-approves)
                    if rag_context.get("sanctions_matches") and result.status.value == "approved":
                        result.status = ScreeningStatus.flagged
                        if result.risk_score < 0.5:
                            result.risk_score = 0.5
                    # Record success for circuit breaker
                    pgvector_breaker.success_count += 1
                    if pgvector_breaker.state == "half_open" and pgvector_breaker.success_count >= pgvector_breaker.half_open_max_calls:
                        pgvector_breaker.state = "closed"
                        pgvector_breaker.failure_count = 0
                        pgvector_breaker.last_state_change_at = datetime.utcnow()
                    db.commit()
                except Exception as e:
                    # Record failure for circuit breaker
                    pgvector_breaker.failure_count += 1
                    pgvector_breaker.last_failure_at = datetime.utcnow()
                    if pgvector_breaker.state == "closed" and pgvector_breaker.failure_count >= pgvector_breaker.failure_threshold:
                        pgvector_breaker.state = "open"
                        pgvector_breaker.last_state_change_at = datetime.utcnow()
                    elif pgvector_breaker.state == "half_open":
                        pgvector_breaker.state = "open"
                        pgvector_breaker.last_state_change_at = datetime.utcnow()
                        pgvector_breaker.failure_count = 1
                    db.commit()
                    logger.warning(f"RAG enrichment failed (screening continues): {e}")
                    # Honest degraded signal - RAG was attempted but failed
                    result.rag_context = {
                        "degraded": True,
                        "reason": f"RAG retrieval failed: {type(e).__name__}",
                        "fallback": "rule_based_screening_only",
                    }
                    if "rag_retrieval_degraded" not in result.pipeline_stages:
                        result.pipeline_stages = result.pipeline_stages + ["rag_retrieval_degraded"]
        except Exception as e:
            logger.warning(f"Circuit breaker check failed: {e}")
    else:
        # Honest degraded signal - RAG not available or disabled
        if rag_service is None:
            result.rag_context = {
                "degraded": True,
                "reason": "RAG service not initialized (no RAG_DATABASE_URL or dependencies unavailable)",
                "fallback": "rule_based_screening_only",
            }
        elif not config_service.get_flag(db, "screening.rag"):
            result.rag_context = {
                "degraded": True,
                "reason": "RAG retrieval disabled via feature flag",
                "fallback": "rule_based_screening_only",
            }

    # Update user credits
    current_user.used_credits += result.credits_consumed

    # Persist transaction
    db_tx = Transaction(
        user_id=current_user.id,
        idempotency_key=tx.idempotency_key,
        amount=tx.amount,
        currency=tx.currency,
        transaction_type=tx.transaction_type.value,
        sender_name=tx.sender_name,
        receiver_name=tx.receiver_name,
        destination_country=tx.destination_country,
        status=result.status.value,
        risk_score=result.risk_score,
        credit_tier=result.credit_tier.value,
        credits_consumed=result.credits_consumed,
        rule_results=[r.model_dump() for r in result.rule_results],
        behavioral_score=result.behavioral_score,
        ml_classification=result.ml_classification,
        ml_confidence=result.ml_confidence,
        total_latency_ms=result.total_latency_ms,
        pipeline_stages=result.pipeline_stages,
        rag_context=result.rag_context,
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)

    # Return the persisted DB id (single source of truth for downstream case creation)
    result.transaction_id = db_tx.id

    # Generate notifications for important events
    if result.status.value == "blocked":
        notif = Notification(
            user_id=current_user.id,
            type="blocked_tx",
            title="Transaction blocked",
            message=f"${tx.amount:,.2f} {tx.currency} from {tx.sender_name} blocked (risk: {result.risk_score:.0%}).",
            link="/transactions",
        )
        db.add(notif)

    # Credit usage alert (below 20%)
    remaining_after = current_user.total_credits - current_user.used_credits
    pct_remaining = remaining_after / max(current_user.total_credits, 1)
    if pct_remaining < 0.2 and remaining_after > 0:
        notif = Notification(
            user_id=current_user.id,
            type="credit_alert",
            title="Low credit balance",
            message=f"You have {remaining_after:.0f} credits remaining ({pct_remaining:.0%}). Consider purchasing more.",
            link="/settings?tab=billing",
        )
        db.add(notif)

    db.commit()

    logger.info(
        f"Transaction screened: {result.status.value} | risk={result.risk_score:.2f} | "
        f"tier={result.credit_tier.value} | user={current_user.email}"
    )

    return TransactionResponse(success=True, data=result)


@router.get("/api/v1/transactions", tags=["Compliance"])
def list_transactions(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent transactions for the current user."""
    txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "amount": t.amount,
            "currency": t.currency,
            "type": t.transaction_type,
            "sender": t.sender_name,
            "receiver": t.receiver_name,
            "status": t.status,
            "risk_score": t.risk_score,
            "credit_tier": t.credit_tier,
            "created_at": t.created_at.isoformat(),
        }
        for t in txs
    ]


@router.get("/api/v1/transactions/export", tags=["Compliance"])
def export_transactions(
    fmt: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export transactions as CSV with optional date range filter."""
    import csv
    from io import StringIO

    from fastapi.responses import StreamingResponse

    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    # Apply date range filters
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Transaction.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)") from None
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Transaction.created_at <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)") from None

    txs = query.order_by(Transaction.created_at.desc()).all()
    if fmt != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format supported")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Amount", "Currency", "Type", "Sender", "Receiver",
        "Country", "Status", "Risk Score", "Credit Tier", "Credits Used", "Created At",
    ])
    for t in txs:
        writer.writerow([
            t.id, t.amount, t.currency, t.transaction_type,
            t.sender_name, t.receiver_name, t.destination_country or "",
            t.status, t.risk_score, t.credit_tier, t.credits_consumed,
            t.created_at.isoformat(),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=finshield_transactions.csv"},
    )


@router.get("/api/v1/transactions/{tx_id}", tags=["Compliance"])
def get_transaction(
    tx_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full transaction detail including rule results and ML scores (for explainability)."""
    tx = db.query(Transaction).filter(
        Transaction.id == tx_id, Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {
        "id": tx.id,
        "amount": tx.amount,
        "currency": tx.currency,
        "transaction_type": tx.transaction_type,
        "sender_name": tx.sender_name,
        "receiver_name": tx.receiver_name,
        "destination_country": tx.destination_country,
        "status": tx.status,
        "risk_score": tx.risk_score,
        "credit_tier": tx.credit_tier,
        "credits_consumed": tx.credits_consumed,
        "idempotency_key": tx.idempotency_key,
        "rule_results": tx.rule_results or [],
        "behavioral_score": tx.behavioral_score,
        "ml_classification": tx.ml_classification,
        "ml_confidence": tx.ml_confidence,
        "total_latency_ms": tx.total_latency_ms,
        "pipeline_stages": tx.pipeline_stages or [],
        "rag_context": tx.rag_context,
        "created_at": tx.created_at.isoformat(),
    }


@router.delete("/api/v1/transactions/{tx_id}", tags=["Compliance"])
def delete_transaction(
    tx_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a transaction and its associated cases."""
    tx = db.query(Transaction).filter(
        Transaction.id == tx_id, Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Delete associated cases first (FK constraint)
    db.query(Case).filter(Case.transaction_id == tx_id).delete()
    db.query(CaseComment).filter(
        CaseComment.case_id.in_(
            db.query(Case.id).filter(Case.transaction_id == tx_id)
        )
    ).delete()
    db.delete(tx)
    db.commit()
    return {"deleted": tx_id}
