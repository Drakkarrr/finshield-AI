"""
FinShield AI — Database Configuration

PostgreSQL is the primary database (ruling D6). SQLite is used only under APP_ENV=test,
unless TEST_DATABASE_URL points the suite at Postgres (the CI Postgres job does this).
The schema is owned by Alembic (backend/migrations); create_all is test-only.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

APP_ENV = os.getenv("APP_ENV", "production")

if APP_ENV == "test":
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_finshield.db")
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    if not DATABASE_URL.startswith("postgresql"):
        raise RuntimeError(
            "DATABASE_URL must be a postgresql:// URL outside APP_ENV=test "
            "(SQLite is test-only, ruling D6)"
        )

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        echo=os.getenv("DEBUG", "false").lower() == "true",
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Bookkeeping that runs while a request already holds a connection (circuit-breaker state) uses
# its own small pool. Taking a second connection from the request pool deadlocks under load:
# every worker thread holds one connection and waits for another that no one can release.
side_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}) if IS_SQLITE else     create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)
SideSession = sessionmaker(autocommit=False, autoflush=False, bind=side_engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_schema():
    """Build the test schema. SQLite: straight from the models, for speed. Postgres: through
    the real Alembic migrations, so the Postgres suite also proves the migrations work."""
    if APP_ENV != "test":
        raise RuntimeError("create_test_schema() is test-only; run `alembic upgrade head`")
    import app.db_models  # noqa: F401  (register every model on Base.metadata)

    if IS_SQLITE:
        Base.metadata.create_all(bind=engine)
        return
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(cfg, "head")
