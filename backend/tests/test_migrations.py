"""Postgres-only schema checks (skipped on SQLite; run with TEST_DATABASE_URL=postgresql://...)."""
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import app.db_models  # noqa: F401
from app.database import Base, engine

pytestmark = pytest.mark.postgres

BACKEND = Path(__file__).resolve().parent.parent


def test_database_is_at_alembic_head():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == head


def test_migrations_match_models():
    """A model change without a migration fails here."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def _alembic(connection) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["connection"] = connection  # migrate this database, not the suite's
    return cfg


def test_migration_0013_backfills_filing_versions():
    """0013 snapshots the narrative of filings submitted before versioning existed, so the text
    sent to the regulator survives the first amendment. Runs on its own throwaway database: the
    suite's database is never downgraded, and nothing depends on data from other tests."""
    owner_url = engine.url.render_as_string(hide_password=False)
    name = f"fs_migtest_{uuid.uuid4().hex[:8]}"
    admin = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    scratch = create_engine(make_url(owner_url).set(database=name))  # owner: no RLS, no app role
    try:
        with scratch.connect() as conn:
            command.upgrade(_alembic(conn), "0012")
            conn.commit()
            conn.execute(text("""
                INSERT INTO tenants (id, name, created_at) VALUES ('t1', 't1', now());
                INSERT INTO users (id, tenant_id, email, hashed_password, first_name, last_name, role, plan,
                                   total_credits, used_credits, is_active, is_verified, is_trial, created_at, updated_at)
                    VALUES ('u1', 't1', 'mig@test.io', 'x', 'M', 'T', 'admin', 'starter', 0, 0, true, false, false, now(), now());
                INSERT INTO transactions (id, tenant_id, user_id, idempotency_key, amount, transaction_type,
                                          sender_name, receiver_name, created_at)
                    VALUES ('x1', 't1', 'u1', 'k1', 1, 'ach', 's', 'r', now());
                INSERT INTO cases (id, tenant_id, transaction_id, user_id, reason, created_at)
                    VALUES ('c1', 't1', 'x1', 'u1', 'r', now());
                INSERT INTO filings (id, tenant_id, case_id, user_id, filing_type, status, narrative,
                                     submitted_at, submitted_by, created_at, updated_at) VALUES
                    ('f-sub', 't1', 'c1', 'u1', 'SAR', 'submitted', 'as submitted', now(), 'u1', now(), now()),
                    ('f-conf', 't1', 'c1', 'u1', 'SAR', 'confirmed', 'as confirmed', NULL, NULL, now(), now()),
                    ('f-draft', 't1', 'c1', 'u1', 'SAR', 'draft', 'still a draft', NULL, NULL, now(), now());
            """))
            conn.commit()

            for _ in range(2):  # upgrade, then prove the downgrade/upgrade cycle works with data present
                command.upgrade(_alembic(conn), "0013")
                conn.commit()
                rows = {r.filing_id: r for r in conn.execute(text(
                    "SELECT filing_id, version_number, narrative, changed_by, changed_at FROM filing_versions"))}
                assert set(rows) == {"f-sub", "f-conf"}  # drafts are not versioned
                assert rows["f-sub"].narrative == "as submitted" and rows["f-conf"].narrative == "as confirmed"
                assert all(r.version_number == 1 and r.changed_by == "u1" and r.changed_at is not None
                           for r in rows.values())  # f-conf had no submitted_by / submitted_at
                command.downgrade(_alembic(conn), "0012")
                conn.commit()
    finally:
        scratch.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
