"""Copy rows from a dev SQLite database into the Postgres primary. One-off dev convenience.

Usage (from backend/):
    DATABASE_URL=postgresql://... python -m scripts.sqlite_to_postgres path/to/finshield.db

Run `alembic upgrade head` on the target first. Tables are copied in foreign-key order using
the ORM column types, so SQLite's text datetimes and JSON are converted properly. Rows whose
primary key already exists in the target are skipped, so the script is safe to re-run.

Pre-tenancy files (no tenant_id) get the same backfill as migration 0005: each user becomes its
own tenant and that tenant's admin, child rows inherit their owner's tenant, and audit rows with
no user go to the 'system' tenant. It writes under an explicit RLS bypass (a system job).
"""
from __future__ import annotations

import sys
from datetime import datetime

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects.postgresql import insert

import app.db_models  # noqa: F401  (registers every model on Base.metadata)
from app.database import Base, engine
from app.db_models import Tenant

BATCH = 500
SYSTEM_TENANT = "system"


def copy(sqlite_path: str) -> dict[str, int]:
    source = create_engine(f"sqlite:///{sqlite_path}")
    source_tables = set(inspect(source).get_table_names())
    copied: dict[str, int] = {}
    tenant_of_user: dict[str, str] = {}
    tenants = Base.metadata.tables[Tenant.__tablename__]
    with source.connect() as src, engine.begin() as dst:
        dst.exec_driver_sql("SELECT set_config('app.rls_bypass', 'on', true)")
        for table in Base.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            source_cols = {c["name"] for c in inspect(source).get_columns(table.name)}
            cols = [c for c in table.columns if c.name in source_cols]
            rows = [dict(r._mapping) for r in src.execute(select(*cols))]
            needs_tenant = "tenant_id" in table.c and "tenant_id" not in source_cols
            if needs_tenant and table.name == "users":
                new_tenants = []
                for r in rows:
                    r["tenant_id"] = tenant_of_user[r["id"]] = f"tenant-{r['id']}"
                    r.setdefault("role", "admin")
                    new_tenants.append({"id": r["tenant_id"], "name": r.get("company") or r["email"],
                                        "created_at": r.get("created_at") or datetime.utcnow()})
                if new_tenants:
                    dst.execute(insert(tenants).values(new_tenants).on_conflict_do_nothing())
            elif needs_tenant:
                for r in rows:
                    r["tenant_id"] = tenant_of_user.get(r.get("user_id") or "", SYSTEM_TENANT)
                if any(r["tenant_id"] == SYSTEM_TENANT for r in rows):
                    dst.execute(insert(tenants).values(id=SYSTEM_TENANT, name=SYSTEM_TENANT,
                                                       created_at=datetime.utcnow()).on_conflict_do_nothing())
            elif table.name == "users":
                tenant_of_user.update({r["id"]: r["tenant_id"] for r in rows})
            inserted = 0
            for i in range(0, len(rows), BATCH):
                stmt = insert(table).values(rows[i:i + BATCH]).on_conflict_do_nothing()
                inserted += dst.execute(stmt).rowcount or 0
            copied[table.name] = inserted
    return copied


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if engine.dialect.name != "postgresql":
        sys.exit("DATABASE_URL must point at Postgres")
    for name, n in copy(sys.argv[1]).items():
        print(f"{name:28} {n} rows copied")
