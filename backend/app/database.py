"""
FinShield AI — Database Configuration

PostgreSQL is the primary database (ruling D6). SQLite is used only under APP_ENV=test,
unless TEST_DATABASE_URL points the suite at Postgres (the CI Postgres job does this).
The schema is owned by Alembic (backend/migrations); create_all is test-only.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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

# --- Tenant isolation (S3.4, ruling D3) ---------------------------------------------------------
# Postgres RLS policies (migration 0005) filter every tenant-owned table on app.tenant_id unless
# app.rls_bypass is on. Superusers bypass RLS, so request connections drop to the non-login
# APP_DB_ROLE created by the migration; Alembic uses its own engine and keeps owner rights.
APP_DB_ROLE = os.getenv("APP_DB_ROLE", "finshield_app")
TENANT_KEY = "tenant_id"
BYPASS_KEY = "rls_bypass"

if not IS_SQLITE and APP_DB_ROLE:
    @event.listens_for(engine, "connect")
    def _use_app_role(dbapi_conn, _record):
        # SET ROLE is transactional: commit it, or the pool's reset-on-return ROLLBACK undoes it and
        # the connection goes back to the pool as the (RLS-exempt) login user.
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET ROLE "{APP_DB_ROLE}"')
        dbapi_conn.commit()


@event.listens_for(SessionLocal, "after_begin")
def _apply_tenant(session, _transaction, connection):
    """Re-applied at the start of every transaction, so it survives mid-request commits. The role is
    re-asserted transaction-locally too, so no session ever runs as the login user."""
    if connection.dialect.name != "postgresql":
        return
    if APP_DB_ROLE:
        connection.exec_driver_sql(f'SET LOCAL ROLE "{APP_DB_ROLE}"')
    connection.exec_driver_sql(
        "SELECT set_config('app.tenant_id', %s, true), set_config('app.rls_bypass', %s, true)",
        (session.info.get(TENANT_KEY) or "", "on" if session.info.get(BYPASS_KEY) else "off"),
    )


@event.listens_for(SessionLocal, "before_flush")
def _stamp_tenant(session, _ctx, _instances):
    """New tenant-owned rows inherit the session's tenant; a row with no tenant fails loudly."""
    for obj in session.new:
        if hasattr(obj, "tenant_id") and obj.tenant_id is None:
            tenant = session.info.get(TENANT_KEY)
            if tenant is None:
                raise RuntimeError(f"{type(obj).__name__} has no tenant_id and the session is not bound to a tenant")
            obj.tenant_id = tenant


def bind_tenant(session: Session, tenant_id: str) -> None:
    """Scope the session to one tenant from the next transaction on (ends any open one)."""
    session.commit()
    session.info[TENANT_KEY] = tenant_id
    session.info.pop(BYPASS_KEY, None)


@contextmanager
def rls_bypass(session: Session) -> Iterator[Session]:
    """Cross-tenant access for auth bootstrap (login / token lookup) and system jobs only."""
    session.commit()
    session.info[BYPASS_KEY] = True
    try:
        yield session
    finally:
        session.commit()
        session.info.pop(BYPASS_KEY, None)

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
