"""Postgres-only schema checks (skipped on SQLite; run with TEST_DATABASE_URL=postgresql://...)."""
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

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
