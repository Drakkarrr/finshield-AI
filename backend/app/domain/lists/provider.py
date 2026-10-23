"""Persistence-backed list access: import (replace a source's entries) and cached snapshots."""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import HighRiskCountry, ListImport, WatchlistEntry
from app.domain.lists import ListEntry, WatchlistSnapshot

_lock = threading.Lock()
_cache: dict[str, object] = {"key": None, "snapshot": None}


def store_import(db: Session, entries: list[ListEntry], source: str, list_type: str, list_version: str,
                 is_fixture: bool = False) -> int:
    """Replace every entry of `source` with `entries` and record the import. Returns entry count."""
    now = datetime.utcnow()
    db.query(WatchlistEntry).filter(WatchlistEntry.source == source).delete(synchronize_session=False)
    db.add_all(WatchlistEntry(
        id=e.id, source=e.source, list_version=e.list_version, list_type=e.list_type, primary_name=e.primary_name,
        aliases=list(e.aliases), entity_type=e.entity_type, country=e.country, effective_from=now,
    ) for e in entries)
    db.add(ListImport(source=source, list_type=list_type, list_version=list_version, entry_count=len(entries),
                      imported_at=now, is_fixture=is_fixture))
    db.commit()
    return len(entries)


def snapshot(db: Session) -> WatchlistSnapshot:
    """The active entries as an immutable index, rebuilt only when a new import lands."""
    key = db.query(func.max(ListImport.id)).scalar()
    with _lock:
        cached = _cache["snapshot"]
        if _cache["key"] == key and isinstance(cached, WatchlistSnapshot):
            return cached
    now = datetime.utcnow()
    rows = db.query(WatchlistEntry).all()
    entries = [
        ListEntry(id=r.id, source=r.source, list_version=r.list_version, list_type=r.list_type,
                  primary_name=r.primary_name, aliases=tuple(r.aliases or ()), entity_type=r.entity_type,
                  country=r.country)
        for r in rows
        if (r.effective_from is None or r.effective_from <= now) and (r.effective_to is None or now < r.effective_to)
    ]
    snap = WatchlistSnapshot(entries=sorted(entries, key=lambda e: e.id),
                             versions={r.source: r.list_version for r in rows})
    with _lock:
        _cache.update(key=key, snapshot=snap)
    return snap


def high_risk_countries(db: Session) -> frozenset[str]:
    return frozenset(r.code for r in db.query(HighRiskCountry).all())


def status(db: Session, max_age_hours: float, now: Optional[datetime] = None) -> list[dict]:
    """Freshness of every source: latest import, version, size, age and whether it is stale."""
    now = now or datetime.utcnow()
    latest: dict[str, ListImport] = {}
    for imp in db.query(ListImport).order_by(ListImport.id).all():
        latest[imp.source] = imp
    out = []
    for source, imp in sorted(latest.items()):
        age_h = (now - imp.imported_at).total_seconds() / 3600
        out.append({
            "source": source, "list_type": imp.list_type, "list_version": imp.list_version,
            "entry_count": imp.entry_count, "imported_at": imp.imported_at.isoformat(),
            "age_hours": round(age_h, 2), "stale": age_h > max_age_hours, "is_fixture": imp.is_fixture,
        })
    return out
