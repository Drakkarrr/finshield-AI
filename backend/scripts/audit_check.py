"""Verify every tenant's audit chain and optionally write signed exports (S4.5 restore check).

Usage (from backend/):
    python -m scripts.audit_check [--export-dir DIR]

Prints one line per tenant with its entry count and chain head hash. Run it before a backup and
after a restore: identical head hashes prove the restored chain is the one that was backed up.
With --export-dir, also writes <tenant>.json bundles plus public-key.pem for the standalone
verifier (scripts/verify_audit_export.py), so the check does not rely on FinShield code alone.
Exit 0 only when every chain verifies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import crypto
from app.database import SessionLocal
from app.db_models import Tenant
from app.domain import audit


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export-dir", type=Path)
    args = ap.parse_args(argv)
    if args.export_dir:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        (args.export_dir / "public-key.pem").write_text(crypto.public_key_pem(), encoding="ascii")
    failures = 0
    with SessionLocal() as db:
        db.info["rls_bypass"] = True  # system check across tenants
        tenants = [t for (t,) in db.query(Tenant.id).order_by(Tenant.id).all()]
        for tenant_id in tenants:
            result = audit.verify(db, tenant_id)
            failures += 0 if result["ok"] else 1
            head = result.get("head_hash") or "-"
            print(f"{'OK  ' if result['ok'] else 'FAIL'} {tenant_id:40} entries={result['verified']:<6} head={head}")
            if args.export_dir:
                bundle = audit.export(db, tenant_id)
                (args.export_dir / f"{tenant_id}.json").write_text(json.dumps(bundle), encoding="utf-8")
    print(f"{len(tenants)} tenant(s), {failures} broken chain(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
