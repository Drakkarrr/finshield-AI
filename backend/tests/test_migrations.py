"""Postgres-only schema checks (skipped on SQLite; run with TEST_DATABASE_URL=postgresql://...)."""
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

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


def test_migration_0013_backfills_filing_versions():
    """Migration 0013 backfills version 1 for existing submitted/confirmed filings."""
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))

    # Generate unique IDs for test data
    filing_id_1 = f"test-filing-{uuid.uuid4().hex[:8]}"
    filing_id_2 = f"test-filing-{uuid.uuid4().hex[:8]}"

    # Downgrade to 0012 (before filing_versions table exists)
    command.downgrade(cfg, "0012")

    try:
        # Insert test data: one submitted filing with submitted_at/submitted_by set,
        # one confirmed filing with them NULL
        with engine.connect() as conn:
            # Enable RLS bypass for system-level operations
            conn.execute(text("SET app.rls_bypass = 'on'"))
            # Get a tenant and user to use
            tenant_id = conn.execute(text("SELECT id FROM tenants LIMIT 1")).scalar()
            user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar()
            case_id = conn.execute(text("SELECT id FROM cases LIMIT 1")).scalar()

            if not all([tenant_id, user_id, case_id]):
                pytest.skip("Need at least one tenant, user, and case in the database")

            # Insert a submitted filing with submitted_at and submitted_by set
            conn.execute(text("""
                INSERT INTO filings (id, case_id, user_id, filing_type, status, narrative, tenant_id, submitted_at, submitted_by, created_at, updated_at)
                VALUES (:filing_id_1, :case_id, :user_id, 'SAR', 'submitted', 'Original narrative 1', :tenant_id, now(), :user_id, now(), now())
            """), {"filing_id_1": filing_id_1, "case_id": case_id, "user_id": user_id, "tenant_id": tenant_id})

            # Insert a confirmed filing with submitted_at and submitted_by NULL
            conn.execute(text("""
                INSERT INTO filings (id, case_id, user_id, filing_type, status, narrative, tenant_id, created_at, updated_at)
                VALUES (:filing_id_2, :case_id, :user_id, 'SAR', 'confirmed', 'Original narrative 2', :tenant_id, now(), now())
            """), {"filing_id_2": filing_id_2, "case_id": case_id, "user_id": user_id, "tenant_id": tenant_id})

            conn.commit()

        # Upgrade to 0013 (should backfill version 1 for both filings)
        command.upgrade(cfg, "0013")

        # Verify backfill
        with engine.connect() as conn:
            # Check filing 1 (had submitted_at and submitted_by)
            v1 = conn.execute(text(f"""
                SELECT version_number, narrative, changed_by, changed_at, change_reason
                FROM filing_versions WHERE filing_id = '{filing_id_1}' AND version_number = 1
            """)).fetchone()
            assert v1 is not None, f"Version 1 should exist for {filing_id_1}"
            assert v1.narrative == "Original narrative 1"
            assert v1.changed_by == user_id
            assert v1.change_reason == "Backfilled version 1 for pre-existing filing"

            # Check filing 2 (had submitted_at and submitted_by NULL)
            v2 = conn.execute(text(f"""
                SELECT version_number, narrative, changed_by, changed_at, change_reason
                FROM filing_versions WHERE filing_id = '{filing_id_2}' AND version_number = 1
            """)).fetchone()
            assert v2 is not None, f"Version 1 should exist for {filing_id_2}"
            assert v2.narrative == "Original narrative 2"
            assert v2.changed_by == user_id  # Should fall back to user_id
            assert v2.change_reason == "Backfilled version 1 for pre-existing filing"

        # Test downgrade and upgrade again (reversibility)
        command.downgrade(cfg, "0012")
        command.upgrade(cfg, "0013")

        # Verify backfill still works after downgrade/upgrade cycle
        with engine.connect() as conn:
            v1 = conn.execute(text(f"""
                SELECT version_number, narrative FROM filing_versions WHERE filing_id = '{filing_id_1}' AND version_number = 1
            """)).fetchone()
            assert v1 is not None
            assert v1.narrative == "Original narrative 1"

    finally:
        # Ensure we're at head before cleanup
        command.upgrade(cfg, "head")
        # Clean up test data
        with engine.connect() as conn:
            conn.execute(text("SET app.rls_bypass = 'on'"))
            conn.execute(text(f"DELETE FROM filing_versions WHERE filing_id IN ('{filing_id_1}', '{filing_id_2}')"))
            conn.execute(text(f"DELETE FROM filings WHERE id IN ('{filing_id_1}', '{filing_id_2}')"))
            conn.commit()

