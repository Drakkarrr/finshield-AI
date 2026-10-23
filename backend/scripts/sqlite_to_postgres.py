"""Copy rows from a dev SQLite database into the Postgres primary. One-off dev convenience.

Usage (from backend/):
    DATABASE_URL=postgresql://... python -m scripts.sqlite_to_postgres path/to/finshield.db

Run `alembic upgrade head` on the target first. Tables are copied in foreign-key order using
the ORM column types, so SQLite's text datetimes and JSON are converted properly. Rows whose
primary key already exists in the target are skipped, so the script is safe to re-run.
"""
from __future__ import annotations

import sys

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects.postgresql import insert

import app.db_models  # noqa: F401  (registers every model on Base.metadata)
from app.database import Base, engine

BATCH = 500


def copy(sqlite_path: str) -> dict[str, int]:
    source = create_engine(f"sqlite:///{sqlite_path}")
    source_tables = set(inspect(source).get_table_names())
    copied: dict[str, int] = {}
    with source.connect() as src, engine.begin() as dst:
        for table in Base.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            source_cols = {c["name"] for c in inspect(source).get_columns(table.name)}
            cols = [c for c in table.columns if c.name in source_cols]
            rows = [dict(r._mapping) for r in src.execute(select(*cols))]
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
