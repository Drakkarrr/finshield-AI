"""FinShield AI — Transaction screening, listing, export and detail."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app import config_service, crypto, metrics, screening_service
from app.auth import (
    get_current_user,
)
from app.core import SCREENING_RATE_LIMIT, credential_key, limiter, logger
from app.database import get_db
from app.db_models import (
    AuditLog,
    Case,
    Filing,
    Notification,
    Transaction,
    User,
)
from app.domain import privacy, webhooks
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

def _record_metrics(result: ScreeningResult) -> None:
    metrics.PIPELINE_TRANSACTIONS.labels(outcome=result.status.value).inc()
    for dep in result.degraded_dependencies:
        metrics.PIPELINE_DEGRADED.labels(dependency=dep).inc()
    for r in result.rule_results:
        if r.triggered:
            metrics.RULE_HITS.labels(rule=r.rule_id).inc()
    if result.ml_confidence is not None:
        metrics.CLASSIFIER_CONFIDENCE.observe(result.ml_confidence)
        fired = any(r.triggered for r in result.rule_results)
        if (result.ml_classification == "high_risk" and result.status == ScreeningStatus.APPROVED) or (
                result.ml_classification == "low_risk" and result.status == ScreeningStatus.BLOCKED and not fired):
            metrics.GATE_DISAGREEMENT.inc()


@router.post("/api/v1/transactions", response_model=TransactionResponse, tags=["Compliance"])
@limiter.limit(SCREENING_RATE_LIMIT, key_func=credential_key)
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
        Transaction.idempotency_key == tx.idempotency_key, Transaction.tenant_id == current_user.tenant_id
    ).first()
    if existing_tx and existing_tx.decision:
        return TransactionResponse(success=True, data=ScreeningResult.model_validate(existing_tx.decision))
    if existing_tx:  # screened before decisions were persisted: rebuild from the stored columns
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

    # Pure pipeline over inputs resolved through circuit breakers (lists, history, RAG, model)
    outcome = screening_service.run(db, current_user.tenant_id, tx, getattr(request.app.state, "rag_service", None))
    result = outcome.result
    _record_metrics(result)

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
        account_id=result.account_key,
        reasons=[r.model_dump() for r in result.reasons],
        model_version=result.model_version,
        degraded=result.degraded,
        shadow_result=outcome.shadow,
    )
    db.add(db_tx)
    db.flush()

    # The persisted DB id is the single source of truth for downstream case creation
    result.transaction_id = db_tx.id
    db_tx.decision = result.model_dump(mode="json")
    # Every decision is audited; parties appear only as pseudonyms (the log is append-only).
    db.add(AuditLog(user_id=current_user.id, action="transaction_screened", resource_type="transaction",
                    resource_id=db_tx.id, details={
        "decision": result.status.value, "risk_score": result.risk_score, "model_version": result.model_version,
        "degraded": result.degraded, "degraded_dependencies": result.degraded_dependencies,
        "rule_hits": [r.rule_id for r in result.rule_results if r.triggered],
        "list_hits": [{"entry_id": getattr(r, "entry_id", None), "list_version": getattr(r, "list_version", None),
                       "score": getattr(r, "score", None)} for r in result.reasons if r.source == "list"
                      and r.feature.endswith("_match")],
        "behavioral_score": result.behavioral_score, "rag_status": result.rag_status,
        "rag_sanctions_matches": len((result.rag_context or {}).get("sanctions_matches") or []),
        "inputs": {"amount": tx.amount, "currency": tx.currency, "transaction_type": tx.transaction_type.value,
                   "destination_country": tx.destination_country, "sender": crypto.pseudonym(tx.sender_name),
                   "receiver": crypto.pseudonym(tx.receiver_name), "account": crypto.pseudonym(result.account_key)},
        "api_key_id": db.info.get("api_key_id"),
    }))
    if result.account_key:
        screening_service.refresh_baseline(db, current_user.tenant_id, current_user.id, result.account_key)
    db.commit()
    db.refresh(db_tx)

    if result.status.value in ("flagged", "blocked"):
        webhooks.emit(db, current_user.tenant_id, f"transaction.{result.status.value}", {
            "transaction_id": db_tx.id, "status": result.status.value, "risk_score": result.risk_score,
            "model_version": result.model_version, "degraded": result.degraded}, user_id=current_user.id)

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
    response: Response,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the tenant's transactions, newest first. X-Total-Count carries the total for paging."""
    scoped = db.query(Transaction).filter(Transaction.tenant_id == current_user.tenant_id)
    response.headers["X-Total-Count"] = str(scoped.count())
    txs = (
        scoped
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    mask = privacy.masks_for(db, current_user.role)
    name = privacy.mask_name if mask else (lambda v: v)
    return [
        {
            "id": t.id,
            "amount": t.amount,
            "currency": t.currency,
            "type": t.transaction_type,
            "sender": name(t.sender_name),
            "receiver": name(t.receiver_name),
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

    query = db.query(Transaction).filter(Transaction.tenant_id == current_user.tenant_id)

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
    name = privacy.mask_name if privacy.masks_for(db, current_user.role) else (lambda v: v)
    for t in txs:
        writer.writerow([
            t.id, t.amount, t.currency, t.transaction_type,
            name(t.sender_name), name(t.receiver_name), t.destination_country or "",
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
        Transaction.id == tx_id, Transaction.tenant_id == current_user.tenant_id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    detail = {
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
        "account_id": tx.account_id,
        "reasons": tx.reasons or [],
        "model_version": tx.model_version,
        "degraded": bool(tx.degraded),
        "shadow_result": tx.shadow_result,
        "decision": tx.decision,
        "created_at": tx.created_at.isoformat(),
    }
    if not privacy.masks_for(db, current_user.role):
        return detail
    # Names also appear inside the stored decision, reasons and RAG context; mask them everywhere.
    return privacy.mask_names_in(detail, [tx.sender_name, tx.receiver_name], [tx.account_id])


@router.delete("/api/v1/transactions/{tx_id}", tags=["Compliance"])
def delete_transaction(
    tx_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a transaction (retention-safe: refuses inside window or if linked)."""
    tx = db.query(Transaction).filter(
        Transaction.id == tx_id, Transaction.tenant_id == current_user.tenant_id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Check if linked to a case or filing
    linked_case = db.query(Case).filter(Case.transaction_id == tx_id).first()
    linked_filing = db.query(Filing).join(Case, Filing.case_id == Case.id).filter(Case.transaction_id == tx_id).first() if linked_case else None

    if linked_case or linked_filing:
        reason = "linked case" if linked_case else "linked filing"
        db.add(AuditLog(
            user_id=current_user.id,
            action="delete_refused",
            resource_type="transaction",
            resource_id=tx_id,
            details={
                "reason": reason,
                "case_id": linked_case.id if linked_case else None,
                "filing_id": linked_filing.id if linked_filing else None,
            }
        ))
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: transaction is {reason}. Remove linked records first."
        )

    # Check retention window
    within_retention, eligible_from = privacy.is_within_retention(db, tx.created_at)
    if within_retention:
        years = float(config_service.get_setting(db, "privacy.retention_years"))
        db.add(AuditLog(
            user_id=current_user.id,
            action="delete_refused",
            resource_type="transaction",
            resource_id=tx_id,
            details={
                "reason": f"within {years:g}-year retention window",
                "eligible_from": eligible_from,
            }
        ))
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: within {years:g}-year retention window. Eligible from {eligible_from}."
        )

    # Outside retention window: pseudonymise instead of hard delete
    privacy.pseudonymise_transaction(tx)

    db.add(AuditLog(
        user_id=current_user.id,
        action="transaction_pseudonymised",
        resource_type="transaction",
        resource_id=tx_id,
        details={"reason": "outside retention window", "method": "pseudonymise"}
    ))
    db.commit()
    return {"pseudonymised": tx_id}
