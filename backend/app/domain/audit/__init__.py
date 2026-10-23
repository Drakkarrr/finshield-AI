"""Audit trail: sealing into a per-tenant hash chain, verification, signed export (S3.2).

entry_hash = sha256(prev_hash || canonical_json(entry)), with GENESIS as the first prev_hash.
Requests only append; seal() is the single writer of the chain (it locks the tenant's chain head),
so concurrent requests never contend for the chain. Unsealed rows are reported as pending.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app import crypto
from app.db_models import AuditChainHead, AuditLog

GENESIS = "0" * 64
FORMAT = "finshield-audit-export/1"


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False).encode("utf-8")


def payload(row: AuditLog) -> dict:
    """The hashed content of an entry (everything except the chain fields themselves)."""
    return {
        "id": row.id, "tenant_id": row.tenant_id, "seq": row.seq, "user_id": row.user_id, "action": row.action,
        "resource_type": row.resource_type, "resource_id": row.resource_id, "details": row.details,
        "ip_address": row.ip_address, "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def entry_hash(prev_hash: str, entry: dict) -> str:
    return hashlib.sha256(prev_hash.encode("ascii") + canonical(entry)).hexdigest()


def seal(db: Session, tenant_id: str) -> int:
    """Append every unsealed entry of the tenant to its chain. Returns how many were sealed."""
    head = db.query(AuditChainHead).filter(AuditChainHead.tenant_id == tenant_id).with_for_update().first()
    if head is None:
        head = AuditChainHead(tenant_id=tenant_id, seq=0, last_hash=GENESIS)
        db.add(head)
        db.flush()
    pending = (db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id, AuditLog.seq.is_(None))
               .order_by(AuditLog.created_at, AuditLog.id).all())
    now = datetime.utcnow()
    for row in pending:
        row.seq = head.seq + 1
        row.prev_hash = head.last_hash
        row.entry_hash = entry_hash(row.prev_hash, payload(row))
        row.sealed_at = now
        head.seq, head.last_hash = row.seq, row.entry_hash
    head.updated_at = now
    db.commit()
    return len(pending)


def verify_entries(entries: list[dict]) -> dict:
    """Recompute the chain over exported/stored entries (each with seq, prev_hash, entry_hash)."""
    prev = GENESIS
    for i, e in enumerate(entries, start=1):
        content = {k: e.get(k) for k in ("id", "tenant_id", "seq", "user_id", "action", "resource_type",
                                         "resource_id", "details", "ip_address", "created_at")}
        if e.get("seq") != i or e.get("prev_hash") != prev or entry_hash(prev, content) != e.get("entry_hash"):
            return {"ok": False, "verified": i - 1, "first_break_seq": e.get("seq"), "entry_id": e.get("id")}
        prev = e["entry_hash"]
    return {"ok": True, "verified": len(entries), "first_break_seq": None, "head_hash": prev}


def _sealed(db: Session, tenant_id: str) -> list[dict]:
    rows = (db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id, AuditLog.seq.isnot(None))
            .order_by(AuditLog.seq).all())
    return [{**payload(r), "prev_hash": r.prev_hash, "entry_hash": r.entry_hash} for r in rows]


def verify(db: Session, tenant_id: str) -> dict:
    seal(db, tenant_id)
    result = verify_entries(_sealed(db, tenant_id))
    head = db.query(AuditChainHead).filter(AuditChainHead.tenant_id == tenant_id).first()
    # The head must agree with the last sealed entry, or entries were removed from the end.
    if result["ok"] and head is not None and head.last_hash != result["head_hash"]:
        result = {**result, "ok": False, "first_break_seq": head.seq, "detail": "chain head does not match"}
    result["pending"] = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id, AuditLog.seq.is_(None)).count()
    return result


def export(db: Session, tenant_id: str) -> dict:
    """Signed chain-of-custody bundle. Verifiable offline with scripts/verify_audit_export.py and
    the public key alone: the chain proves integrity, the signature proves origin."""
    seal(db, tenant_id)
    entries = _sealed(db, tenant_id)
    bundle = {
        "format": FORMAT, "tenant_id": tenant_id, "exported_at": datetime.utcnow().isoformat(),
        "count": len(entries), "verification": verify_entries(entries), "entries": entries,
        "public_key": crypto.public_key_pem(),
    }
    bundle["signature"] = crypto.sign(canonical(bundle))
    return bundle
