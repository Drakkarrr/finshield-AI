"""Data-subject requests (DSAR): access export and erasure with retention preserved (S3.3).

The balancing is the point:
- Access exports the subject's own transaction data. Case investigations, investigator notes and
  regulatory filings are WITHHELD and the export says so: disclosing a SAR to its subject is
  prohibited "tipping off" (31 U.S.C. 5318(g)(2); GDPR Art. 23 restriction under AML law).
- Erasure pseudonymises a transaction only when no obligation requires keeping it: records inside
  the AML record-keeping window (privacy.retention_years, default 5) or linked to a case or filing
  are RETAINED, each with its reason. The audit log needs no change: it only ever holds pseudonyms.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app import config_service, crypto
from app.db_models import ApiKey, AuditLog, Case, CaseComment, Filing, Notification, Transaction, User

ERASED = "[erased]"
RETENTION_BASIS = "AML record-keeping obligation (e.g. 31 CFR 1010.430: 5 years); GDPR Art. 17(3)(b)"
FILING_BASIS = "Linked to a suspicious-activity case or filing; must be retained and not disclosed (tipping-off)"


def mask_name(value: str | None) -> str | None:
    """'Jane Smith' -> 'J*** S****' (first letter of each word kept)."""
    if not value:
        return value
    return " ".join(w[0] + "*" * max(len(w) - 1, 1) for w in value.split())


def mask_account(value: str | None) -> str | None:
    if not value:
        return value
    return "*" * max(len(value) - 4, 2) + value[-4:]


def mask_names_in(value: Any, names: list[str | None], accounts: list[str | None] | None = None) -> Any:
    """Replace every occurrence of the given names / account ids in a nested structure with masks."""
    out = value
    for n in sorted({n for n in names if n}, key=len, reverse=True):
        out = _replace(out, n, mask_name(n) or "")
    for a in {a for a in accounts or [] if a}:
        out = _replace(out, a, mask_account(a) or "")
    return out


def _replace(value: Any, needle: str, repl: str) -> Any:
    if isinstance(value, str):
        return value.replace(needle, repl)
    if isinstance(value, list):
        return [_replace(v, needle, repl) for v in value]
    if isinstance(value, dict):
        return {k: _replace(v, needle, repl) for k, v in value.items()}
    return value


def masks_for(db: Session, role: str) -> bool:
    return role in (config_service.get_setting(db, "privacy.mask_roles") or [])


def _subject_transactions(db: Session, tenant_id: str, subject: str) -> list[Transaction]:
    s = subject.strip().casefold()
    return (db.query(Transaction).filter(Transaction.tenant_id == tenant_id, or_(
        func.lower(Transaction.sender_name) == s, func.lower(Transaction.receiver_name) == s,
        func.lower(Transaction.account_id) == s)).order_by(Transaction.created_at).all())


def _subject_user(db: Session, tenant_id: str, subject: str) -> User | None:
    return db.query(User).filter(User.tenant_id == tenant_id, func.lower(User.email) == subject.strip().casefold()).first()


def _linked_cases(db: Session, tx_ids: list[str]) -> list[Case]:
    return db.query(Case).filter(Case.transaction_id.in_(tx_ids)).all() if tx_ids else []


def _audit_refs(db: Session, tenant_id: str, subject: str) -> int:
    ref = crypto.pseudonym(subject)
    return db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id,
                                     cast(AuditLog.details, String).contains(ref or "")).count()


def access_export(db: Session, tenant_id: str, subject_type: str, subject: str) -> dict:
    out: dict[str, Any] = {"subject_type": subject_type, "generated_at": datetime.utcnow().isoformat()}
    if subject_type == "user":
        user = _subject_user(db, tenant_id, subject)
        if user is None:
            return {**out, "found": False}
        out.update(found=True, profile={
            "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
            "company": user.company, "role": user.role, "created_at": user.created_at.isoformat() if user.created_at else None,
            "timezone": user.timezone})
        out["api_keys"] = [{"name": k.name, "prefix": k.key_prefix, "active": k.is_active,
                            "created_at": k.created_at.isoformat() if k.created_at else None}
                           for k in db.query(ApiKey).filter(ApiKey.user_id == user.id).all()]
        out["notifications"] = db.query(Notification).filter(Notification.user_id == user.id).count()
        out["case_comments_authored"] = db.query(CaseComment).filter(CaseComment.user_id == user.id).count()
        out["audit_entries_as_actor"] = db.query(AuditLog).filter(AuditLog.user_id == user.id).count()
        return out
    txs = _subject_transactions(db, tenant_id, subject)
    cases = _linked_cases(db, [t.id for t in txs])
    out.update(found=bool(txs), transactions=[{
        "id": t.id, "created_at": t.created_at.isoformat() if t.created_at else None, "amount": t.amount,
        "currency": t.currency, "type": t.transaction_type, "sender_name": t.sender_name,
        "receiver_name": t.receiver_name, "destination_country": t.destination_country,
        "account_id": t.account_id, "description": t.description, "status": t.status} for t in txs])
    out["withheld"] = {
        "cases_and_investigator_notes": len(cases),
        "regulatory_filings": db.query(Filing).filter(Filing.case_id.in_([c.id for c in cases])).count() if cases else 0,
        "legal_basis": FILING_BASIS,
    } if cases else None
    out["audit_entries_referencing_subject"] = _audit_refs(db, tenant_id, subject)
    return out


def _scrub(value: Any, needles: list[str]) -> Any:
    if isinstance(value, str):
        out = value
        for n in needles:
            if n:
                out = out.replace(n, ERASED)
        return out
    if isinstance(value, list):
        return [_scrub(v, needles) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v, needles) for k, v in value.items()}
    return value


def erase(db: Session, tenant_id: str, subject_type: str, subject: str, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    years = float(config_service.get_setting(db, "privacy.retention_years"))
    cutoff = now - timedelta(days=365.25 * years)
    erased: list[str] = []
    retained: list[dict] = []
    if subject_type == "user":
        user = _subject_user(db, tenant_id, subject)
        if user is None:
            return {"found": False, "erased": [], "retained": []}
        # The row stays (audit entries reference its id); everything personal on it goes.
        user.email = f"erased-{user.id}@invalid"
        user.first_name, user.last_name, user.company, user.timezone = ERASED, ERASED, None, None
        user.hashed_password = crypto.pseudonym(secrets.token_hex(16)) or ""
        user.is_active = False
        for key in db.query(ApiKey).filter(ApiKey.user_id == user.id).all():
            key.is_active = False
        db.query(Notification).filter(Notification.user_id == user.id).delete(synchronize_session=False)
        erased.append(f"user:{user.id}")
        retained.append({"record": "audit_entries_as_actor", "reason": "append-only audit trail (actor id only)",
                         "legal_basis": "Regulatory audit obligation; entries hold no raw personal data"})
        return {"found": True, "erased": erased, "retained": retained}

    txs = _subject_transactions(db, tenant_id, subject)
    linked = {c.transaction_id for c in _linked_cases(db, [t.id for t in txs])}
    for t in txs:
        if t.id in linked:
            retained.append({"record": f"transaction:{t.id}", "reason": "linked case/filing", "legal_basis": FILING_BASIS})
        elif t.created_at and t.created_at >= cutoff:
            retained.append({"record": f"transaction:{t.id}", "reason": f"within {years:g}-year retention",
                             "legal_basis": RETENTION_BASIS,
                             "eligible_from": (t.created_at + timedelta(days=365.25 * years)).date().isoformat()})
        else:
            needles = [x for x in {t.sender_name, t.receiver_name, t.account_id} if x and x.casefold() == subject.casefold()]
            for field in ("sender_name", "receiver_name"):
                if (getattr(t, field) or "").casefold() == subject.casefold():
                    setattr(t, field, ERASED)
            if (t.account_id or "").casefold() == subject.casefold():
                t.account_id = crypto.pseudonym(t.account_id)
            t.description = _scrub(t.description, needles)
            for col in ("decision", "reasons", "rule_results", "rag_context"):
                setattr(t, col, _scrub(getattr(t, col), needles))
            erased.append(f"transaction:{t.id}")
    return {"found": bool(txs), "erased": erased, "retained": retained,
            "audit_entries_referencing_subject": _audit_refs(db, tenant_id, subject),
            "audit_note": "audit entries hold pseudonyms only and are append-only; nothing to erase there"}


def classification(db: Session) -> dict:
    return {"pii_fields": config_service.get_setting(db, "privacy.pii_fields"),
            "masked_roles": config_service.get_setting(db, "privacy.mask_roles"),
            "retention_years": config_service.get_setting(db, "privacy.retention_years"),
            "dsar_due_days": config_service.get_setting(db, "privacy.dsar_due_days")}
